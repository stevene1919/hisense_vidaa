"""TV volume and toast notification actions for Hisense VIDAA TV."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def show_message(
    client: HisenseTvClient, message: str, title: str | None = None, duration: int = 5
) -> bool:
    """Displays an on-screen toast popup notification on the TV."""
    if not client.connected or not client.mqtt_client:
        _LOGGER.debug("[%s] Cannot show toast message: TV MQTT client not connected", getattr(client, "ip", "unknown"))
        return False

    payload_dict = {
        "message": message,
        "title": title or "",
        "duration": duration,
        "type": "notify",
    }
    payload = json.dumps(payload_dict)
    client.mqtt_client.publish(f"{client.topics.ui}actions/showmessage", payload)
    client.mqtt_client.publish(f"{client.topics.ui}actions/toast", payload)
    return True


async def async_show_message(
    client: HisenseTvClient, message: str, title: str | None = None, duration: int = 5
) -> bool:
    """Displays an on-screen toast popup notification on the TV asynchronously."""
    if not client.connected or not client.mqtt_client:
        _LOGGER.debug("[%s] Cannot show toast message: TV MQTT client not connected", getattr(client, "ip", "unknown"))
        return False

    payload_dict = {
        "message": message,
        "title": title or "",
        "duration": duration,
        "type": "notify",
    }
    payload = json.dumps(payload_dict)
    await client.async_publish(f"{client.topics.ui}actions/showmessage", payload)
    await client.async_publish(f"{client.topics.ui}actions/toast", payload)
    return True


def set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100)."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(f"{client.topics.platform}actions/changevolume", str(volume))


async def async_set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100) asynchronously."""
    if client.connected and client.mqtt_client:
        await client.async_publish(f"{client.topics.platform}actions/changevolume", str(volume))


class TvMediaActionsMixin:
    """Mixin providing volume control and notification toast actions."""

    def show_message(self, message: str, title: str | None = None, duration: int = 5) -> bool:
        """Displays an on-screen toast popup notification on the TV."""
        return show_message(self, message=message, title=title, duration=duration)  # type: ignore[arg-type]

    async def async_show_message(self, message: str, title: str | None = None, duration: int = 5) -> bool:
        """Displays an on-screen toast popup notification on the TV asynchronously."""
        return await async_show_message(self, message=message, title=title, duration=duration)  # type: ignore[arg-type]

    def set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100)."""
        set_volume(self, volume=volume)  # type: ignore[arg-type]

    async def async_set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100) asynchronously."""
        await async_set_volume(self, volume=volume)  # type: ignore[arg-type]
