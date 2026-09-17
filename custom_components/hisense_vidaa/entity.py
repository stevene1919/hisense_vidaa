"""Base entity for the Hisense VIDAA TV integration."""

from __future__ import annotations

from typing import Any

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
        entry_or_mac: ConfigEntry | str | None = None,
        mac: str | None = None,
        entry_id: str | None = None,
        name: str | None = None,
        model: str | None = None,
        manufacturer: str | None = None,
        sw_version: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the base entity."""
        self._client = client

        entry = entry_or_mac if isinstance(entry_or_mac, ConfigEntry) else None
        if entry:
            self._entry: ConfigEntry | None = entry
            self._entry_id = entry.entry_id
            self._mac = entry.data.get(CONF_MAC_ADDRESS)
            self._name = entry.title or DEFAULT_NAME
            self._model = entry.data.get(CONF_MODEL, model or "VIDAA TV")
            self._manufacturer = entry.data.get(
                CONF_MANUFACTURER, manufacturer or "Hisense"
            )
            self._sw_version = entry.data.get(CONF_SW_VERSION, sw_version)
            self._options = entry.options
        else:
            self._entry = None
            self._mac = str(mac or entry_or_mac) if (mac or entry_or_mac) else None
            self._entry_id = entry_id or (
                self._mac.replace(":", "") if self._mac else "hisense_tv"
            )
            self._name = name or DEFAULT_NAME
            self._model = model or "VIDAA TV"
            self._manufacturer = manufacturer or "Hisense"
            self._sw_version = sw_version
            self._options = options or {}

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
        return bool(self._client and self._client.connected)
