"""TV volume actions for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100)."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(f"{client.topics.platform}actions/changevolume", str(volume))


async def async_set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100) asynchronously."""
    if client.connected and client.mqtt_client:
        await client.async_publish(f"{client.topics.platform}actions/changevolume", str(volume))


class TvMediaActionsMixin:
    """Mixin providing volume control actions."""

    def set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100)."""
        set_volume(self, volume=volume)  # type: ignore[arg-type]

    async def async_set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100) asynchronously."""
        await async_set_volume(self, volume=volume)  # type: ignore[arg-type]
