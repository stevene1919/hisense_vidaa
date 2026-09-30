"""MQTT incoming message router and payload dispatcher for Hisense VIDAA TV."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)

__all__ = ["dispatch_incoming_mqtt_message"]


def dispatch_incoming_mqtt_message(client: HisenseTvClient, topic: str, payload: str) -> None:
    """Dispatches decoded MQTT messages to appropriate client futures, state updaters, and callbacks."""
    ip = getattr(client, "ip", "Unknown")
    _LOGGER.debug("[%s] Message received: %s on topic %s", ip, payload, topic)

    # 1. Authentication & pairing futures
    # The PIN dialog is announced by a push to .../ui_service/data/authentication
    # (empty payload). Only this topic resolves the PIN-shown future: the
    # vidaa_app_connect acknowledgement below is a weaker signal (an already
    # authorised client gets it too, with no dialog) and must NOT stand in for
    # the challenge.
    if client._auth_future and topic == client.topicMobiBasepath + "ui_service/data/authentication":
        client._safe_set_future_result(client._auth_future, payload)
        return

    # The TV's acknowledgement of a vidaa_app_connect request: {"connect_result":1}.
    # It only means the request was accepted, so it is logged and tracked on its
    # own future (the dynamic pairing cascade still falls back to it); it never
    # resolves the PIN-shown future.
    if topic == client.topicMobiBasepath + "ui_service/data/vidaa_app_connect":
        _LOGGER.info("[%s] TV acknowledged vidaa_app_connect (not a PIN confirmation): %s", ip, payload)
        ack_future = getattr(client, "_connect_ack_future", None)
        if ack_future:
            client._safe_set_future_result(ack_future, payload)
        return

    # PIN dialog closed (~30s expiry or dismissed) or the remote slot is busy
    # ("another remote is pairing"). Neither carries a result, but both must
    # unblock a pending pairing wait so the flow can surface a retryable error.
    if topic in (
        client.topicMobiBasepath + "ui_service/data/authenticationcodeclose",
        client.topicMobiBasepath + "ui_service/data/authenticationcodetoast",
    ):
        event = "closed" if topic.endswith("/authenticationcodeclose") else "busy"
        _LOGGER.info("[%s] TV reported pairing dialog %s", ip, event)
        event_future = getattr(client, "_pairing_event_future", None)
        if event_future:
            client._safe_set_future_result(event_future, event)
        return

    if client._auth_code_future and topic == client.topicMobiBasepath + "ui_service/data/authenticationcode":
        client._safe_set_future_result(client._auth_code_future, payload)
        return

    if client._token_future and topic in (
        client.topicMobiBasepath + "platform_service/data/tokenissuance",
        client.topicMobiBasepath + "platform_service/data/gettoken",
    ):
        client._safe_set_future_result(client._token_future, payload)
        return

    # 2. State & power updates
    if topic in (
        client.topicBrcsBasepath + "ui_service/state",
        client.topicMobiBasepath + "ui_service/data/gettvstate",
        client.topicMobiBasepath + "ui_service/data/state",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_state_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing state payload: %s", ip, e)
        return

    if topic in (
        client.topicBrcsBasepath + "platform_service/actions/volumechange",
        client.topicBrcsBasepath + "ui_service/volume",
        client.topicMobiBasepath + "platform_service/data/getvolume",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_volume_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing volume payload: %s", ip, e)
        return

    if topic == client.topicBrcsBasepath + "platform_service/actions/tvsleep":
        client._dispatch_state_update({"statetype": "fake_sleep_0"})
        return

    if topic == client.topicMobiBasepath + "ui_service/data/sourcelist":
        try:
            data = json.loads(payload)
            client._dispatch_sourcelist_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing sourcelist payload: %s", ip, e)
        return

    if topic == client.topicMobiBasepath + "ui_service/data/applist":
        try:
            data = json.loads(payload)
            client._dispatch_applist_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing applist payload: %s", ip, e)
        return

    if topic in (
        client.topicMobiBasepath + "platform_service/data/picturesetting",
        client.topicBrcsBasepath + "platform_service/data/picturesetting",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_picture_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing picturesetting payload: %s", ip, e)
        return

    if topic in (
        client.topicMobiBasepath + "platform_service/data/soundsetting",
        client.topicBrcsBasepath + "platform_service/data/soundsetting",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_sound_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing soundsetting payload: %s", ip, e)
        return

    if topic == client.topicMobiBasepath + "ui_service/data/capability":
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
        client.topicMobiBasepath + "platform_service/data/getdeviceinfo",
        client.topicMobiBasepath + "platform_service/data/gettvinfo",
    ):
        try:
            data = json.loads(payload)
            client._dispatch_device_info_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing device info payload: %s", ip, e)
        return
