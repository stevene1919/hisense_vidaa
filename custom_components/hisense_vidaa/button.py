"""Diagnostic utility buttons for Hisense VIDAA TV."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    DEFAULT_NAME,
    DOMAIN,
)
from .discovery import get_tv_timestamp

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
    ]

    async_add_entities(entities)


class HisenseVidaaBaseButton(ButtonEntity):
    """Base button for Hisense VIDAA TV."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        """Initialize the button."""
        self._client = client
        self._entry = entry
        self._entry_id = entry.entry_id
        self._mac = entry.data.get(CONF_MAC_ADDRESS)
        self._name = entry.title or DEFAULT_NAME

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer=self._entry.data.get(CONF_MANUFACTURER, "Hisense"),
            model=self._entry.data.get(CONF_MODEL, "VIDAA TV"),
            sw_version=self._entry.data.get(CONF_SW_VERSION),
        )
        if self._mac:
            cleaned_mac = self._mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}
        return info


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
        self._client.connect_and_run()


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
