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
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    DEFAULT_NAME,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hisense VIDAA binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: HisenseTvClient = data["client"]

    async_add_entities([HisenseVidaaMqttConnectedBinarySensor(client, entry)])


class HisenseVidaaMqttConnectedBinarySensor(BinarySensorEntity):
    """Binary sensor indicating if TV MQTT broker connection is active."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "mqtt_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        self._client = client
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{self._entry_id}_mqtt_connected"
        self._mac = entry.data.get(CONF_MAC_ADDRESS)
        self._name = entry.title or DEFAULT_NAME
        self._entry = entry

    @property
    def is_on(self) -> bool:
        """Return true if MQTT connection is active."""
        return self._client.connected

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer=self._entry.data.get(CONF_MANUFACTURER, "Hisense"),
            model=self._entry.data.get(CONF_MODEL, "VIDAA TV"),
            sw_version=self._entry.data.get(CONF_SW_VERSION),
        )
        if self._mac:
            cleaned_mac = self._mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}
        return info

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
