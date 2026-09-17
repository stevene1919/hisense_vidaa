"""Binary sensors for Hisense VIDAA TV."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import DOMAIN
from .entity import HisenseVidaaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hisense VIDAA binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: HisenseTvClient = data.get("client", data) if isinstance(data, dict) else data

    async_add_entities([
        HisenseVidaaMqttConnectedBinarySensor(client, entry),
        HisenseVidaaInUseBinarySensor(client, entry),
    ])


class HisenseVidaaMqttConnectedBinarySensor(HisenseVidaaEntity, BinarySensorEntity):
    """Binary sensor indicating if TV MQTT broker connection is active."""

    _attr_translation_key = "mqtt_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        client: HisenseTvClient,
        entry_or_mac=None,
        mac=None,
        entry_id=None,
        name=None,
        model=None,
        manufacturer=None,
        sw_version=None,
        options=None,
    ) -> None:
        """Initialize the binary sensor."""
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
        self._attr_unique_id = f"{self._entry_id}_mqtt_connected"

    @property
    def is_on(self) -> bool:
        """Return true if MQTT connection is active."""
        return self._client.connected

    async def async_added_to_hass(self) -> None:
        """Register callbacks when added."""
        self._client.register_connected_callback(self._handle_update)
        self._client.register_state_callback(self._handle_update)
        self._client.register_disconnected_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self._client.unregister_connected_callback(self._handle_update)
        self._client.unregister_state_callback(self._handle_update)
        self._client.unregister_disconnected_callback(self._handle_update)

    def _handle_update(self, *args: Any) -> None:
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()


class HisenseVidaaInUseBinarySensor(HisenseVidaaEntity, BinarySensorEntity):
    """Binary sensor indicating whether the TV is genuinely awake and displaying content."""

    _attr_name = "In Use"
    _attr_icon = "mdi:television-play"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        client: HisenseTvClient,
        entry_or_mac=None,
        mac=None,
        entry_id=None,
        name=None,
        model=None,
        manufacturer=None,
        sw_version=None,
        options=None,
    ) -> None:
        """Initialize the in-use binary sensor."""
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
        self._attr_unique_id = f"{self._entry_id}_in_use"

    @property
    def is_on(self) -> bool:
        """Return True when TV is active and not in standby."""
        return bool(self._client and self._client.connected and self._client.state not in ("off", ""))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return metadata regarding the current playback or TV broadcast."""
        if not self._client:
            return {}
        return {
            "current_source": self._client.current_source,
            "channel_name": self._client.current_channel,
            "channel_number": self._client.channel_number,
            "program_title": self._client.current_program,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks when added."""
        self._client.register_connected_callback(self._handle_update)
        self._client.register_state_callback(self._handle_update)
        self._client.register_volume_callback(self._handle_update)
        self._client.register_disconnected_callback(self._handle_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self._client.unregister_connected_callback(self._handle_update)
        self._client.unregister_state_callback(self._handle_update)
        self._client.unregister_volume_callback(self._handle_update)
        self._client.unregister_disconnected_callback(self._handle_update)

    def _handle_update(self, *args: Any) -> None:
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()

