import asyncio
import logging
import time
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_WOL,
    CONF_KEY_DELAY,
    CONF_KEY_REPEAT,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SECONDARY_MAC_ADDRESS,
    CONF_SW_VERSION,
    DEFAULT_ENABLE_WOL,
    DEFAULT_KEY_DELAY,
    DEFAULT_KEY_REPEAT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaRemote(RemoteEntity):
    """Hisense VIDAA Remote entity."""

    _attr_has_entity_name = True
    _attr_name = "Remote"

    def __init__(
        self,
        client,
        mac,
        entry_id,
        name,
        options=None,
        model=None,
        manufacturer=None,
        sw_version=None,
    ):
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._options = options or {}
        self._model = model or "VIDAA TV"
        self._manufacturer = manufacturer or "Hisense"
        self._sw_version = sw_version
        self._state = STATE_ON if getattr(client, "connected", False) else STATE_OFF

    async def async_added_to_hass(self) -> None:
        """Register callbacks and query initial state when entity is added to hass."""
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

        # Sync state immediately if client is already connected
        if getattr(self._client, "connected", False):
            self._state = STATE_ON
            await self.hass.async_add_executor_job(self._client.query_initial_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._entry_id}_remote"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info linked to the same TV device."""
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
    def is_on(self) -> bool:
        """Return true if TV is on."""
        return self._client.connected and self._state != STATE_OFF

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
            if self._state == STATE_OFF:
                _LOGGER.debug("TV connected in standby/fake sleep. Sending KEY_POWER to wake display")
                self._client.send_key("KEY_POWER")
            else:
                _LOGGER.debug("TV already connected and running. Skipping KEY_POWER to prevent powering off")
        else:
            await self.hass.async_add_executor_job(self._send_power_reconnect)

        self._state = STATE_ON
        self.async_write_ha_state()

    def _send_power_reconnect(self) -> None:
        try:
            self._client.check_and_refresh_token()
            self._client.mqtt_client.username_pw_set(
                username=self._client.username,
                password=self._client.access_token,
            )
            self._client.mqtt_client.reconnect()
            for _ in range(50):
                if self._client.connected:
                    self._client.send_key("KEY_POWER")
                    break
                time.sleep(0.1)
        except Exception as e:
            _LOGGER.error("Failed to reconnect and send KEY_POWER from remote: %s", e)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the TV off."""
        if self._client.connected and self._state != STATE_OFF:
            self._client.send_key("KEY_POWER")
        self._state = STATE_OFF
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

    def _handle_connected(self) -> None:
        """Handle MQTT connection established."""
        self._state = STATE_ON
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_state_update(self, data: dict[str, Any]) -> None:
        statetype = data.get("statetype")
        if statetype == "fake_sleep_0":
            self._state = STATE_OFF
        else:
            self._state = STATE_ON
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_disconnected(self) -> None:
        self._state = STATE_OFF
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA remote entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client = data.get("client", data) if isinstance(data, dict) else data
    mac = config_entry.data.get(CONF_MAC_ADDRESS)
    options = config_entry.options

    entity = HisenseVidaaRemote(
        client=client,
        mac=mac,
        entry_id=config_entry.entry_id,
        name=config_entry.title,
        options=options,
        model=config_entry.data.get(CONF_MODEL, "VIDAA TV"),
        manufacturer=config_entry.data.get(CONF_MANUFACTURER, "Hisense"),
        sw_version=config_entry.data.get(CONF_SW_VERSION),
    )
    async_add_entities([entity])
