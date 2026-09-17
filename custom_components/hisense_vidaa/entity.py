"""Base entity for the Hisense VIDAA TV integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

from .client import HisenseTvClient
from .const import (
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    DEFAULT_NAME,
    DOMAIN,
)


class HisenseVidaaEntity(Entity):
    """Base entity representation for Hisense VIDAA TV."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the base entity."""
        self._client = client
        self._entry: ConfigEntry = entry
        self._entry_id = entry.entry_id
        self._mac = entry.data.get(CONF_MAC_ADDRESS)
        self._name = entry.title or DEFAULT_NAME
        self._model = entry.data.get(CONF_MODEL, "VIDAA TV")
        self._manufacturer = entry.data.get(CONF_MANUFACTURER, "Hisense")
        self._sw_version = entry.data.get(CONF_SW_VERSION)
        self._options = entry.options

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant DeviceInfo linking to this TV."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer=self._manufacturer,
            model=self._model,
            sw_version=self._sw_version,
        )
        if self._mac:
            cleaned_mac = self._mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}
        return info

    @property
    def available(self) -> bool:
        """Return True if the TV entity is available."""
        return bool(self._entry_id and self._client)
