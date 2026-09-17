"""MQTT Authentication, TLS setup, PIN validation, and token refresh logic for Hisense VIDAA TV."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import ssl
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

try:
    from .topics import TopicPaths, build_topic_paths
except (ImportError, ValueError):
    from protocol.topics import TopicPaths, build_topic_paths

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

        start = time.time()
        while not lock.is_set() and time.time() - start < timeout:
            time.sleep(0.1)
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
