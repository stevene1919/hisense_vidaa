"""MQTT incoming message router and payload dispatcher for Hisense VIDAA TV."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)

SENSITIVE_KEYS: frozenset[str] = frozenset({
    "accesstoken",
    "refreshtoken",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "p12_password",
    "secret",
})

_SENSITIVE_JSON_PATTERN = re.compile(
    r'("(?:accesstoken|refreshtoken|access_token|refresh_token|password|p12_password|secret)"\s*:\s*)"[^"]*"',
    re.IGNORECASE,
)

__all__ = [
    "SENSITIVE_KEYS",
    "dispatch_incoming_mqtt_message",
    "mask_sensitive_data",
    "mask_sensitive_payload",
]


def mask_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive values in dictionaries and lists."""
    if isinstance(data, dict):
        return {
            k: "***" if str(k).lower() in SENSITIVE_KEYS else mask_sensitive_data(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    return data


def mask_sensitive_payload(payload: str, topic: str | None = None) -> str:
    """Mask sensitive tokens and credentials in MQTT payload strings for safe logging."""
    if not payload:
        return payload

    is_token_topic = bool(
        topic
        and any(
            topic.endswith(suffix)
            for suffix in ("/tokenissuance", "/gettoken", "tokenissuance", "gettoken")
        )
    )

    try:
        data = json.loads(payload)
        if isinstance(data, (dict, list)):
            masked_data = mask_sensitive_data(data)
            return json.dumps(masked_data)
    except Exception:
        pass

    if is_token_topic:
        return "[payload masked]"

    # Fallback regex masking for non-standard or malformed JSON payloads
    return _SENSITIVE_JSON_PATTERN.sub(r'\1"***"', payload)


def dispatch_incoming_mqtt_message(client: HisenseTvClient, topic: str, payload: str) -> None:
    """Dispatches decoded MQTT messages to appropriate client futures, state updaters, and callbacks."""
    ip = getattr(client, "ip", "Unknown")
    _LOGGER.debug("[%s] Message received: %s on topic %s", ip, mask_sensitive_payload(payload, topic), topic)

    # 1. Authentication & pairing futures
    # The PIN dialog is announced by a push to .../ui_service/data/authentication
    # (empty payload). Only this topic resolves the PIN-shown future: the
    # vidaa_app_connect acknowledgement below is a weaker signal (an already
    # authorised client gets it too, with no dialog) and must NOT stand in for
    # the challenge.
    if client._auth_future and topic == f"{client.topics.mobile}ui_service/data/authentication":
        client._safe_set_future_result(client._auth_future, payload)
        return

    # The TV's acknowledgement of a vidaa_app_connect request: {"connect_result":1}.
    # It only means the request was accepted, so it is logged and tracked on its
    # own future (the dynamic pairing cascade still falls back to it); it never
    # resolves the PIN-shown future.
    if topic == f"{client.topics.mobile}ui_service/data/vidaa_app_connect":
        _LOGGER.info(
            "[%s] TV acknowledged vidaa_app_connect (not a PIN confirmation): %s",
            ip,
            mask_sensitive_payload(payload, topic),
        )
        ack_future = getattr(client, "_connect_ack_future", None)
        if ack_future:
            client._safe_set_future_result(ack_future, payload)
        return

    # PIN dialog closed (~30s expiry or dismissed) or the remote slot is busy
    # ("another remote is pairing"). Neither carries a result, but both must
    # unblock a pending pairing wait so the flow can surface a retryable error.
    if topic in (
        f"{client.topics.mobile}ui_service/data/authenticationcodeclose",
        f"{client.topics.mobile}ui_service/data/authenticationcodetoast",
    ):
        event = "closed" if topic.endswith("/authenticationcodeclose") else "busy"
        _LOGGER.info("[%s] TV reported pairing dialog %s", ip, event)
        event_future = getattr(client, "_pairing_event_future", None)
        if event_future:
            client._safe_set_future_result(event_future, event)
        return

    if client._auth_code_future and topic == f"{client.topics.mobile}ui_service/data/authenticationcode":
        client._safe_set_future_result(client._auth_code_future, payload)
        return

    if client._token_future and topic in (
        f"{client.topics.mobile}platform_service/data/tokenissuance",
        f"{client.topics.mobile}platform_service/data/gettoken",
    ):
        client._safe_set_future_result(client._token_future, payload)
        return

    # 2. State & power updates
    if topic in (
        f"{client.topics.broadcast}ui_service/state",
        f"{client.topics.mobile}ui_service/data/gettvstate",
        f"{client.topics.mobile}ui_service/data/state",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_state_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing state payload: %s", ip, e)
        return

    if topic in (
        f"{client.topics.broadcast}platform_service/actions/volumechange",
        f"{client.topics.broadcast}ui_service/volume",
        f"{client.topics.mobile}platform_service/data/getvolume",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_volume_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing volume payload: %s", ip, e)
        return

    if topic == f"{client.topics.broadcast}platform_service/actions/tvsleep":
        client._dispatch_state_update({"statetype": "fake_sleep_0"})
        return

    if topic == f"{client.topics.mobile}ui_service/data/sourcelist":
        try:
            data = json.loads(payload)
            client._dispatch_sourcelist_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing sourcelist payload: %s", ip, e)
        return

    if topic == f"{client.topics.mobile}ui_service/data/applist":
        try:
            data = json.loads(payload)
            client._dispatch_applist_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing applist payload: %s", ip, e)
        return

    if topic in (
        f"{client.topics.mobile}platform_service/data/picturesetting",
        f"{client.topics.broadcast}platform_service/data/picturesetting",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_picture_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing picturesetting payload: %s", ip, e)
        return

    if topic in (
        f"{client.topics.mobile}platform_service/data/soundsetting",
        f"{client.topics.broadcast}platform_service/data/soundsetting",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_sound_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing soundsetting payload: %s", ip, e)
        return

    if topic == f"{client.topics.mobile}ui_service/data/capability":
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                caps = str(data).lower()
                if "notify" in caps or "toast" in caps or "showmessage" in caps or "message" in caps:
                    client.has_notifications = True
                    _LOGGER.info("[%s] TV reported support for on-screen notifications: %s", ip, data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing capability descriptor: %s", ip, e)
        return

    if topic in (
        f"{client.topics.mobile}platform_service/data/getdeviceinfo",
        f"{client.topics.mobile}platform_service/data/gettvinfo",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_device_info_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing device info payload: %s", ip, e)
        return
