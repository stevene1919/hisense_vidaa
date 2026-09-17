"""Hisense VIDAA Toast Notification entity."""

from __future__ import annotations

import logging

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaNotifyEntity(HisenseVidaaEntity, NotifyEntity):
    """Hisense VIDAA Toast Notification entity."""

    _attr_name = "Notifications"
    _attr_icon = "mdi:television-guide"

    def __init__(
        self,
        client,
        entry_or_mac=None,
        mac=None,
        entry_id=None,
        name=None,
        model=None,
        manufacturer=None,
        sw_version=None,
    ) -> None:
        super().__init__(
            client=client,
            entry_or_mac=entry_or_mac,
            mac=mac,
            entry_id=entry_id,
            name=name,
            model=model,
            manufacturer=manufacturer,
            sw_version=sw_version,
        )
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
    client = data.get("client", data) if isinstance(data, dict) else data

    entity = HisenseVidaaNotifyEntity(client=client, entry_or_mac=config_entry)
    async_add_entities([entity])
