"""Diagnostic utility buttons for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_SOUND_CONTROLS,
    DOMAIN,
)
from .discovery import get_tv_timestamp
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hisense VIDAA buttons based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: HisenseTvClient = data["client"]

    entities: list[ButtonEntity] = [
        HisenseVidaaForceReconnectButton(client, entry),
        HisenseVidaaSyncClockButton(client, entry),
        HisenseVidaaProbeCapabilitiesButton(client, entry),
    ]

    async_add_entities(entities)


class HisenseVidaaBaseButton(HisenseVidaaEntity, ButtonEntity):
    """Base button for Hisense VIDAA TV."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC


class HisenseVidaaForceReconnectButton(HisenseVidaaBaseButton):
    """Button to force reconnect the MQTT client."""

    _attr_translation_key = "force_reconnect"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_force_reconnect"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Manually forcing MQTT reconnection to TV at %s", self._client.ip)
        await self.hass.async_add_executor_job(self._client.disconnect)
        await self.hass.async_add_executor_job(self._client.connect_and_run)


class HisenseVidaaSyncClockButton(HisenseVidaaBaseButton):
    """Button to query and verify the TV's UPnP clock time."""

    _attr_translation_key = "sync_clock"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_sync_clock"

    async def async_press(self) -> None:
        """Handle button press."""
        tv_ts = await self.hass.async_add_executor_job(get_tv_timestamp, self._client.ip, 2.0)
        if tv_ts:
            _LOGGER.info("Successfully fetched live TV timestamp: %s (Epoch: %d)", self._client.ip, tv_ts)
        else:
            _LOGGER.warning("Could not fetch UPnP timestamp from TV at %s", self._client.ip)


class HisenseVidaaProbeCapabilitiesButton(HisenseVidaaBaseButton):
    """Button to actively query and probe live TV picture and sound menu capabilities."""

    _attr_translation_key = "probe_capabilities"
    _attr_icon = "mdi:television-guide"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_probe_capabilities"

    async def async_press(self) -> None:
        """Handle button press to probe capabilities."""
        if not self._client.connected:
            _LOGGER.warning("[%s] Cannot probe capabilities: TV is not connected via MQTT", self._client.ip)
            return

        _LOGGER.info("[%s] Probing TV picture and sound menu capabilities over MQTT...", self._client.ip)
        await self.hass.async_add_executor_job(self._client.get_picture_settings)
        await self.hass.async_add_executor_job(self._client.get_sound_settings)
        await asyncio.sleep(2.0)

        pic_supported = bool(self._client.picture_settings)
        sound_supported = bool(self._client.sound_settings)

        _LOGGER.info(
            "[%s] Capability probe complete: Picture Menu: %s (%d items), Sound Menu: %s (%d items)",
            self._client.ip,
            "Supported" if pic_supported else "Unsupported",
            len(self._client.picture_settings) if pic_supported else 0,
            "Supported" if sound_supported else "Unsupported",
            len(self._client.sound_settings) if sound_supported else 0,
        )

        if pic_supported or sound_supported:
            new_options = {
                **self._entry.options,
                CONF_ENABLE_PICTURE_CONTROLS: pic_supported or self._entry.options.get(CONF_ENABLE_PICTURE_CONTROLS, False),
                CONF_ENABLE_SOUND_CONTROLS: sound_supported or self._entry.options.get(CONF_ENABLE_SOUND_CONTROLS, False),
            }
            self.hass.config_entries.async_update_entry(self._entry, options=new_options)
