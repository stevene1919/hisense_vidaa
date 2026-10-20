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
import warnings
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
    clock_offset: int = 0,
) -> bool:
    """Checks if access token is expired or within margin of expiration."""
    if not access_token_time or not access_token_duration_day:
        return False
    now = int(time.time()) + clock_offset
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
    out_status: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Connects synchronously using refresh_token to obtain new token credentials from TV."""
    if not refresh_token or not client_id or not username:
        _LOGGER.warning("[%s] Cannot refresh token: missing refresh_token, client_id, or username", ip)
        if out_status is not None:
            out_status["connect_rc"] = None
        return None

    paths: TopicPaths = build_topic_paths(client_id)
    client_kwargs: dict[str, Any] = {
        "client_id": client_id,
        "clean_session": True,
        "protocol": mqtt.MQTTv311,
        "transport": "tcp",
    }
    if hasattr(mqtt, "CallbackAPIVersion"):
        client_kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION2

    client = mqtt.Client(**client_kwargs)
    apply_mqtt_tls(
        client,
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        verify_ssl=verify_ssl,
        use_ssl=True,
    )
    client.username_pw_set(username=username, password=refresh_token)

    refresh_completion_event = threading.Event()
    updated_data: dict[str, Any] = {}
    connect_return_code = [None]

    def on_refresh_connect(
        client_instance: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, *args: Any
    ) -> None:
        code = getattr(reason_code, "value", reason_code)
        try:
            code = int(code)
        except (ValueError, TypeError):
            code = -1
        connect_return_code[0] = code
        if code == 0:
            _LOGGER.debug("[%s] Refresh client connected successfully. Subscribing to token topics...", ip)
            # Some VIDAA firmwares deny wildcard subscriptions (SUBACK 128): subscribe to exact topics
            client_instance.subscribe([
                (paths.mobile + "platform_service/data/tokenissuance", 0),
                (paths.mobile + "platform_service/data/gettoken", 0),
            ])
            payload = json.dumps({"refreshtoken": refresh_token or ""})
            client_instance.publish(paths.platform + "data/gettoken", payload)
        else:
            _LOGGER.warning("[%s] Refresh client connection rejected (rc: %d)", ip, code)
            refresh_completion_event.set()

    def on_refresh_subscribe(
        client_instance: mqtt.Client, userdata: Any, message_id: int, *args: Any
    ) -> None:
        payload = json.dumps({"refreshtoken": refresh_token or ""})
        client_instance.publish(paths.platform + "data/gettoken", payload)

    def on_token_message(client_instance: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        nonlocal updated_data
        try:
            payload_str = message.payload.decode("utf-8", errors="ignore")
            _LOGGER.debug("[%s] Refresh client received message on %s: %s", ip, message.topic, payload_str)
            data = json.loads(payload_str)
            if isinstance(data, dict) and "accesstoken" in data:
                updated_data = data
                refresh_completion_event.set()
        except Exception as error:
            _LOGGER.debug("[%s] Error parsing refreshed token: %s", ip, error)

    client.on_connect = on_refresh_connect
    client.on_subscribe = on_refresh_subscribe
    client.on_message = on_token_message
    client.on_disconnect = lambda client_instance, userdata, *args: _LOGGER.debug(
        "[%s] Refresh client disconnected: %s", ip, args
    )

    try:
        client.connect(ip, port, 60)
        client.loop_start()
        refresh_completion_event.wait(timeout=timeout)
    except (OSError, TimeoutError) as error:
        _LOGGER.debug("[%s] TV is offline or unreachable during token refresh: %s", ip, error)
    except Exception as error:
        _LOGGER.warning("[%s] Unexpected error during refresh client connection: %s", ip, error)
    finally:
        with contextlib.suppress(Exception):
            client.loop_stop()
            client.disconnect()

    if out_status is not None:
        out_status["connect_rc"] = connect_return_code[0]

    if updated_data:
        return updated_data

    if connect_return_code[0] is not None:
        _LOGGER.warning("[%s] Failed to refresh token (Connect RC: %d)", ip, connect_return_code[0])

    return None


def test_tv_ssl_connection(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Tests the TLS handshake against the TV MQTT broker on port 36669."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    if verify_ssl and ca_cert and os.path.isfile(ca_cert):
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=ca_cert)
    else:
        context.verify_mode = ssl.CERT_NONE

    has_client_cert = False
    if certfile or keyfile:
        if not certfile or not os.path.isfile(certfile):
            raise FileNotFoundError(f"SSL Certificate file not found: '{certfile}'")
        if not keyfile or not os.path.isfile(keyfile):
            raise FileNotFoundError(f"SSL Private Key file not found: '{keyfile}'")
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        has_client_cert = True

    with (
        socket.create_connection((ip, 36669), timeout=timeout) as sock,
        context.wrap_socket(sock) as ssock,
    ):
        cipher = ssock.cipher()
        cipher_name = cipher[0] if cipher else "Unknown"
        bits = cipher[2] if cipher and len(cipher) > 2 else 0
        return {
            "connected": True,
            "tls_version": ssock.version(),
            "cipher": cipher_name,
            "bits": bits,
            "client_cert_presented": has_client_cert,
            "certfile": certfile if has_client_cert else None,
            "keyfile": keyfile if has_client_cert else None,
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
    has_cert = bool(certfile and keyfile and os.path.isfile(certfile) and os.path.isfile(keyfile))
    results = {
        "legacy_static": {"rc": None, "supported": False},
        "standard_dynamic": {"rc": None, "supported": False},
        "middle_dynamic": {"rc": None, "supported": False},
        "modern_dynamic": {"rc": None, "supported": False},
        "client_cert_presented": has_cert,
    }

    def _setup_tls(c: mqtt.Client) -> None:
        if has_cert:
            if verify_ssl and ca_cert and os.path.isfile(ca_cert):
                c.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
            else:
                c.tls_set(ca_certs=None, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        else:
            c.tls_set(cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        c.tls_insecure_set(True)

    def _create_probe_client(client_id: str) -> mqtt.Client:
        kwargs: dict[str, Any] = {
            "client_id": client_id,
            "clean_session": True,
            "protocol": mqtt.MQTTv311,
        }
        if hasattr(mqtt, "CallbackAPIVersion"):
            kwargs["callback_api_version"] = mqtt.CallbackAPIVersion.VERSION1
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return mqtt.Client(**kwargs)

    # 1. Legacy static ('hisenseservice')
    try:
        legacy_return_code = [None]
        legacy_completion_event = threading.Event()
        legacy_client = _create_probe_client("hisenseservice")
        _setup_tls(legacy_client)
        legacy_client.username_pw_set(username="hisenseservice", password="multimqttservice")
        legacy_client.on_connect = lambda client_obj, userdata, flags, rc: (
            legacy_return_code.__setitem__(0, rc),
            legacy_completion_event.set(),
        )
        legacy_client.on_disconnect = lambda client_obj, userdata, rc: legacy_completion_event.set()
        legacy_client.connect_async(ip, 36669, 5)
        legacy_client.loop_start()
        legacy_completion_event.wait(timeout=timeout)
        legacy_client.loop_stop()
        legacy_client.disconnect()
        results["legacy_static"]["rc"] = legacy_return_code[0]
        results["legacy_static"]["supported"] = (legacy_return_code[0] == 0)
    except Exception as error:
        _LOGGER.debug("[%s] Legacy static probe error: %s", ip, error)

    # 2. Standard dynamic pairing (his$<timestamp> / standard salt)
    try:
        client_id, username, password = generate_initial_credentials(mac_address=mac, auth_profile="remotenow")
        standard_return_code = [None]
        standard_completion_event = threading.Event()
        standard_client = _create_probe_client(client_id)
        _setup_tls(standard_client)
        standard_client.username_pw_set(username=username, password=password)
        standard_client.on_connect = lambda client_obj, userdata, flags, rc: (
            standard_return_code.__setitem__(0, rc),
            standard_completion_event.set(),
        )
        standard_client.on_disconnect = lambda client_obj, userdata, rc: standard_completion_event.set()
        standard_client.connect_async(ip, 36669, 5)
        standard_client.loop_start()
        standard_completion_event.wait(timeout=timeout)
        standard_client.loop_stop()
        standard_client.disconnect()
        results["standard_dynamic"]["rc"] = standard_return_code[0]
        results["standard_dynamic"]["supported"] = (standard_return_code[0] == 0)
    except Exception as error:
        _LOGGER.debug("[%s] Standard dynamic probe error: %s", ip, error)

    # 3. Middle XOR dynamic pairing (his$<timestamp ^ XOR> / standard salt)
    try:
        client_id, username, password = generate_initial_credentials(mac_address=mac, auth_profile="middle")
        middle_return_code = [None]
        middle_completion_event = threading.Event()
        middle_client = _create_probe_client(client_id)
        _setup_tls(middle_client)
        middle_client.username_pw_set(username=username, password=password)
        middle_client.on_connect = lambda client_obj, userdata, flags, rc: (
            middle_return_code.__setitem__(0, rc),
            middle_completion_event.set(),
        )
        middle_client.on_disconnect = lambda client_obj, userdata, rc: middle_completion_event.set()
        middle_client.connect_async(ip, 36669, 5)
        middle_client.loop_start()
        middle_completion_event.wait(timeout=timeout)
        middle_client.loop_stop()
        middle_client.disconnect()
        results["middle_dynamic"]["rc"] = middle_return_code[0]
        results["middle_dynamic"]["supported"] = (middle_return_code[0] == 0)
    except Exception as error:
        _LOGGER.debug("[%s] Middle dynamic probe error: %s", ip, error)

    # 4. Modern XOR dynamic pairing (his$<timestamp ^ XOR> / modern salt)
    try:
        client_id, username, password = generate_initial_credentials(mac_address=mac, auth_profile="modern")
        modern_return_code = [None]
        modern_completion_event = threading.Event()
        modern_client = _create_probe_client(client_id)
        _setup_tls(modern_client)
        modern_client.username_pw_set(username=username, password=password)
        modern_client.on_connect = lambda client_obj, userdata, flags, rc: (
            modern_return_code.__setitem__(0, rc),
            modern_completion_event.set(),
        )
        modern_client.on_disconnect = lambda client_obj, userdata, rc: modern_completion_event.set()
        modern_client.connect_async(ip, 36669, 5)
        modern_client.loop_start()
        modern_completion_event.wait(timeout=timeout)
        modern_client.loop_stop()
        modern_client.disconnect()
        results["modern_dynamic"]["rc"] = modern_return_code[0]
        results["modern_dynamic"]["supported"] = (modern_return_code[0] == 0)
    except Exception as error:
        _LOGGER.debug("[%s] Modern dynamic probe error: %s", ip, error)

    return results
