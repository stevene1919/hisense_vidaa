"""Hisense VIDAA Toast Notification entity."""

from __future__ import annotations

import logging

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import DOMAIN
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaNotifyEntity(HisenseVidaaEntity, NotifyEntity):
    """Hisense VIDAA Toast Notification entity."""

    _attr_name = "Notifications"
    _attr_icon = "mdi:television-guide"

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_notify"

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification message to the TV."""
        await self.hass.async_add_executor_job(
            self._client.show_message, message, title
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA notify platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: HisenseTvClient = data["client"]
    async_add_entities([HisenseVidaaNotifyEntity(client=client, entry=config_entry)])
