"""Number platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaBacklightNumber(NumberEntity):
    """Hisense VIDAA Backlight Slider."""

    _attr_has_entity_name = True
    _attr_name = "Backlight"
    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        client,
        mac: str | None,
        entry_id: str,
        name: str,
        model: str | None = None,
        manufacturer: str | None = None,
        sw_version: str | None = None,
    ) -> None:
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._model = model or "VIDAA TV"
        self._manufacturer = manufacturer or "Hisense"
        self._sw_version = sw_version
        self._value = 80.0

    async def async_added_to_hass(self) -> None:
        self._client.register_picture_callback(self._handle_picture_update)

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_backlight"

    @property
    def device_info(self) -> DeviceInfo:
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
        return bool(self._client and self._client.connected)

    @property
    def native_value(self) -> float | None:
        if self._client.backlight is not None:
            return float(self._client.backlight)
        return self._value

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        if self._client.backlight is not None:
            self._value = float(self._client.backlight)
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        else:
            self.schedule_update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new backlight level."""
        self._value = value
        await self.hass.async_add_executor_job(self._client.set_backlight, int(value))
        self.async_write_ha_state()


class HisenseVidaaBrightnessNumber(NumberEntity):
    """Hisense VIDAA Brightness Slider."""

    _attr_has_entity_name = True
    _attr_name = "Brightness"
    _attr_icon = "mdi:brightness-5"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        client,
        mac: str | None,
        entry_id: str,
        name: str,
        model: str | None = None,
        manufacturer: str | None = None,
        sw_version: str | None = None,
    ) -> None:
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._model = model or "VIDAA TV"
        self._manufacturer = manufacturer or "Hisense"
        self._sw_version = sw_version
        self._value = 50.0

    async def async_added_to_hass(self) -> None:
        self._client.register_picture_callback(self._handle_picture_update)

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_brightness"

    @property
    def device_info(self) -> DeviceInfo:
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
        return bool(self._client and self._client.connected)

    @property
    def native_value(self) -> float | None:
        if self._client.brightness is not None:
            return float(self._client.brightness)
        return self._value

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        if self._client.brightness is not None:
            self._value = float(self._client.brightness)
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        else:
            self.schedule_update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new brightness level."""
        self._value = value
        await self.hass.async_add_executor_job(self._client.set_brightness, int(value))
        self.async_write_ha_state()


class HisenseVidaaContrastNumber(NumberEntity):
    """Hisense VIDAA Contrast Slider."""

    _attr_has_entity_name = True
    _attr_name = "Contrast"
    _attr_icon = "mdi:contrast-circle"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        client,
        mac: str | None,
        entry_id: str,
        name: str,
        model: str | None = None,
        manufacturer: str | None = None,
        sw_version: str | None = None,
    ) -> None:
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._model = model or "VIDAA TV"
        self._manufacturer = manufacturer or "Hisense"
        self._sw_version = sw_version
        self._value = 50.0

    async def async_added_to_hass(self) -> None:
        self._client.register_picture_callback(self._handle_picture_update)

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_contrast"

    @property
    def device_info(self) -> DeviceInfo:
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
        return bool(self._client and self._client.connected)

    @property
    def native_value(self) -> float | None:
        if self._client.contrast is not None:
            return float(self._client.contrast)
        return self._value

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        if self._client.contrast is not None:
            self._value = float(self._client.contrast)
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        else:
            self.schedule_update_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new contrast level."""
        self._value = value
        await self.hass.async_add_executor_job(self._client.set_contrast, int(value))
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA number platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client = data.get("client", data) if isinstance(data, dict) else data
    mac = config_entry.data.get(CONF_MAC_ADDRESS)
    name = config_entry.title
    model = config_entry.data.get(CONF_MODEL, "VIDAA TV")
    mfr = config_entry.data.get(CONF_MANUFACTURER, "Hisense")
    sw_ver = config_entry.data.get(CONF_SW_VERSION)

    entities: list[NumberEntity] = []

    # Only instantiate picture calibration sliders if TV advertises dynamic settings support
    if hasattr(client, "picture_settings") and client.picture_settings:
        entities.extend([
            HisenseVidaaBacklightNumber(
                client=client,
                mac=mac,
                entry_id=config_entry.entry_id,
                name=name,
                model=model,
                manufacturer=mfr,
                sw_version=sw_ver,
            ),
            HisenseVidaaBrightnessNumber(
                client=client,
                mac=mac,
                entry_id=config_entry.entry_id,
                name=name,
                model=model,
                manufacturer=mfr,
                sw_version=sw_ver,
            ),
            HisenseVidaaContrastNumber(
                client=client,
                mac=mac,
                entry_id=config_entry.entry_id,
                name=name,
                model=model,
                manufacturer=mfr,
                sw_version=sw_ver,
            ),
        ])

    async_add_entities(entities)
