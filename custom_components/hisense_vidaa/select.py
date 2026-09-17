"""Select platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_SOUND_CONTROLS,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_SOUND_CONTROLS,
    DOMAIN,
)
from .entity import HisenseVidaaEntity
from .tv.settings import (
    DEFAULT_MENU_ID_PICTURE_MODE,
    DEFAULT_MENU_ID_SOUND_MODE,
    STANDARD_PICTURE_MODES,
    STANDARD_SOUND_MODES,
    find_menu_item_by_name,
)

_LOGGER = logging.getLogger(__name__)

AUDIO_OUTPUT_TV_SPEAKERS = "TV Speakers"
AUDIO_OUTPUT_ARC = "ARC / eARC"
AUDIO_OUTPUT_HEADPHONE = "Headphone / Bluetooth"

AUDIO_OUTPUT_OPTIONS = [
    AUDIO_OUTPUT_TV_SPEAKERS,
    AUDIO_OUTPUT_ARC,
    AUDIO_OUTPUT_HEADPHONE,
]

VOLUME_TYPE_MAP = {
    0: AUDIO_OUTPUT_TV_SPEAKERS,
    1: AUDIO_OUTPUT_ARC,
    2: AUDIO_OUTPUT_HEADPHONE,
}


class HisenseVidaaAudioOutputSelect(HisenseVidaaEntity, SelectEntity):
    """Hisense VIDAA Audio Output Mode selector."""

    _attr_name = "Audio Output Mode"
    _attr_icon = "mdi:speaker-multiple"
    _attr_options = AUDIO_OUTPUT_OPTIONS

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_audio_output_select"
        self._volume_type = 0

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._client and self._client.connected)

    async def async_added_to_hass(self) -> None:
        self._client.register_volume_callback(self._handle_volume_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_volume_callback(self._handle_volume_update)

    @property
    def current_option(self) -> str:
        return VOLUME_TYPE_MAP.get(self._volume_type, AUDIO_OUTPUT_TV_SPEAKERS)

    def _handle_volume_update(self, data: dict[str, Any]) -> None:
        vol_type = data.get("volume_type")
        if vol_type in (0, 1):
            self._volume_type = int(vol_type)
            self.schedule_update_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the audio output option."""
        if option == AUDIO_OUTPUT_TV_SPEAKERS:
            self._volume_type = 0
            await self.hass.async_add_executor_job(self._client.send_key, "KEY_AUDIO_ONLY")
        elif option == AUDIO_OUTPUT_ARC:
            self._volume_type = 1
            await self.hass.async_add_executor_job(self._client.send_key, "KEY_SOUND")
        elif option == AUDIO_OUTPUT_HEADPHONE:
            self._volume_type = 2
            await self.hass.async_add_executor_job(self._client.send_key, "KEY_HEADPHONE")
        self.async_write_ha_state()


class HisenseVidaaPictureModeSelect(HisenseVidaaEntity, SelectEntity):
    """Hisense VIDAA Picture Mode selector."""

    _attr_name = "Picture Mode"
    _attr_icon = "mdi:television-shading"

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_picture_mode"
        self._current_mode = "Standard"

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._client and self._client.connected)

    async def async_added_to_hass(self) -> None:
        self._client.register_picture_callback(self._handle_picture_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_picture_callback(self._handle_picture_update)

    @property
    def options(self) -> list[str]:
        pm_item = find_menu_item_by_name(self._client.picture_settings, "Picture Mode", DEFAULT_MENU_ID_PICTURE_MODE)
        if pm_item and pm_item.options:
            return pm_item.options
        return STANDARD_PICTURE_MODES

    @property
    def current_option(self) -> str | None:
        if self._client.picture_mode:
            return self._client.picture_mode
        return self._current_mode

    def _handle_picture_update(self, data: dict[str, Any]) -> None:
        if self._client.picture_mode:
            self._current_mode = self._client.picture_mode
        self.schedule_update_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change picture mode option."""
        self._current_mode = option
        await self.hass.async_add_executor_job(self._client.set_picture_mode, option)
        self.async_write_ha_state()


class HisenseVidaaSoundModeSelect(HisenseVidaaEntity, SelectEntity):
    """Hisense VIDAA Sound Mode selector."""

    _attr_name = "Sound Mode"
    _attr_icon = "mdi:equalizer"

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_sound_mode"
        self._current_mode = "Standard"

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._client and self._client.connected)

    async def async_added_to_hass(self) -> None:
        self._client.register_sound_callback(self._handle_sound_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_sound_callback(self._handle_sound_update)

    @property
    def options(self) -> list[str]:
        sm_item = find_menu_item_by_name(self._client.sound_settings, "Sound Mode", DEFAULT_MENU_ID_SOUND_MODE)
        if sm_item and sm_item.options:
            return sm_item.options
        return STANDARD_SOUND_MODES

    @property
    def current_option(self) -> str | None:
        if self._client.sound_mode:
            return self._client.sound_mode
        return self._current_mode

    def _handle_sound_update(self, data: dict[str, Any]) -> None:
        if self._client.sound_mode:
            self._current_mode = self._client.sound_mode
        self.schedule_update_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change sound mode option."""
        self._current_mode = option
        await self.hass.async_add_executor_job(self._client.set_sound_mode, option)
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA select platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: HisenseTvClient = data["client"]

    enable_picture = config_entry.options.get(
        CONF_ENABLE_PICTURE_CONTROLS, DEFAULT_ENABLE_PICTURE_CONTROLS
    )
    enable_sound = config_entry.options.get(
        CONF_ENABLE_SOUND_CONTROLS, DEFAULT_ENABLE_SOUND_CONTROLS
    )

    # Clean up disabled/unsupported entities from entity registry
    entity_reg = er.async_get(hass)
    if not enable_picture:
        unique_id = f"{config_entry.entry_id}_picture_mode"
        if entity_id := entity_reg.async_get_entity_id("select", DOMAIN, unique_id):
            entity_reg.async_remove(entity_id)

    if not enable_sound:
        unique_id = f"{config_entry.entry_id}_sound_mode"
        if entity_id := entity_reg.async_get_entity_id("select", DOMAIN, unique_id):
            entity_reg.async_remove(entity_id)

    entities: list[SelectEntity] = [
        HisenseVidaaAudioOutputSelect(client=client, entry=config_entry),
    ]
    if enable_picture:
        entities.append(
            HisenseVidaaPictureModeSelect(client=client, entry=config_entry)
        )
    if enable_sound:
        entities.append(
            HisenseVidaaSoundModeSelect(client=client, entry=config_entry)
        )

    async_add_entities(entities)
