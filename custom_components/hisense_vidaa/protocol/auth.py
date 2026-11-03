"""MQTT Authentication, TLS setup, PIN validation, and token refresh logic for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import ssl
import time
from typing import Any

from ..crypto import generate_initial_credentials
from .dispatcher import mask_sensitive_payload
from .topics import TopicPaths, build_topic_paths

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "apply_mqtt_tls",
    "async_perform_token_refresh",
    "async_probe_tv_auth_methods",
    "async_test_tv_ssl_connection",
    "build_mqtt_ssl_context",
    "extract_connect_rc",
    "is_token_expired",
    "perform_token_refresh",
    "probe_tv_auth_methods",
    "test_tv_ssl_connection",
]


def extract_connect_rc(err: Any) -> int:
    """Normalize CONNACK return code or ReasonCode from an MQTT exception to an integer."""
    rc = getattr(err, "rc", None)
    if rc is None:
        rc = getattr(err, "reason_code", None)
    val = getattr(rc, "value", rc)
    try:
        return int(val)
    except (TypeError, ValueError):
        return -1


def build_mqtt_ssl_context(
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    use_ssl: bool = True,
) -> ssl.SSLContext | None:
    """Constructs an SSLContext for MQTT connection without blocking network calls."""
    if not use_ssl:
        return None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    if verify_ssl and ca_cert and os.path.isfile(ca_cert):
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=ca_cert)
    else:
        context.verify_mode = ssl.CERT_NONE

    if certfile or keyfile:
        if not certfile or not os.path.isfile(certfile):
            raise FileNotFoundError(f"SSL Certificate file not found: '{certfile}'")
        if not keyfile or not os.path.isfile(keyfile):
            raise FileNotFoundError(f"SSL Private Key file not found: '{keyfile}'")
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def apply_mqtt_tls(
    client: Any,
    certfile: str | None,
    keyfile: str | None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    use_ssl: bool = True,
) -> None:
    """Applies TLS certificate configuration to an MQTT client instance."""
    if not use_ssl or not certfile or not keyfile:
        return

    if hasattr(client, "tls_set"):
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


async def async_perform_token_refresh(
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
    """Connects asynchronously using refresh_token to obtain new token credentials from TV."""
    if not refresh_token or not client_id or not username:
        _LOGGER.warning("[%s] Cannot refresh token: missing refresh_token, client_id, or username", ip)
        if out_status is not None:
            out_status["connect_rc"] = None
        return None

    paths: TopicPaths = build_topic_paths(client_id)
    loop = asyncio.get_running_loop()
    ssl_ctx = await loop.run_in_executor(
        None,
        build_mqtt_ssl_context,
        certfile,
        keyfile,
        ca_cert,
        verify_ssl,
        True,
    )

    connect_rc: int | None = None
    try:
        from aiomqtt import Client, ProtocolVersion
        from aiomqtt.exceptions import MqttConnectError, MqttError
    except ImportError:
        _LOGGER.error("aiomqtt library is not installed. Please install 'aiomqtt>=2.3.0'.")
        return None

    try:
        async with asyncio.timeout(timeout):
            async with Client(
                hostname=ip,
                port=port,
                username=username,
                password=refresh_token,
                identifier=client_id,
                tls_context=ssl_ctx,
                protocol=ProtocolVersion.V311,
                clean_session=True,
                timeout=timeout,
            ) as client:
                connect_rc = 0
                _LOGGER.debug("[%s] Refresh client connected successfully. Subscribing to token topics...", ip)
                await client.subscribe(paths.mobile + "platform_service/data/tokenissuance")
                await client.subscribe(paths.mobile + "platform_service/data/gettoken")
                payload = json.dumps({"refreshtoken": refresh_token or ""})
                await client.publish(paths.platform + "data/gettoken", payload)

                async for message in client.messages:
                    payload_str = (
                        message.payload.decode("utf-8", errors="ignore")
                        if isinstance(message.payload, (bytes, bytearray))
                        else str(message.payload)
                    )
                    _LOGGER.debug(
                        "[%s] Refresh client received message on %s: %s",
                        ip,
                        str(message.topic),
                        mask_sensitive_payload(payload_str, str(message.topic)),
                    )
                    try:
                        data = json.loads(payload_str)
                        if isinstance(data, dict) and "accesstoken" in data:
                            if out_status is not None:
                                out_status["connect_rc"] = 0
                            return data
                    except Exception as err:
                        _LOGGER.debug("[%s] Error parsing refreshed token: %s", ip, err)
    except MqttConnectError as err:
        connect_rc = extract_connect_rc(err)
        _LOGGER.warning("[%s] Refresh client connection rejected (rc: %d)", ip, connect_rc)
    except TimeoutError:
        _LOGGER.debug("[%s] Token refresh timed out after %s s", ip, timeout)
    except (OSError, MqttError) as err:
        _LOGGER.debug("[%s] TV is offline or unreachable during token refresh: %s", ip, err)
    except Exception as err:
        _LOGGER.warning("[%s] Unexpected error during refresh client connection: %s", ip, err)

    if out_status is not None:
        out_status["connect_rc"] = connect_rc

    if connect_rc is not None and connect_rc != 0:
        _LOGGER.warning("[%s] Failed to refresh token (Connect RC: %d)", ip, connect_rc)

    return None


def perform_token_refresh(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    """Synchronous wrapper for async_perform_token_refresh (CLI usage)."""
    return asyncio.run(async_perform_token_refresh(*args, **kwargs))


async def async_test_tv_ssl_connection(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Tests the TLS handshake against the TV MQTT broker on port 36669 asynchronously."""
    loop = asyncio.get_running_loop()
    context = await loop.run_in_executor(
        None,
        build_mqtt_ssl_context,
        certfile,
        keyfile,
        ca_cert,
        verify_ssl,
        True,
    )
    has_client_cert = bool(certfile and keyfile)

    _reader, writer = await asyncio.wait_for(
        asyncio.open_connection(ip, 36669, ssl=context),
        timeout=timeout,
    )
    try:
        ssl_obj = writer.get_extra_info("ssl_object")
        cipher = ssl_obj.cipher() if ssl_obj else None
        cipher_name = cipher[0] if cipher else "Unknown"
        bits = cipher[2] if cipher and len(cipher) > 2 else 0
        tls_version = ssl_obj.version() if ssl_obj else "Unknown"
        return {
            "connected": True,
            "tls_version": tls_version,
            "cipher": cipher_name,
            "bits": bits,
            "client_cert_presented": has_client_cert,
            "certfile": certfile if has_client_cert else None,
            "keyfile": keyfile if has_client_cert else None,
            "ca_cert": ca_cert if verify_ssl else None,
        }
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


