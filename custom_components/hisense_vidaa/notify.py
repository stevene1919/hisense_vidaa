"""Hisense VIDAA Toast Notification entity."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import CONF_ENABLE_NOTIFY, DEFAULT_ENABLE_NOTIFY, DOMAIN
from .entity import HisenseVidaaEntity

if TYPE_CHECKING:
    from . import HisenseVidaaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class HisenseVidaaNotifyEntity(HisenseVidaaEntity, NotifyEntity):
    """Hisense VIDAA Toast Notification entity."""

    _attr_translation_key = "notifications"

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
    config_entry: HisenseVidaaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA notify platform."""
    client: HisenseTvClient = config_entry.runtime_data.client

    # Clean up the notify entity from the entity registry if the feature was disabled
    entity_reg = er.async_get(hass)
    unique_id = f"{config_entry.entry_id}_notify"
    if not config_entry.options.get(CONF_ENABLE_NOTIFY, DEFAULT_ENABLE_NOTIFY):
        if entity_id := entity_reg.async_get_entity_id("notify", DOMAIN, unique_id):
            entity_reg.async_remove(entity_id)
        return

    async_add_entities([HisenseVidaaNotifyEntity(client=client, entry=config_entry)])
