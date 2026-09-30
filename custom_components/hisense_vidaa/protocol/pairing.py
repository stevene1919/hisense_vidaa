"""Authentication and PIN-pairing handshake protocol for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any

from ..tv.fingerprint import get_tv_timestamp

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


async def async_probe_pairing_challenge(client: Any, timeout: float = 8.0) -> bool:
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
    await loop.run_in_executor(None, client.disconnect)
    await asyncio.sleep(0.1)

    client._auth_future = loop.create_future()
    client._pairing_event_future = loop.create_future()
    try:
        client.mqtt_client = await loop.run_in_executor(
            None, client.create_mqtt_client, client.client_id, client.username, client.password
        )
        client.mqtt_client.reconnect_delay_set(min_delay=30, max_delay=60)
        client.mqtt_client.connect_async(client.ip, 36669, 60)
        client.mqtt_client.loop_start()

        # Wait up to ~10s for the connection (mirrors the dynamic handshake).
        for _ in range(50):
            if client.connected or client._auth_future.done():
                break
            await asyncio.sleep(0.2)

        if not client.connected:
            if client._auth_future.done() and not client._auth_future.cancelled():
                _LOGGER.warning(
                    "[%s] Static session could not connect for pairing probe: %s",
                    client.ip, client._auth_future.exception(),
                )
            return False

        # Mirror the push topics the pairing handshake subscribes to, plus the
        # close/toast topics so the TV's dialog events unblock the wait.
        client.mqtt_client.subscribe([
            (client.topicMobiBasepath + "#", 0),
            (client.topicMobiBasepath + "ui_service/data/authentication", 0),
            (client.topicMobiBasepath + "ui_service/data/authenticationcode", 0),
            (client.topicMobiBasepath + "ui_service/data/authenticationcodeclose", 0),
            (client.topicMobiBasepath + "ui_service/data/authenticationcodetoast", 0),
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
                client.mqtt_client.publish(client.topicTVUIBasepath + "actions/gettvstate", "")
                next_trigger = loop.time() + timeout / 2
            await asyncio.sleep(0.2)
        return False
    finally:
        client._auth_future = None
        client._pairing_event_future = None


async def async_start_pairing_handshake(client: Any) -> None:
    """Initiates pairing handshake cascade across auto/modern/middle/remotenow profiles."""
    if getattr(client, "auth_profile", "auto") in ("legacy", "static"):
        client.client_id = "hisenseservice"
        client.username = "hisenseservice"
        client.password = "multimqttservice"
        client.access_token = "multimqttservice"
        client.define_topic_paths()
        return

    profile = getattr(client, "auth_profile", "auto")
    if profile in ("modern", "vidaa_2024", "vidaa"):
        await client._async_start_auth_internal(profile="modern")
    elif profile in ("middle", "vidaa_15", "vidaa_middle"):
        await client._async_start_auth_internal(profile="middle")
    elif profile in ("remotenow", "remotenow_2018", "standard"):
        await client._async_start_auth_internal(profile="remotenow")
    else:  # auto
        profiles_to_try = ["modern", "middle", "remotenow"]
        if getattr(client, "ip", None):
            try:
                loop = asyncio.get_running_loop()
                fp = await loop.run_in_executor(None, client.get_device_fingerprint, 1.0)
                tp = fp.get("transport_protocol")
                if tp:
                    with contextlib.suppress(ValueError, TypeError):
                        tp_int = int(tp)
                        if tp_int >= 3290:
                            profiles_to_try = ["modern", "middle", "remotenow"]
                        elif 3000 <= tp_int < 3290:
                            profiles_to_try = ["middle", "modern", "remotenow"]
                        else:
                            profiles_to_try = ["remotenow", "middle", "modern"]
            except Exception as e:
                _LOGGER.debug("[%s] Could not determine transport_protocol before auth: %s", client.ip, e)

        last_err = None
        for p in profiles_to_try:
            try:
                _LOGGER.debug("[%s] Attempting pairing auth with profile: %s", client.ip, p)
                await client._async_start_auth_internal(profile=p)
                client.auth_profile = p
                return
            except Exception as e:
                last_err = e
                err_msg = str(e)
                if "code 5" in err_msg or "code 4" in err_msg or "Not authorized" in err_msg:
                    _LOGGER.info("[%s] Auth profile %s rejected by TV (%s), falling back...", client.ip, p, err_msg)
                    continue
                raise
        if last_err:
            raise last_err


async def _async_execute_pairing_attempt(
    client: Any, profile: str = "modern", use_new_auth: bool | None = None
) -> None:
    loop = asyncio.get_running_loop()
    client._loop = loop
    client.disconnect()
    await asyncio.sleep(0.2)
    tv_ts = await loop.run_in_executor(None, get_tv_timestamp, client.ip, 1.5)
    client.generate_initial_creds(
        use_new_auth=use_new_auth, auth_profile=profile, timestamp=tv_ts
    )
    client.mqtt_client = await loop.run_in_executor(
        None, client.create_mqtt_client, client.client_id, client.username, client.password
    )
    client.mqtt_client.reconnect_delay_set(min_delay=30, max_delay=60)

    client._auth_future = loop.create_future()
    client._connect_ack_future = loop.create_future()
    client.mqtt_client.connect_async(client.ip, 36669, 60)
    client.mqtt_client.loop_start()

    # Wait up to 10 seconds for connection
    for _ in range(50):
        if client.connected:
            break
        if client._auth_future.done() and client._auth_future.exception():
            client.disconnect()
            raise client._auth_future.exception()
        await asyncio.sleep(0.2)

    if not client.connected:
        client.disconnect()
        raise Exception("Cannot connect to TV MQTT Broker (connection timeout)")

    client.mqtt_client.subscribe([
        (client.topicTVUIBasepath + "actions/vidaa_app_connect", 0),
        (client.topicMobiBasepath + "#", 0),
        (client.topicMobiBasepath + "ui_service/data/authentication", 0),
        (client.topicMobiBasepath + "ui_service/data/authenticationcode", 0),
        (client.topicMobiBasepath + "ui_service/data/vidaa_app_connect", 0),
        (client.topicMobiBasepath + "platform_service/data/tokenissuance", 0),
    ])

    await asyncio.sleep(0.5)

    for attempt in range(3):
        client.mqtt_client.publish(
            client.topicTVUIBasepath + "actions/vidaa_app_connect",
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
                client.disconnect()
                raise Exception("TV authentication request timed out (TV did not show PIN)")
    client._auth_future = None
    client._connect_ack_future = None


async def async_submit_pin_code(client: Any, pin_code: str) -> dict[str, Any]:
    """Submits the PIN code entered by the user and retrieves token pair from TV."""
    loop = asyncio.get_running_loop()
    client._loop = loop
    client._auth_code_future = loop.create_future()
    client._pairing_event_future = loop.create_future()

    if not client.mqtt_client:
        raise Exception("MQTT client not initialized")

    client.mqtt_client.publish(
        client.topicTVUIBasepath + "actions/authenticationcode",
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
        _LOGGER.debug("[%s] Received PIN response payload: %s", client.ip, payload_str)
        payload = json.loads(payload_str)
        if payload.get("result") != 1:
            _LOGGER.warning("[%s] PIN validation rejected with payload: %s", client.ip, payload_str)
            raise Exception(f"Incorrect PIN code (TV response: {payload_str})")
    finally:
        client._auth_code_future = None
        client._pairing_event_future = None

    if getattr(client, "auth_profile", "auto") in STATIC_AUTH_PROFILES:
        # Pre-dynamic (static) firmware puts no token behind the PIN: accepting
        # the code IS the pairing, and the static credentials stay in use.
        _LOGGER.info("[%s] PIN accepted on static session; no token exchange needed", client.ip)
        return {}

    client._token_future = loop.create_future()
    client.mqtt_client.publish(client.topicTVPSBasepath + "data/gettoken", '{"refreshtoken": ""}')
    client.mqtt_client.publish(client.topicTVUIBasepath + "actions/authenticationcodeclose")

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
