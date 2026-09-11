"""Diagnostic and operational sensors for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    AUTH_PROFILES,
    CONF_AUTH_PROFILE,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hisense VIDAA sensors based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    client: HisenseTvClient = data["client"]

    entities: list[SensorEntity] = [
        HisenseVidaaTokenExpiresSensor(client, entry),
        HisenseVidaaAuthProfileSensor(client, entry),
        HisenseVidaaActiveAppSensor(client, entry),
        HisenseVidaaActiveSourceSensor(client, entry),
    ]

    async_add_entities(entities)


class HisenseVidaaBaseSensor(SensorEntity):
    """Base class for Hisense VIDAA sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._client = client
        self._entry = entry
        self._entry_id = entry.entry_id
        self._mac = entry.data.get(CONF_MAC_ADDRESS)
        self._name = entry.title or DEFAULT_NAME

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info with dynamic model and software version."""
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


class HisenseVidaaTokenExpiresSensor(HisenseVidaaBaseSensor):
    """Sensor displaying access token expiration timestamp."""

    _attr_translation_key = "token_expires_in"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_token_expires"

    async def async_added_to_hass(self) -> None:
        self._client.register_token_refreshed_callback(self._handle_token_refreshed)
        self._update_state()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_token_refreshed_callback(self._handle_token_refreshed)

    def _handle_token_refreshed(self, client: HisenseTvClient) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        if self._client.access_token_time and self._client.access_token_duration:
            exp_ts = self._client.access_token_time + (self._client.access_token_duration * 86400)
            self._attr_native_value = datetime.fromtimestamp(exp_ts, tz=UTC)
        else:
            self._attr_native_value = None


class HisenseVidaaAuthProfileSensor(HisenseVidaaBaseSensor):
    """Sensor displaying current active authentication profile."""

    _attr_translation_key = "auth_profile"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_auth_profile"
        profile_key = entry.data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
        self._attr_native_value = AUTH_PROFILES.get(profile_key, profile_key.title())


class HisenseVidaaActiveAppSensor(HisenseVidaaBaseSensor):
    """Sensor reporting the foreground active application."""

    _attr_translation_key = "active_app"
    _attr_icon = "mdi:application"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_active_app"
        self._attr_native_value = None
        self._app_dict: dict[str, str] = {}

    async def async_added_to_hass(self) -> None:
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_applist_callback(self._handle_applist_update)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_state_callback(self._handle_state_update)

    def _handle_applist_update(self, apps: list[dict[str, Any]]) -> None:
        self._app_dict = {a.get("appId", ""): a.get("appName", "") for a in apps if isinstance(a, dict)}
        self.async_write_ha_state()

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        app_id = state.get("appId") or state.get("activeAppId")
        if app_id and app_id in self._app_dict:
            self._attr_native_value = self._app_dict[app_id]
        elif app_id:
            self._attr_native_value = app_id
        elif state.get("statetype") == "fake_sleep_0":
            self._attr_native_value = "Off"
        self.async_write_ha_state()


class HisenseVidaaActiveSourceSensor(HisenseVidaaBaseSensor):
    """Sensor reporting current physical input source."""

    _attr_translation_key = "active_source"
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_active_source"
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        self._client.register_sourcelist_callback(self._handle_sourcelist_update)

    def _handle_sourcelist_update(self, sources: list[dict[str, Any]]) -> None:
        for s in sources:
            if isinstance(s, dict) and s.get("is_active"):
                self._attr_native_value = s.get("sourceName") or s.get("sourcename")
                break
        self.async_write_ha_state()
