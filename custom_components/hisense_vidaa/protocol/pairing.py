"""Authentication and PIN-pairing handshake protocol for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from .dispatcher import mask_sensitive_payload

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)

# Profiles served by the pre-dynamic, static-credential session. They never
# issue a token: entering the PIN is the whole pairing and the static
# credentials (hisenseservice / multimqttservice) stay in use.
STATIC_AUTH_PROFILES = ("legacy", "static")


class PairingStatusError(Exception):
    """The TV closed the pairing dialog or reported the remote slot busy.

    Raised while waiting for a pairing reply when the TV pushes
    ``.../ui_service/data/authenticationcodeclose`` (dialog dismissed / code
    expired) or ``.../ui_service/data/authenticationcodetoast`` (the remote
    slot is occupied by another client). ``status`` is ``"closed"`` or
    ``"busy"``.
    """

    def __init__(self, status: str) -> None:
        super().__init__(f"TV pairing dialog {status}")
        self.status = status


async def async_probe_pairing_challenge(client: HisenseTvClient, timeout: float = 8.0) -> bool:
    """Opens the static session and probes whether the TV demands PIN pairing.

    On the static session ``gettvstate`` is answered by an ``authentication``
    push (empty payload) when the TV does not yet know this client; an
    already-paired client (or pre-dynamic firmware) answers normally instead,
    so this is a harmless no-op for them.

    Returns True when the challenge arrived within ``timeout``, False when the
    TV did not challenge (or could not be reached). Raises
    :class:`PairingStatusError` when the TV reports the dialog closed or the
    remote slot busy.
    """
    loop = asyncio.get_running_loop()
    client._loop = loop
    await client.async_disconnect()
    await asyncio.sleep(0.1)

    client._auth_future = loop.create_future()
    client._pairing_event_future = loop.create_future()
    try:
        try:
            await client.async_open_pairing_session(
                client.client_id, client.username, client.password, timeout=10.0
            )
        except Exception as err:
            _LOGGER.warning("[%s] Static session could not connect for pairing probe: %s", client.ip, err)
            return False
        # The session failure path may have resolved the future; reset it for the probe.
        if client._auth_future.done():
            client._auth_future = loop.create_future()

        # Mirror the push topics the pairing handshake subscribes to, plus the
        # close/toast topics so the TV's dialog events unblock the wait.
        await client.async_subscribe([
            (f"{client.topics.mobile}#", 0),
            (f"{client.topics.mobile}ui_service/data/authentication", 0),
            (f"{client.topics.mobile}ui_service/data/authenticationcode", 0),
            (f"{client.topics.mobile}ui_service/data/authenticationcodeclose", 0),
            (f"{client.topics.mobile}ui_service/data/authenticationcodetoast", 0),
        ])
        await asyncio.sleep(0.3)

        deadline = loop.time() + timeout
        next_trigger = 0.0  # publish the trigger immediately
        while loop.time() < deadline:
            if client._auth_future.done() and not client._auth_future.exception():
                return True
            if client._pairing_event_future.done():
                raise PairingStatusError(client._pairing_event_future.result())
            if loop.time() >= next_trigger:
                # gettvstate is the documented trigger; a second publish inside
                # the window re-opens the dialog if the first was missed.
                await client.async_publish(f"{client.topics.ui}actions/gettvstate", "")
                next_trigger = loop.time() + timeout / 2
            await asyncio.sleep(0.2)
        return False
    finally:
        client._auth_future = None
        client._pairing_event_future = None


async def async_start_pairing_handshake(client: HisenseTvClient) -> None:
    """Initiates pairing handshake cascade across auto/modern/middle/remotenow profiles."""
    if getattr(client, "auth_profile", "auto") in ("legacy", "static"):
        client.client_id = "hisenseservice"
        client.username = "hisenseservice"
        client.password = "multimqttservice"
        client.access_token = "multimqttservice"
        client.update_topic_paths()
        return

    profile = getattr(client, "auth_profile", "auto")
    if profile in ("modern", "vidaa_2024", "vidaa"):
        target_profile = "modern"
    elif profile in ("middle", "vidaa_15", "vidaa_middle"):
        target_profile = "middle"
    elif profile in ("remotenow", "remotenow_2018", "standard"):
        target_profile = "remotenow"
    else:
        target_profile = None

    if target_profile:
        try:
            await client._async_start_auth_internal(profile=target_profile)
            return
        except Exception as error:
            error_message = str(error)
            is_auth_reject = any(
                code in error_message
                for code in ("code 5", "code 4", "code 134", "code 135", "Not authorized")
            )
            if client.brand == "his" and is_auth_reject:
                _LOGGER.info(
                    "[%s] Default brand 'his' rejected with auth error (%s); probing candidate OEM brands...",
                    client.ip,
                    error,
                )
                for candidate_brand in ("tos", "loe", "tpv", "shp", "jvc"):
                    client.brand = candidate_brand
                    try:
                        await client._async_start_auth_internal(profile=target_profile)
                        _LOGGER.info(
                            "[%s] Successfully connected! Confirmed TV brand as '%s' (accepted profile: %s)",
                            client.ip,
                            candidate_brand,
                            target_profile,
                        )
                        return
                    except Exception:
                        continue
                client.brand = "his"
            raise
    else:  # auto
        profiles_to_try = ["modern", "middle", "remotenow"]
        if getattr(client, "ip", None):
            try:
                fingerprint = await client.async_get_device_fingerprint(1.0)
                transport_protocol = fingerprint.get("transport_protocol")
                if transport_protocol:
                    with contextlib.suppress(ValueError, TypeError):
                        protocol_version = int(transport_protocol)
                        if protocol_version >= 3290:
                            profiles_to_try = ["modern", "middle", "remotenow"]
                        elif 3000 <= protocol_version < 3290:
                            profiles_to_try = ["middle", "modern", "remotenow"]
                        else:
                            profiles_to_try = ["remotenow", "middle", "modern"]
            except Exception as error:
                _LOGGER.debug("[%s] Could not determine transport_protocol before auth: %s", client.ip, error)

        last_error = None
        for candidate_profile in profiles_to_try:
            try:
                _LOGGER.debug("[%s] Attempting pairing auth with profile: %s", client.ip, candidate_profile)
                await client._async_start_auth_internal(profile=candidate_profile)
                client.auth_profile = candidate_profile
                return
            except Exception as error:
                last_error = error
                error_message = str(error)
                if (
                    "code 5" in error_message
                    or "code 4" in error_message
                    or "code 134" in error_message
                    or "code 135" in error_message
                    or "Not authorized" in error_message
                ):
                    _LOGGER.info(
                        "[%s] Auth profile %s rejected by TV (%s), falling back...",
                        client.ip,
                        candidate_profile,
                        error_message,
                    )
                    continue
                raise
        if last_error:
            error_message = str(last_error)
            is_auth_reject = any(
                code in error_message
                for code in ("code 5", "code 4", "code 134", "code 135", "Not authorized")
            )
            if client.brand == "his" and is_auth_reject:
                _LOGGER.info(
                    "[%s] Default brand 'his' rejected with auth error (%s); probing candidate OEM brands...",
                    client.ip,
                    last_error,
                )
                candidate_profiles = [p for p in profiles_to_try if p != "remotenow"]
                for candidate_brand in ("tos", "loe", "tpv", "shp", "jvc"):
                    client.brand = candidate_brand
                    for candidate_profile in candidate_profiles:
                        try:
                            _LOGGER.debug(
                                "[%s] Probing OEM brand '%s' with profile '%s'...",
                                client.ip,
                                candidate_brand,
                                candidate_profile,
                            )
                            await client._async_start_auth_internal(profile=candidate_profile)
                            client.auth_profile = candidate_profile
                            _LOGGER.info(
                                "[%s] Successfully connected! Confirmed TV brand as '%s' (accepted profile: %s)",
                                client.ip,
                                candidate_brand,
                                candidate_profile,
                            )
                            return
                        except Exception as brand_err:
                            err_msg = str(brand_err)
                            if any(
                                code in err_msg
                                for code in ("code 5", "code 4", "code 134", "code 135", "Not authorized")
                            ):
                                continue
                            break
                client.brand = "his"
            raise last_error


async def _async_execute_pairing_attempt(
    client: HisenseTvClient, profile: str = "modern", use_new_auth: bool | None = None
) -> None:
    loop = asyncio.get_running_loop()
    client._loop = loop
    await client.async_disconnect()
    await asyncio.sleep(0.2)
    tv_timestamp = await client.upnp.async_get_tv_timestamp(1.5)
    client.derive_pairing_credentials(
        use_new_auth=use_new_auth, auth_profile=profile, timestamp=tv_timestamp
    )

    # Raises the CONNACK rejection immediately so the profile cascade can fall back.
    await client.async_open_pairing_session(
        client.client_id, client.username, client.password, timeout=10.0
    )
    client._auth_future = loop.create_future()
    client._connect_ack_future = loop.create_future()

    await client.async_subscribe([
        (f"{client.topics.ui}actions/vidaa_app_connect", 0),
        (f"{client.topics.mobile}#", 0),
        (f"{client.topics.mobile}ui_service/data/authentication", 0),
        (f"{client.topics.mobile}ui_service/data/authenticationcode", 0),
        (f"{client.topics.mobile}ui_service/data/vidaa_app_connect", 0),
        (f"{client.topics.mobile}platform_service/data/tokenissuance", 0),
    ])

    await asyncio.sleep(0.5)

    for attempt in range(3):
        await client.async_publish(
            f"{client.topics.ui}actions/vidaa_app_connect",
            '{"app_version":2,"connect_result":0,"device_type":"Mobile App"}',
        )
        try:
            await asyncio.wait_for(asyncio.shield(client._auth_future), timeout=4.0)
            break
        except TimeoutError:
            if client._connect_ack_future.done():
                # The TV accepted the request but never announced a PIN dialog.
                # Some firmware does this even with a PIN on screen; the ACK is
                # weaker evidence than the authentication push but is all we get.
                _LOGGER.info(
                    "[%s] TV acknowledged vidaa_app_connect but sent no PIN notification", client.ip
                )
                break
            if attempt < 2 and not client._auth_future.done():
                _LOGGER.debug("[%s] No response to vidaa_app_connect on attempt %d, retrying...", client.ip, attempt + 1)
                await asyncio.sleep(0.5)
            else:
                await client.async_disconnect()
                raise Exception("TV authentication request timed out (TV did not show PIN)")
    client._auth_future = None
    client._connect_ack_future = None


async def async_submit_pin_code(client: HisenseTvClient, pin_code: str) -> dict[str, Any]:
    """Submits the PIN code entered by the user and retrieves token pair from TV."""
    loop = asyncio.get_running_loop()
    client._loop = loop
    client._auth_code_future = loop.create_future()
    client._pairing_event_future = loop.create_future()

    if not client.mqtt_client:
        raise Exception("MQTT client not initialized")

    await client.async_publish(
        f"{client.topics.ui}actions/authenticationcode",
        json.dumps({"authNum": int(pin_code)}),
    )

    try:
        # Wait for the PIN result, but unblock early if the TV closes the dialog
        # or reports the remote slot busy instead of answering.
        done, _pending = await asyncio.wait(
            {client._auth_code_future, client._pairing_event_future},
            timeout=15,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if client._pairing_event_future in done:
            raise PairingStatusError(client._pairing_event_future.result())
        if client._auth_code_future not in done:
            raise Exception("Timeout waiting for PIN validation")
        payload_str = client._auth_code_future.result()
        _LOGGER.debug("[%s] Received PIN response payload: %s", client.ip, mask_sensitive_payload(payload_str))
        payload = json.loads(payload_str)
        if payload.get("result") != 1:
            _LOGGER.warning(
                "[%s] PIN validation rejected with payload: %s",
                client.ip,
                mask_sensitive_payload(payload_str),
            )
            raise Exception(f"Incorrect PIN code (TV response: {mask_sensitive_payload(payload_str)})")
    finally:
        client._auth_code_future = None
        client._pairing_event_future = None

    if getattr(client, "auth_profile", "auto") in STATIC_AUTH_PROFILES:
        # Pre-dynamic (static) firmware puts no token behind the PIN: accepting
        # the code IS the pairing, and the static credentials stay in use.
        _LOGGER.info("[%s] PIN accepted on static session; no token exchange needed", client.ip)
        return {}

    client._token_future = loop.create_future()
    await client.async_publish(f"{client.topics.platform}data/gettoken", '{"refreshtoken": ""}')
    await client.async_publish(f"{client.topics.ui}actions/authenticationcodeclose")

    try:
        token_payload_str = await asyncio.wait_for(client._token_future, timeout=15)
        token_data = json.loads(token_payload_str)

        client.access_token = str(token_data.get("accesstoken", ""))
        client.access_token_time = int(token_data.get("accesstoken_time") or time.time())
        client.access_token_duration = int(token_data.get("accesstoken_duration_day") or 30)
        client.refresh_token = str(token_data.get("refreshtoken", ""))
        client.refresh_token_time = int(token_data.get("refreshtoken_time") or time.time())
        client.refresh_token_duration = int(token_data.get("refreshtoken_duration_day") or 30)

        _LOGGER.info(
            "[%s] Pairing successful! Received access_token (valid %d days) and refresh_token (valid %d days)",
            client.ip,
            client.access_token_duration,
            client.refresh_token_duration,
        )
        return token_data
    except TimeoutError:
        raise Exception("Timeout waiting for token issuance from TV")
    finally:
        client._token_future = None
