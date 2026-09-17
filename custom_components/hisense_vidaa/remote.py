import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
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
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_remote"

    async def async_added_to_hass(self) -> None:
        """Register callbacks and query initial state when entity is added to hass."""
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_volume_callback(self._handle_update)
        self._client.register_sourcelist_callback(self._handle_update)
        self._client.register_applist_callback(self._handle_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

        # Sync state immediately if client is already connected
        if getattr(self._client, "connected", False):
            await self.hass.async_add_executor_job(self._client.query_initial_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_volume_callback(self._handle_update)
        self._client.unregister_sourcelist_callback(self._handle_update)
        self._client.unregister_applist_callback(self._handle_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)

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

    async def _async_exec(self, func: Any, *args: Any) -> Any:
        """Execute a client function in the executor if hass is present, or directly if testing."""
        if getattr(self, "hass", None) is not None:
            return await self.hass.async_add_executor_job(func, *args)
        return func(*args)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the TV on."""
        mac_targets = []
        if self._options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL):
            if self._mac:
                mac_targets.append(self._mac)
            sec_mac = self._options.get(CONF_SECONDARY_MAC_ADDRESS)
            if sec_mac and sec_mac not in mac_targets:
                mac_targets.append(sec_mac)

        await self._async_exec(self._client.turn_on, mac_targets if mac_targets else None)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the TV off."""
        await self._async_exec(self._client.turn_off)
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
                        await self._async_exec(self._client.send_key, "KEY_OK_LONG_PRESS")
                    elif cmd_lower in ("mute", "key_mute"):
                        await self._async_exec(self._client.send_key, "KEY_MUTE_LONG_PRESS")
                    else:
                        # Emulate key hold by rapid repetition over hold_secs
                        steps = max(1, round(hold_secs / 0.1))
                        for _ in range(steps):
                            await self._async_exec(self._client.send_command, single_cmd)
                            await asyncio.sleep(0.1)
                else:
                    await self._async_exec(self._client.send_command, single_cmd)
                if delay_secs > 0:
                    await asyncio.sleep(delay_secs)

    def _handle_update(self, *args: Any) -> None:
        """Handle state update from TV."""
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
    client: HisenseTvClient = data["client"]
    async_add_entities([HisenseVidaaRemote(client=client, entry=config_entry)])
