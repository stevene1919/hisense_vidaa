"""MQTT Authentication, TLS setup, PIN validation, and token refresh logic for Hisense VIDAA TV."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import socket
import ssl
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

from ..crypto import generate_initial_credentials
from .topics import TopicPaths, build_topic_paths

_LOGGER = logging.getLogger(__name__)


def apply_mqtt_tls(
    client: mqtt.Client,
    certfile: str | None,
    keyfile: str | None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    use_ssl: bool = True,
) -> None:
    """Applies TLS certificate configuration to an MQTT client instance."""
    if not use_ssl or not certfile or not keyfile:
        return

    if verify_ssl and ca_cert and os.path.isfile(ca_cert):
        client.tls_set(
            ca_certs=ca_cert,
            certfile=certfile,
            keyfile=keyfile,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS,
        )
        client.tls_insecure_set(True)
    else:
        client.tls_set(
            ca_certs=None,
            certfile=certfile,
            keyfile=keyfile,
            cert_reqs=ssl.CERT_NONE,
            tls_version=ssl.PROTOCOL_TLS,
        )
        client.tls_insecure_set(True)


def is_token_expired(
    access_token_time: int | None,
    access_token_duration_day: int | None,
    margin_seconds: int = 0,
) -> bool:
    """Checks if access token is expired or within margin of expiration."""
    if not access_token_time or not access_token_duration_day:
        return False
    now = int(time.time())
    token_expiration = access_token_time + (access_token_duration_day * 86400)
    return (token_expiration - now) <= margin_seconds


def perform_token_refresh(
    ip: str,
    client_id: str,
    username: str,
    refresh_token: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    port: int = 36669,
    timeout: float = 10.0,
) -> dict[str, Any] | None:
    """Connects synchronously using refresh_token to obtain new token credentials from TV."""
    if not refresh_token or not client_id or not username:
        _LOGGER.warning("[%s] Cannot refresh token: missing refresh_token, client_id, or username", ip)
        return None

    paths: TopicPaths = build_topic_paths(client_id)
    client = mqtt.Client(
        client_id=client_id,
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
    )
    apply_mqtt_tls(
        client,
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        verify_ssl=verify_ssl,
        use_ssl=True,
    )
    client.username_pw_set(username=username, password=refresh_token)

    lock = threading.Event()
    updated_data: dict[str, Any] = {}
    connect_rc = [None]

    def on_refresh_connect(cl: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
        connect_rc[0] = rc
        if rc == 0:
            _LOGGER.debug("[%s] Refresh client connected successfully. Subscribing to token topics...", ip)
            cl.subscribe(paths.mobile + "#")
            payload = json.dumps({"refreshtoken": refresh_token or ""})
            cl.publish(paths.platform + "data/gettoken", payload)
        else:
            _LOGGER.warning("[%s] Refresh client connection rejected (rc: %d)", ip, rc)
            lock.set()

    def on_refresh_subscribe(cl: mqtt.Client, userdata: Any, mid: int, granted_qos: Any) -> None:
        payload = json.dumps({"refreshtoken": refresh_token or ""})
        cl.publish(paths.platform + "data/gettoken", payload)

    def on_token_msg(cl: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        nonlocal updated_data
        try:
            payload_str = msg.payload.decode("utf-8", errors="ignore")
            _LOGGER.debug("[%s] Refresh client received message on %s: %s", ip, msg.topic, payload_str)
            data = json.loads(payload_str)
            if isinstance(data, dict) and "accesstoken" in data:
                updated_data = data
                lock.set()
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing refreshed token: %s", ip, e)

    client.on_connect = on_refresh_connect
    client.on_subscribe = on_refresh_subscribe
    client.on_message = on_token_msg
    client.on_disconnect = lambda cl, userdata, rc: _LOGGER.debug("[%s] Refresh client disconnected: %d", ip, rc)

    try:
        client.connect(ip, port, 60)
        client.loop_start()
        lock.wait(timeout=timeout)
    except (OSError, TimeoutError) as e:
        _LOGGER.debug("[%s] TV is offline or unreachable during token refresh: %s", ip, e)
    except Exception as e:
        _LOGGER.warning("[%s] Unexpected error during refresh client connection: %s", ip, e)
    finally:
        with contextlib.suppress(Exception):
            client.loop_stop()
            client.disconnect()

    if updated_data:
        return updated_data

    if connect_rc[0] is not None:
        _LOGGER.warning("[%s] Failed to refresh token (Connect RC: %d)", ip, connect_rc[0])

    return None


def test_tv_ssl_connection(
    ip: str,
    certfile: str,
    keyfile: str,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Tests the TLS handshake against the TV MQTT broker on port 36669."""
    if not certfile or not os.path.isfile(certfile):
        raise FileNotFoundError(f"SSL Certificate file not found: '{certfile}'")
    if not keyfile or not os.path.isfile(keyfile):
        raise FileNotFoundError(f"SSL Private Key file not found: '{keyfile}'")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    if verify_ssl and ca_cert and os.path.isfile(ca_cert):
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=ca_cert)
    else:
        context.verify_mode = ssl.CERT_NONE
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)

    with (
        socket.create_connection((ip, 36669), timeout=timeout) as sock,
        context.wrap_socket(sock) as ssock,
    ):
        cipher_name, _proto, bits = ssock.cipher()
        return {
            "connected": True,
            "tls_version": ssock.version(),
            "cipher": cipher_name,
            "bits": bits,
            "certfile": certfile,
            "keyfile": keyfile,
            "ca_cert": ca_cert if verify_ssl else None,
        }


