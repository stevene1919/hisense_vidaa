"""Diagnostic utility buttons for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import VidaaClient
from .const import (
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_SOUND_CONTROLS,
)
from .entity import VidaaEntity

if TYPE_CHECKING:
    from . import VidaaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VidaaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VIDAA buttons based on a config entry."""
    client: VidaaClient = entry.runtime_data.client

    entities: list[ButtonEntity] = [
        VidaaForceReconnectButton(client, entry),
        VidaaSyncClockButton(client, entry),
        VidaaProbeCapabilitiesButton(client, entry),
        VidaaTriggerReauthButton(client, entry),
    ]

    async_add_entities(entities)


class VidaaBaseButton(VidaaEntity, ButtonEntity):
    """Base button for VIDAA Smart TV."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC


class VidaaForceReconnectButton(VidaaBaseButton):
    """Button to force reconnect the MQTT client."""

    _attr_translation_key = "force_reconnect"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_force_reconnect"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Manually forcing MQTT reconnection to TV at %s", self._client.ip)
        await self._client.async_disconnect()
        await self._client.async_connect_and_run()


class VidaaSyncClockButton(VidaaBaseButton):
    """Button to query and verify the TV's UPnP clock time."""

    _attr_translation_key = "sync_clock"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_sync_clock"

    async def async_press(self) -> None:
        """Handle button press."""
        offset = await self._client.async_sync_clock(2.0)
        if offset is not None:
            _LOGGER.info(
                "[%s] Successfully synchronized TV clock (offset: %d s)",
                self._client.ip,
                offset,
            )
        else:
            _LOGGER.warning("Could not fetch UPnP timestamp from TV at %s", self._client.ip)


class VidaaProbeCapabilitiesButton(VidaaBaseButton):
    """Button to actively query and probe live TV picture and sound menu capabilities."""

    _attr_translation_key = "probe_capabilities"
    _attr_icon = "mdi:television-guide"
    _attr_entity_registry_enabled_default = False

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_probe_capabilities"

    async def async_press(self) -> None:
        """Handle button press to probe capabilities."""
        if not self._client.connected:
            _LOGGER.warning("[%s] Cannot probe capabilities: TV is not connected via MQTT", self._client.ip)
            return

        _LOGGER.info("[%s] Probing TV picture and sound menu capabilities over MQTT...", self._client.ip)
        await self._client.async_get_picture_settings()
        await self._client.async_get_sound_settings()
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


class VidaaTriggerReauthButton(VidaaBaseButton):
    """Button to manually initiate re-pairing and re-authentication with the TV."""

    _attr_translation_key = "trigger_reauth"
    _attr_icon = "mdi:cellphone-key"

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_trigger_reauth"

    async def async_press(self) -> None:
        """Handle button press to trigger re-authentication flow."""
        _LOGGER.info("[%s] Manually triggering re-pairing flow for TV", self._client.ip)
        self._entry.async_start_reauth(self.hass)


# Backwards-compatible aliases during migration
HisenseVidaaBaseButton = VidaaBaseButton
HisenseVidaaForceReconnectButton = VidaaForceReconnectButton
HisenseVidaaSyncClockButton = VidaaSyncClockButton
HisenseVidaaProbeCapabilitiesButton = VidaaProbeCapabilitiesButton
HisenseVidaaTriggerReauthButton = VidaaTriggerReauthButton

