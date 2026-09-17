import asyncio
import logging
import time
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_WOL,
    CONF_KEY_DELAY,
    CONF_KEY_REPEAT,
    CONF_SECONDARY_MAC_ADDRESS,
    DEFAULT_ENABLE_WOL,
    DEFAULT_KEY_DELAY,
    DEFAULT_KEY_REPEAT,
    DOMAIN,
)
from .entity import HisenseVidaaEntity

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaRemote(HisenseVidaaEntity, RemoteEntity):
    """Hisense VIDAA Remote entity."""

    _attr_name = "Remote"

    def __init__(
        self,
        client,
        entry_or_mac=None,
        mac=None,
        entry_id=None,
        name=None,
        options=None,
        model=None,
        manufacturer=None,
        sw_version=None,
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
        self._attr_unique_id = f"{self._entry_id}_remote"

    async def async_added_to_hass(self) -> None:
        """Register callbacks and query initial state when entity is added to hass."""
        self._client.register_connected_callback(self._handle_update)
        self._client.register_state_callback(self._handle_update)
        self._client.register_volume_callback(self._handle_update)
        self._client.register_sourcelist_callback(self._handle_update)
        self._client.register_applist_callback(self._handle_update)
        self._client.register_disconnected_callback(self._handle_update)

        # Sync state immediately if client is already connected
        if getattr(self._client, "connected", False):
            await self.hass.async_add_executor_job(self._client.query_initial_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._client.unregister_connected_callback(self._handle_update)
        self._client.unregister_state_callback(self._handle_update)
        self._client.unregister_volume_callback(self._handle_update)
        self._client.unregister_sourcelist_callback(self._handle_update)
        self._client.unregister_applist_callback(self._handle_update)
        self._client.unregister_disconnected_callback(self._handle_update)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def is_on(self) -> bool:
        """Return true if TV is on."""
        return bool(self._client and self._client.connected and self._client.is_on)

    @property
    def available(self) -> bool:
        """Return true if remote is available."""
        return bool(self._entry_id and (self._client.access_token or self._mac))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the TV on."""
        enable_wol = self._options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL)
        if enable_wol:
            mac_targets = []
            if self._mac:
                mac_targets.append(self._mac)
            sec_mac = self._options.get(CONF_SECONDARY_MAC_ADDRESS)
            if sec_mac and sec_mac not in mac_targets:
                mac_targets.append(sec_mac)
            if mac_targets:
                await self.hass.async_add_executor_job(
                    self._client.send_wake_on_lan,
                    mac_targets,
                    None,
                    9,
                    getattr(self._client, "ip", None),
                )

        if self._client.connected:
            # If the TV is in fake_sleep_0 (screen off / standby), send KEY_POWER to wake it.
            # If it is already ON, do NOT send KEY_POWER because KEY_POWER is a toggle and will turn it off!
            if not self._client.is_on:
                _LOGGER.debug("TV connected in standby/fake sleep. Sending KEY_POWER to wake display")
                self._client.send_key("KEY_POWER")
            else:
                _LOGGER.debug("TV already connected and running. Skipping KEY_POWER to prevent powering off")
        else:
            await self.hass.async_add_executor_job(self._ensure_connected_and_send_power)

        self._client.is_on = True
        self.async_write_ha_state()

    def _ensure_connected_and_send_power(self) -> None:
        try:
            if self._client.ensure_connected():
                for _ in range(50):
                    if self._client.connected:
                        self._client.send_key("KEY_POWER")
                        break
                    time.sleep(0.1)
        except Exception as e:
            _LOGGER.error("Failed to reconnect and send KEY_POWER from remote: %s", e)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the TV off."""
        if self._client.connected and self._client.is_on:
            self._client.send_key("KEY_POWER")
        self._client.is_on = False
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands to the TV."""
        default_delay = self._options.get(CONF_KEY_DELAY, DEFAULT_KEY_DELAY)
        default_repeats = self._options.get(CONF_KEY_REPEAT, DEFAULT_KEY_REPEAT)
        num_repeats = kwargs.get("num_repeats", default_repeats)
        delay_secs = kwargs.get("delay_secs", default_delay)
        hold_secs = kwargs.get("hold_secs", 0.0)

        for _ in range(num_repeats):
            for single_cmd in command:
                if hold_secs and hold_secs > 0:
                    cmd_lower = single_cmd.strip().lower()
                    if cmd_lower in ("ok", "enter", "select", "key_ok"):
                        self._client.send_key("KEY_OK_LONG_PRESS")
                    elif cmd_lower in ("mute", "key_mute"):
                        self._client.send_key("KEY_MUTE_LONG_PRESS")
                    else:
                        # Emulate key hold by rapid repetition over hold_secs
                        steps = max(1, round(hold_secs / 0.1))
                        for _ in range(steps):
                            self._client.send_command(single_cmd)
                            await asyncio.sleep(0.1)
                else:
                    self._client.send_command(single_cmd)
                if delay_secs > 0:
                    await asyncio.sleep(delay_secs)

    def _handle_update(self, *args: Any) -> None:
        """Handle state update from TV."""
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_connected(self, *args: Any) -> None:
        self._handle_update()

    def _handle_disconnected(self, *args: Any) -> None:
        self._handle_update()

    def _handle_state_update(self, data: dict[str, Any]) -> None:
        if isinstance(data, dict):
            statetype = data.get("statetype")
            if statetype == "fake_sleep_0":
                if self._client:
                    self._client.is_on = False
            elif self._client:
                self._client.is_on = True
        self._handle_update()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA remote entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client = data.get("client", data) if isinstance(data, dict) else data

    entity = HisenseVidaaRemote(
        client=client,
        entry_or_mac=config_entry,
    )
    async_add_entities([entity])
