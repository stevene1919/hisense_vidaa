import asyncio
import logging
import time
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_WOL, CONF_MAC_ADDRESS, DEFAULT_ENABLE_WOL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaRemote(RemoteEntity):
    """Hisense VIDAA Remote entity."""

    _attr_has_entity_name = True
    _attr_name = "Remote"

    def __init__(self, client, mac, entry_id, name, options=None):
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._options = options or {}
        self._state = STATE_OFF

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added to hass."""
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._entry_id}_remote"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info linked to the same TV device."""
        info = {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._name,
            "manufacturer": "Hisense",
            "model": "VIDAA TV",
        }
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
        return self._client.connected

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the TV on."""
        enable_wol = self._options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL)
        if enable_wol and self._mac:
            await self.hass.async_add_executor_job(
                self._client.send_wake_on_lan, self._mac
            )

        if self._client.connected:
            self._client.send_key("KEY_POWER")
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
        self._client.send_key("KEY_POWER")
        self._state = STATE_OFF
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands to the TV."""
        num_repeats = kwargs.get("num_repeats", 1)
        delay_secs = kwargs.get("delay_secs", 0.4)

        for _ in range(num_repeats):
            for single_cmd in command:
                self._client.send_command(single_cmd)
                if delay_secs > 0:
                    await asyncio.sleep(delay_secs)

    def _handle_state_update(self, data: dict[str, Any]) -> None:
        statetype = data.get("statetype")
        if statetype == "fake_sleep_0":
            self._state = STATE_OFF
        else:
            self._state = STATE_ON
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_disconnected(self) -> None:
        self._state = STATE_OFF
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA remote entity."""
    client = hass.data[DOMAIN][config_entry.entry_id]
    mac = config_entry.data.get(CONF_MAC_ADDRESS)
    options = config_entry.options

    entity = HisenseVidaaRemote(
        client=client,
        mac=mac,
        entry_id=config_entry.entry_id,
        name=config_entry.title,
        options=options,
    )
    async_add_entities([entity])
