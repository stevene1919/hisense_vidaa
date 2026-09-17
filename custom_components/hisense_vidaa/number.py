"""Number platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaBaseNumber(HisenseVidaaEntity, NumberEntity):
    """Base number entity for Hisense VIDAA TV picture calibration."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

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
        options=None,
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
            options=options,
        )
        self._value = 50.0

    async def async_added_to_hass(self) -> None:
        self._client.register_picture_callback(self._handle_picture_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_picture_callback(self._handle_picture_update)

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        self._update_value_from_client()
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _update_value_from_client(self) -> None:
        """Override in subclasses to read specific attribute."""


class HisenseVidaaBacklightNumber(HisenseVidaaBaseNumber):
    """Hisense VIDAA Backlight Slider."""

    _attr_name = "Backlight"
    _attr_icon = "mdi:brightness-6"

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
        options=None,
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
            options=options,
        )
        self._attr_unique_id = f"{self._entry_id}_backlight"
        self._value = 80.0

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    def _update_value_from_client(self) -> None:
        if self._client.backlight is not None:
            self._value = float(self._client.backlight)

    @property
    def native_value(self) -> float | None:
        if self._client.backlight is not None:
            return float(self._client.backlight)
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set new backlight level."""
        self._value = value
        await self.hass.async_add_executor_job(self._client.set_backlight, int(value))
        self.async_write_ha_state()


class HisenseVidaaBrightnessNumber(HisenseVidaaBaseNumber):
    """Hisense VIDAA Brightness Slider."""

    _attr_name = "Brightness"
    _attr_icon = "mdi:brightness-5"

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
        options=None,
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
            options=options,
        )
        self._attr_unique_id = f"{self._entry_id}_brightness"
        self._value = 50.0

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    def _update_value_from_client(self) -> None:
        if self._client.brightness is not None:
            self._value = float(self._client.brightness)

    @property
    def native_value(self) -> float | None:
        if self._client.brightness is not None:
            return float(self._client.brightness)
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set new brightness level."""
        self._value = value
        await self.hass.async_add_executor_job(self._client.set_brightness, int(value))
        self.async_write_ha_state()


class HisenseVidaaContrastNumber(HisenseVidaaBaseNumber):
    """Hisense VIDAA Contrast Slider."""

    _attr_name = "Contrast"
    _attr_icon = "mdi:contrast-circle"

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
        options=None,
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
            options=options,
        )
        self._attr_unique_id = f"{self._entry_id}_contrast"
        self._value = 50.0

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    def _update_value_from_client(self) -> None:
        if self._client.contrast is not None:
            self._value = float(self._client.contrast)

    @property
    def native_value(self) -> float | None:
        if self._client.contrast is not None:
            return float(self._client.contrast)
        return self._value

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

    entities: list[NumberEntity] = [
        HisenseVidaaBacklightNumber(client=client, entry_or_mac=config_entry),
        HisenseVidaaBrightnessNumber(client=client, entry_or_mac=config_entry),
        HisenseVidaaContrastNumber(client=client, entry_or_mac=config_entry),
    ]

    async_add_entities(entities)
