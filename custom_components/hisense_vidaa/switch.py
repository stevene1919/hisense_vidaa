"""Switch platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_AUDIO_ONLY,
    DEFAULT_ENABLE_AUDIO_ONLY,
    DOMAIN,
)
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)

AUDIO_ONLY_KEY = "KEY_AUDIO"
WAKE_KEY = "KEY_INFO"
KEY_GAP_SECONDS = 0.5


class HisenseVidaaAudioOnlySwitch(HisenseVidaaEntity, SwitchEntity):
    """Switch for Audio-Only mode (display panel off, sound playing).

    Supported on select VIDAA TV models that implement KEY_AUDIO screen toggle.
    """

    _attr_name = "Audio Only"
    _attr_icon = "mdi:television-off"

    def __init__(
        self,
        client: Any,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_audio_only"
        self._is_on: bool = False

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and bool(self._client and self._client.connected)

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        self._client.register_disconnected_callback(self._handle_disconnected)
        self._client.register_state_callback(self._handle_state_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_disconnected_callback(self._handle_disconnected)
        self._client.unregister_state_callback(self._handle_state_update)

    def _handle_disconnected(self, *args: Any) -> None:
        self._is_on = False
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()

    def _handle_state_update(self, data: dict[str, Any]) -> None:
        if isinstance(data, dict) and data.get("statetype") == "fake_sleep_0":
            self._is_on = False
            if getattr(self, "hass", None) is not None:
                self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn off the screen while keeping audio active."""
        if not self._client or not self._client.connected:
            return
        # Guarantee screen is awake first, then toggle off
        await self.hass.async_add_executor_job(self._client.send_key, WAKE_KEY)
        await asyncio.sleep(KEY_GAP_SECONDS)
        await self.hass.async_add_executor_job(self._client.send_key, AUDIO_ONLY_KEY)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Wake the screen back up."""
        if not self._client or not self._client.connected:
            return
        await self.hass.async_add_executor_job(self._client.send_key, WAKE_KEY)
        self._is_on = False
        self.async_write_ha_state()


class HisenseVidaaDebugLoggingSwitch(HisenseVidaaEntity, SwitchEntity):
    """Switch to dynamically toggle verbose debug logging in Home Assistant runtime."""

    _attr_name = "Debug Logging"
    _attr_icon = "mdi:bug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        client: Any,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_debug_logging"

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def is_on(self) -> bool:
        """Return True if debug logging is enabled for this integration."""
        return logging.getLogger("custom_components.hisense_vidaa").isEnabledFor(logging.DEBUG)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable debug logging."""
        logging.getLogger("custom_components.hisense_vidaa").setLevel(logging.DEBUG)
        _LOGGER.info("Debug logging enabled for custom_components.hisense_vidaa")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable debug logging."""
        logging.getLogger("custom_components.hisense_vidaa").setLevel(logging.NOTSET)
        _LOGGER.info("Debug logging disabled for custom_components.hisense_vidaa")
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA switch platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client = data["client"]

    enable_audio_only = config_entry.options.get(
        CONF_ENABLE_AUDIO_ONLY, DEFAULT_ENABLE_AUDIO_ONLY
    )

    # Clean up audio_only switch from entity registry if disabled
    entity_reg = er.async_get(hass)
    unique_id = f"{config_entry.entry_id}_audio_only"
    if not enable_audio_only and (
        entity_id := entity_reg.async_get_entity_id("switch", DOMAIN, unique_id)
    ):
        entity_reg.async_remove(entity_id)

    entities: list[SwitchEntity] = [
        HisenseVidaaDebugLoggingSwitch(client=client, entry=config_entry),
    ]
    if enable_audio_only:
        entities.append(
            HisenseVidaaAudioOnlySwitch(client=client, entry=config_entry)
        )

    async_add_entities(entities)
