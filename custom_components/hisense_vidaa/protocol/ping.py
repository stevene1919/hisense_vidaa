"""Connectivity and handshake verification utilities for Hisense VIDAA TV broker."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import TYPE_CHECKING, Any

from .auth import (
    async_probe_tv_auth_methods,
    async_test_tv_ssl_connection,
    build_mqtt_ssl_context,
    extract_connect_rc,
)

if TYPE_CHECKING:
    from .upnp import HisenseUpnpClient

_LOGGER = logging.getLogger(__name__)

__all__ = ["async_ping_tv", "ping_tv"]


async def async_ping_tv(
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
    upnp: HisenseUpnpClient | None = None,
    brand: str = "his",
) -> dict[str, Any]:
    """Quickly tests if TV broker is listening, accepting TLS, and responding to MQTT packets."""
    results: dict[str, Any] = {
        "tcp_port_open": False,
        "tls_handshake": False,
        "tls_version": None,
        "cipher": None,
        "client_cert_presented": False,
        "certfile": None,
        "keyfile": None,
        "mqtt_connected": False,
        "mqtt_rc": None,
        "mqtt_status": None,
        "auth_probe": None,
        "device_info": None,
        "error": None,
    }

    # 1. Test TCP port
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, 36669), timeout=timeout)
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        results["tcp_port_open"] = True
    except Exception as e:
        results["error"] = f"TCP connection failed (TV may be in deep sleep / off): {e}"
        return results

    loop = asyncio.get_running_loop()
    valid_cert, valid_key = await loop.run_in_executor(
        None,
        lambda: (
            certfile if (certfile and os.path.isfile(certfile)) else None,
            keyfile if (keyfile and os.path.isfile(keyfile)) else None,
        ),
    )

    # 2. Test TLS Handshake
    try:
        ssl_info = await async_test_tv_ssl_connection(
            ip, certfile=valid_cert, keyfile=valid_key, ca_cert=ca_cert, verify_ssl=verify_ssl, timeout=timeout
        )
        results["tls_handshake"] = ssl_info.get("connected", False)
        results["tls_version"] = ssl_info.get("tls_version")
        results["cipher"] = ssl_info.get("cipher")
        results["client_cert_presented"] = ssl_info.get("client_cert_presented", False)
        results["certfile"] = ssl_info.get("certfile")
        results["keyfile"] = ssl_info.get("keyfile")
    except Exception as e:
        results["error"] = f"TLS handshake failed: {e}"
        return results

    # 3. Test MQTT Broker Response (if credentials available)
    if client_id and username and password:
        from aiomqtt import Client, MqttError, ProtocolVersion
        from aiomqtt.exceptions import MqttConnectError

        conn_rc: int | None = None
        try:
            ssl_ctx = await loop.run_in_executor(
                None, build_mqtt_ssl_context, valid_cert, valid_key, ca_cert, verify_ssl, True
            )
            try:
                async with asyncio.timeout(timeout):
                    async with Client(
                        hostname=ip,
                        port=36669,
                        username=username,
                        password=password,
                        identifier=client_id,
                        tls_context=ssl_ctx,
                        protocol=ProtocolVersion.V311,
                        clean_session=True,
                        timeout=timeout,
                    ):
                        conn_rc = 0
            except MqttConnectError as err:
                conn_rc = extract_connect_rc(err)
            except (TimeoutError, MqttError, OSError):
                conn_rc = None

            results["mqtt_rc"] = conn_rc
            if conn_rc == 0:
                results["mqtt_connected"] = True
                results["mqtt_status"] = "Connected successfully"
            elif conn_rc in (4, 5, 134, 135):
                results["mqtt_status"] = "Rejected: Bad username or password / Expired access token"
            elif conn_rc is not None:
                results["mqtt_status"] = f"Broker rejected connection with code {conn_rc}"
            else:
                results["mqtt_status"] = "Timeout waiting for broker CONNACK"
        except Exception as e:
            results["mqtt_status"] = f"MQTT test error: {e}"

    # 4. Probe auth methods
    with contextlib.suppress(Exception):
        results["auth_probe"] = await async_probe_tv_auth_methods(
            ip,
            certfile=valid_cert,
            keyfile=valid_key,
            mac=mac,
            timeout=1.5,
            brand=brand,
        )

    # 5. Device fingerprint
    with contextlib.suppress(Exception):
        if upnp is not None:
            results["device_info"] = await upnp.async_get_device_fingerprint(timeout=1.5)
        else:
            from ..tv.fingerprint import get_device_fingerprint

            results["device_info"] = await loop.run_in_executor(None, get_device_fingerprint, ip, 1.5)

    return results


def ping_tv(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Synchronous (CLI) wrapper for async_ping_tv."""
    return asyncio.run(async_ping_tv(*args, **kwargs))
