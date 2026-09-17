"""Authentication and PIN-pairing handshake protocol for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

try:
    from ..discovery import get_tv_timestamp
except (ImportError, ValueError):
    from discovery import get_tv_timestamp

_LOGGER = logging.getLogger(__name__)


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
                _LOGGER.debug("Could not determine transport_protocol before auth: %s", e)

        last_err = None
        for p in profiles_to_try:
            try:
                _LOGGER.debug("Attempting pairing auth with profile: %s", p)
                await client._async_start_auth_internal(profile=p)
                client.auth_profile = p
                return
            except Exception as e:
                last_err = e
                err_msg = str(e)
                if "code 5" in err_msg or "code 4" in err_msg or "Not authorized" in err_msg:
                    _LOGGER.info("Auth profile %s rejected by TV (%s), falling back...", p, err_msg)
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
            if attempt < 2 and not client._auth_future.done():
                _LOGGER.debug("No response to vidaa_app_connect on attempt %d, retrying...", attempt + 1)
                await asyncio.sleep(0.5)
            else:
                client.disconnect()
                raise Exception("TV authentication request timed out (TV did not show PIN)")
    client._auth_future = None


async def async_submit_pin_code(client: Any, pin_code: str) -> dict[str, Any]:
    """Submits the PIN code entered by the user and retrieves token pair from TV."""
    loop = asyncio.get_running_loop()
    client._loop = loop
    client._auth_code_future = loop.create_future()

    if not client.mqtt_client:
        raise Exception("MQTT client not initialized")

    client.mqtt_client.publish(
        client.topicTVUIBasepath + "actions/authenticationcode",
        json.dumps({"authNum": int(pin_code)}),
    )

    try:
        payload_str = await asyncio.wait_for(client._auth_code_future, timeout=15)
        _LOGGER.debug("Received PIN response payload: %s", payload_str)
        payload = json.loads(payload_str)
        if payload.get("result") != 1:
            _LOGGER.error("PIN validation rejected with payload: %s", payload_str)
            raise Exception(f"Incorrect PIN code (TV response: {payload_str})")
    except TimeoutError:
        raise Exception("Timeout waiting for PIN validation")
    finally:
        client._auth_code_future = None

    client._token_future = loop.create_future()
    client.mqtt_client.publish(client.topicTVPSBasepath + "data/gettoken", '{"refreshtoken": ""}')
    client.mqtt_client.publish(client.topicTVUIBasepath + "actions/authenticationcodeclose")

    try:
        token_payload_str = await asyncio.wait_for(client._token_future, timeout=15)
        token_data = json.loads(token_payload_str)

        client.access_token = token_data["accesstoken"]
        client.access_token_time = int(token_data["accesstoken_time"])
        client.access_token_duration = int(token_data["accesstoken_duration_day"])
        client.refresh_token = token_data["refreshtoken"]
        client.refresh_token_time = int(token_data["refreshtoken_time"])
        client.refresh_token_duration = int(token_data["refreshtoken_duration_day"])

        _LOGGER.info(
            "Pairing successful! Received access_token (valid %d days) and refresh_token (valid %d days)",
            client.access_token_duration,
            client.refresh_token_duration,
        )
        return token_data
    except TimeoutError:
        raise Exception("Timeout waiting for token issuance from TV")
    finally:
        client._token_future = None
