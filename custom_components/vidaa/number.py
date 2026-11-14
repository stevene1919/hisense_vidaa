"""Number platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import VidaaClient
from .const import (
    CONF_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DOMAIN,
)
from .entity import VidaaEntity

if TYPE_CHECKING:
    from . import VidaaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class VidaaBaseNumber(VidaaEntity, NumberEntity):
    """Base number entity for VIDAA TV picture calibration."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        client: VidaaClient,
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
        self._client.register_connected_callback(self._handle_connection_change)
        self._client.register_disconnected_callback(self._handle_connection_change)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_picture_callback(self._handle_picture_update)
        self._client.unregister_connected_callback(self._handle_connection_change)
        self._client.unregister_disconnected_callback(self._handle_connection_change)

    def _handle_connection_change(self, *args: Any) -> None:
        self.schedule_update_ha_state()

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        self._update_value_from_client()
        self.schedule_update_ha_state()

    def _update_value_from_client(self) -> None:
        """Override in subclasses to read specific attribute."""


class VidaaBacklightNumber(VidaaBaseNumber):
    """VIDAA Backlight Slider."""

    _attr_translation_key = "backlight"

    def __init__(
        self,
        client: VidaaClient,
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
        await self._client.async_set_backlight(int(value))
        self.async_write_ha_state()


class VidaaBrightnessNumber(VidaaBaseNumber):
    """VIDAA Brightness Slider."""

    _attr_translation_key = "brightness"

    def __init__(
        self,
        client: VidaaClient,
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
        await self._client.async_set_brightness(int(value))
        self.async_write_ha_state()


class VidaaContrastNumber(VidaaBaseNumber):
    """VIDAA Contrast Slider."""

    _attr_translation_key = "contrast"

    def __init__(
        self,
        client: VidaaClient,
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
        await self._client.async_set_contrast(int(value))
        self.async_write_ha_state()


# Backwards-compatible aliases during migration
HisenseVidaaBaseNumber = VidaaBaseNumber
HisenseVidaaBacklightNumber = VidaaBacklightNumber
HisenseVidaaBrightnessNumber = VidaaBrightnessNumber
HisenseVidaaContrastNumber = VidaaContrastNumber


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VidaaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VIDAA number platform."""
    client: VidaaClient = config_entry.runtime_data.client

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
        VidaaBacklightNumber(client=client, entry=config_entry),
        VidaaBrightnessNumber(client=client, entry=config_entry),
        VidaaContrastNumber(client=client, entry=config_entry),
    ]

    async_add_entities(entities)