def test_tv_ssl_connection(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for async_test_tv_ssl_connection."""
    return asyncio.run(async_test_tv_ssl_connection(*args, **kwargs))


async def async_probe_tv_auth_methods(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    mac: str | None = None,
    timeout: float = 2.0,
    brand: str = "his",
) -> dict[str, Any]:
    """Probes TV MQTT broker with various auth algorithms to diagnose compatibility."""
    from aiomqtt import Client, ProtocolVersion
    from aiomqtt.exceptions import MqttConnectError, MqttError

    has_cert = bool(certfile and keyfile and os.path.isfile(certfile) and os.path.isfile(keyfile))
    results: dict[str, Any] = {
        "legacy_static": {"rc": None, "supported": False},
        "standard_dynamic": {"rc": None, "supported": False},
        "middle_dynamic": {"rc": None, "supported": False},
        "modern_dynamic": {"rc": None, "supported": False},
        "client_cert_presented": has_cert,
    }

    loop = asyncio.get_running_loop()
    ssl_ctx = await loop.run_in_executor(
        None,
        build_mqtt_ssl_context,
        certfile if has_cert else None,
        keyfile if has_cert else None,
        ca_cert,
        verify_ssl,
        True,
    )

    async def _probe_single(client_id: str, u: str, p: str) -> tuple[int | None, bool]:
        try:
            async with asyncio.timeout(timeout):
                async with Client(
                    hostname=ip,
                    port=36669,
                    username=u,
                    password=p,
                    identifier=client_id,
                    tls_context=ssl_ctx,
                    protocol=ProtocolVersion.V311,
                    clean_session=True,
                    timeout=timeout,
                ):
                    return 0, True
        except MqttConnectError as err:
            rc = extract_connect_rc(err)
            return rc, False
        except TimeoutError:
            return None, False
        except (OSError, MqttError):
            return None, False
        except Exception:
            return None, False

    # 1. Legacy static ('hisenseservice')
    rc, ok = await _probe_single("hisenseservice", "hisenseservice", "multimqttservice")
    results["legacy_static"]["rc"] = rc
    results["legacy_static"]["supported"] = ok

    # 2. Standard dynamic pairing (brand$<timestamp> / standard salt)
    cid, u, p = generate_initial_credentials(mac_address=mac, auth_profile="remotenow", brand=brand)
    rc, ok = await _probe_single(cid, u, p)
    results["standard_dynamic"]["rc"] = rc
    results["standard_dynamic"]["supported"] = ok

    # 3. Middle XOR dynamic pairing (brand$<timestamp ^ XOR> / standard salt)
    cid, u, p = generate_initial_credentials(mac_address=mac, auth_profile="middle", brand=brand)
    rc, ok = await _probe_single(cid, u, p)
    results["middle_dynamic"]["rc"] = rc
    results["middle_dynamic"]["supported"] = ok

    # 4. Modern XOR dynamic pairing (brand$<timestamp ^ XOR> / modern salt)
    cid, u, p = generate_initial_credentials(mac_address=mac, auth_profile="modern", brand=brand)
    rc, ok = await _probe_single(cid, u, p)
    results["modern_dynamic"]["rc"] = rc
    results["modern_dynamic"]["supported"] = ok

    return results


def probe_tv_auth_methods(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for async_probe_tv_auth_methods."""
    return asyncio.run(async_probe_tv_auth_methods(*args, **kwargs))