def probe_tv_auth_methods(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    mac: str | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Probes TV MQTT broker with various auth algorithms to diagnose compatibility."""
    results = {
        "legacy_static": {"rc": None, "supported": False},
        "standard_dynamic": {"rc": None, "supported": False},
        "middle_dynamic": {"rc": None, "supported": False},
        "modern_dynamic": {"rc": None, "supported": False},
    }

    def _setup_tls(c: mqtt.Client) -> None:
        if certfile and keyfile and os.path.isfile(certfile) and os.path.isfile(keyfile):
            if verify_ssl and ca_cert and os.path.isfile(ca_cert):
                c.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
            else:
                c.tls_set(ca_certs=None, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
            c.tls_insecure_set(True)

    # 1. Legacy static ('hisenseservice')
    try:
        leg_rc = [None]
        leg_lock = threading.Event()
        leg_client = mqtt.Client(client_id="hisenseservice", clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(leg_client)
        leg_client.username_pw_set(username="hisenseservice", password="multimqttservice")
        leg_client.on_connect = lambda c, u, f, rc: (leg_rc.__setitem__(0, rc), leg_lock.set())
        leg_client.on_disconnect = lambda c, u, rc: leg_lock.set()
        leg_client.connect_async(ip, 36669, 5)
        leg_client.loop_start()
        leg_lock.wait(timeout=timeout)
        leg_client.loop_stop()
        leg_client.disconnect()
        results["legacy_static"]["rc"] = leg_rc[0]
        results["legacy_static"]["supported"] = (leg_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("[%s] Legacy static probe error: %s", ip, e)

    # 2. Standard dynamic pairing (his$<timestamp> / standard salt)
    try:
        cid, user, pwd = generate_initial_credentials(mac=mac, auth_profile="remotenow")
        std_rc = [None]
        std_lock = threading.Event()
        std_client = mqtt.Client(client_id=cid, clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(std_client)
        std_client.username_pw_set(username=user, password=pwd)
        std_client.on_connect = lambda c, u, f, rc: (std_rc.__setitem__(0, rc), std_lock.set())
        std_client.on_disconnect = lambda c, u, rc: std_lock.set()
        std_client.connect_async(ip, 36669, 5)
        std_client.loop_start()
        std_lock.wait(timeout=timeout)
        std_client.loop_stop()
        std_client.disconnect()
        results["standard_dynamic"]["rc"] = std_rc[0]
        results["standard_dynamic"]["supported"] = (std_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("[%s] Standard dynamic probe error: %s", ip, e)

    # 3. Middle XOR dynamic pairing (his$<timestamp ^ XOR> / standard salt)
    try:
        cid, user, pwd = generate_initial_credentials(mac=mac, auth_profile="middle")
        mid_rc = [None]
        mid_lock = threading.Event()
        mid_client = mqtt.Client(client_id=cid, clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(mid_client)
        mid_client.username_pw_set(username=user, password=pwd)
        mid_client.on_connect = lambda c, u, f, rc: (mid_rc.__setitem__(0, rc), mid_lock.set())
        mid_client.on_disconnect = lambda c, u, rc: mid_lock.set()
        mid_client.connect_async(ip, 36669, 5)
        mid_client.loop_start()
        mid_lock.wait(timeout=timeout)
        mid_client.loop_stop()
        mid_client.disconnect()
        results["middle_dynamic"]["rc"] = mid_rc[0]
        results["middle_dynamic"]["supported"] = (mid_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("[%s] Middle dynamic probe error: %s", ip, e)

    # 4. Modern XOR dynamic pairing (his$<timestamp ^ XOR> / modern salt)
    try:
        cid, user, pwd = generate_initial_credentials(mac=mac, auth_profile="modern")
        mod_rc = [None]
        mod_lock = threading.Event()
        mod_client = mqtt.Client(client_id=cid, clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(mod_client)
        mod_client.username_pw_set(username=user, password=pwd)
        mod_client.on_connect = lambda c, u, f, rc: (mod_rc.__setitem__(0, rc), mod_lock.set())
        mod_client.on_disconnect = lambda c, u, rc: mod_lock.set()
        mod_client.connect_async(ip, 36669, 5)
        mod_client.loop_start()
        mod_lock.wait(timeout=timeout)
        mod_client.loop_stop()
        mod_client.disconnect()
        results["modern_dynamic"]["rc"] = mod_rc[0]
        results["modern_dynamic"]["supported"] = (mod_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("[%s] Modern dynamic probe error: %s", ip, e)

    return results
