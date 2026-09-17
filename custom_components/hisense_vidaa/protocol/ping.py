"""Connectivity and handshake verification utilities for Hisense VIDAA TV broker."""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import threading
from typing import Any

import paho.mqtt.client as mqtt

from ..tv.fingerprint import get_device_fingerprint
from .auth import probe_tv_auth_methods, test_tv_ssl_connection

_LOGGER = logging.getLogger(__name__)

__all__ = ["ping_tv"]


def ping_tv(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    client_id: str | None = None,
    username: str | None = None,
    password: str | None = None,
    mac: str | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Quickly tests if TV broker is listening, accepting TLS, and responding to MQTT packets."""
    import ssl

    results: dict[str, Any] = {
        "tcp_port_open": False,
        "tls_handshake": False,
        "tls_version": None,
        "cipher": None,
        "mqtt_connected": False,
        "mqtt_rc": None,
        "mqtt_status": None,
        "auth_probe": None,
        "device_info": None,
        "error": None,
    }

    # 1. Test TCP port
    try:
        with socket.create_connection((ip, 36669), timeout=timeout):
            results["tcp_port_open"] = True
    except Exception as e:
        results["error"] = f"TCP connection failed (TV may be in deep sleep / off): {e}"
        return results

    # 2. Test TLS Handshake
    if certfile and keyfile:
        try:
            ssl_info = test_tv_ssl_connection(
                ip, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl, timeout=timeout
            )
            results["tls_handshake"] = ssl_info.get("connected", False)
            results["tls_version"] = ssl_info.get("tls_version")
            results["cipher"] = ssl_info.get("cipher")
        except Exception as e:
            results["error"] = f"TLS handshake failed: {e}"
            return results

    # 3. Test MQTT Broker Response (if credentials available)
    if client_id and username and password:
        try:
            conn_event = threading.Event()
            conn_rc: list[int | None] = [None]

            def on_conn(c: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
                conn_rc[0] = rc
                conn_event.set()

            c = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311)
            if certfile and keyfile and os.path.isfile(certfile) and os.path.isfile(keyfile):
                if verify_ssl and ca_cert and os.path.isfile(ca_cert):
                    c.tls_set(
                        ca_certs=ca_cert,
                        certfile=certfile,
                        keyfile=keyfile,
                        cert_reqs=ssl.CERT_REQUIRED,
                        tls_version=ssl.PROTOCOL_TLS,
                    )
                else:
                    c.tls_set(
                        ca_certs=None,
                        certfile=certfile,
                        keyfile=keyfile,
                        cert_reqs=ssl.CERT_NONE,
                        tls_version=ssl.PROTOCOL_TLS,
                    )
                c.tls_insecure_set(True)
            c.username_pw_set(username=username, password=password)
            c.on_connect = on_conn
            c.on_disconnect = lambda c, u, rc: conn_event.set()

            c.connect_async(ip, 36669, 5)
            c.loop_start()
            conn_event.wait(timeout=timeout)
            c.loop_stop()
            c.disconnect()

            results["mqtt_rc"] = conn_rc[0]
            if conn_rc[0] == 0:
                results["mqtt_connected"] = True
                results["mqtt_status"] = "Connected successfully"
            elif conn_rc[0] in (4, 5):
                results["mqtt_status"] = "Rejected: Bad username or password / Expired access token"
            elif conn_rc[0] is not None:
                results["mqtt_status"] = f"Broker rejected connection with code {conn_rc[0]}"
            else:
                results["mqtt_status"] = "Timeout waiting for broker CONNACK"
        except Exception as e:
            results["mqtt_status"] = f"MQTT test error: {e}"

    # 4. Probe auth methods
    with contextlib.suppress(Exception):
        results["auth_probe"] = probe_tv_auth_methods(
            ip, certfile=certfile, keyfile=keyfile, mac=mac, timeout=1.5
        )

    # 5. Device fingerprint
    with contextlib.suppress(Exception):
        results["device_info"] = get_device_fingerprint(ip, timeout=1.5)

    return results
