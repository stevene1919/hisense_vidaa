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
    if client._auth_future and (
        topic in (
            client.topicMobiBasepath + "ui_service/data/authentication",
            client.topicMobiBasepath + "ui_service/data/vidaa_app_connect",
        )
        or topic.endswith("ui_service/data/authentication")
        or topic.endswith("ui_service/data/vidaa_app_connect")
    ):
        client._safe_set_future_result(client._auth_future, payload)
        return

    if client._auth_code_future and (
        topic == client.topicMobiBasepath + "ui_service/data/authenticationcode"
        or topic.endswith("ui_service/data/authenticationcode")
    ):
        client._safe_set_future_result(client._auth_code_future, payload)
        return

    if client._token_future and (
        topic in (
            client.topicMobiBasepath + "platform_service/data/tokenissuance",
            client.topicMobiBasepath + "platform_service/data/gettoken",
        )
        or topic.endswith("platform_service/data/tokenissuance")
        or topic.endswith("platform_service/data/gettoken")
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
    ) or topic.endswith("platform_service/data/getdeviceinfo") or topic.endswith("platform_service/data/gettvinfo"):
        try:
            data = json.loads(payload)
            client._dispatch_device_info_update(data)
        except Exception as e:
            _LOGGER.debug("[%s] Error parsing device info payload: %s", ip, e)
        return
