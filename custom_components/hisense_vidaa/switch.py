"""Switch platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)

AUDIO_ONLY_KEY = "KEY_AUDIO"
WAKE_KEY = "KEY_INFO"
KEY_GAP_SECONDS = 0.5


class HisenseVidaaAudioOnlySwitch(HisenseVidaaEntity, SwitchEntity):
    """Switch for Audio-Only mode (display panel off, sound playing).

    KEY_AUDIO toggles the display panel on/off without changing sound, but VIDAA
    does not report whether the screen is currently lit.

    By sending a harmless wake key (KEY_INFO) first, the screen is guaranteed to be awake,
    ensuring KEY_AUDIO consistently turns the display panel OFF (idempotent).
    Turning off sends KEY_INFO directly to wake the screen back up.
    """

    _attr_name = "Audio Only"
    _attr_icon = "mdi:television-off"

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
        self._attr_unique_id = f"{self._entry_id}_audio_only"
        self._is_on: bool = False

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def is_on(self) -> bool:
        return self._is_on

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
    client = data.get("client", data) if isinstance(data, dict) else data

    async_add_entities([
        HisenseVidaaAudioOnlySwitch(client=client, entry_or_mac=config_entry),
        HisenseVidaaDebugLoggingSwitch(client=client, entry_or_mac=config_entry),
    ])
