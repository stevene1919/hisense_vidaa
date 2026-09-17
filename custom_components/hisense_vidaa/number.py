"""Number platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    CONF_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DOMAIN,
)
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
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._value = 50.0

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._client and self._client.connected)

    async def async_added_to_hass(self) -> None:
        self._client.register_picture_callback(self._handle_picture_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_picture_callback(self._handle_picture_update)

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        self._update_value_from_client()
        self.schedule_update_ha_state()

    def _update_value_from_client(self) -> None:
        """Override in subclasses to read specific attribute."""


class HisenseVidaaBacklightNumber(HisenseVidaaBaseNumber):
    """Hisense VIDAA Backlight Slider."""

    _attr_name = "Backlight"
    _attr_icon = "mdi:brightness-6"

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
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
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
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
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
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
    client: HisenseTvClient = data["client"]

    enable_picture = config_entry.options.get(
        CONF_ENABLE_PICTURE_CONTROLS, DEFAULT_ENABLE_PICTURE_CONTROLS
    )

    # Clean up disabled/unsupported number entities from entity registry
    entity_reg = er.async_get(hass)
    if not enable_picture:
        for suffix in ("backlight", "brightness", "contrast"):
            unique_id = f"{config_entry.entry_id}_{suffix}"
            if entity_id := entity_reg.async_get_entity_id("number", DOMAIN, unique_id):
                entity_reg.async_remove(entity_id)
        return

    entities: list[NumberEntity] = [
        HisenseVidaaBacklightNumber(client=client, entry=config_entry),
        HisenseVidaaBrightnessNumber(client=client, entry=config_entry),
        HisenseVidaaContrastNumber(client=client, entry=config_entry),
    ]

    async_add_entities(entities)
