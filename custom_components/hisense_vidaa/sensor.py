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

    async_add_entities([
        HisenseVidaaTokenExpiresSensor(client, entry),
        HisenseVidaaAuthProfileSensor(client, entry),
        HisenseVidaaActiveAppSensor(client, entry),
        HisenseVidaaActiveSourceSensor(client, entry),
    ])


class HisenseVidaaBaseSensor(SensorEntity):
    """Base class for Hisense VIDAA sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        """Initialize the base sensor."""
        self._client = client
        self._entry = entry
        self._entry_id = entry.entry_id
        self._mac = entry.data.get(CONF_MAC_ADDRESS)
        self._name = entry.title or DEFAULT_NAME

    def _schedule_state_update(self) -> None:
        """Safely schedule state update if entity is added to hass."""
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()

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
        self._update_state()

    @property
    def available(self) -> bool:
        """Return True only if dynamic token expiration data exists."""
        return bool(
            self._client.auth_profile != "legacy"
            and self._client.access_token_time
            and self._client.access_token_duration
        )

    async def async_added_to_hass(self) -> None:
        self._client.register_token_refreshed_callback(self._handle_token_refreshed)
        self._update_state()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_token_refreshed_callback(self._handle_token_refreshed)

    def _handle_token_refreshed(self, client: HisenseTvClient) -> None:
        self._update_state()
        self._schedule_state_update()

    def _update_state(self) -> None:
        if self._client.auth_profile != "legacy" and self._client.access_token_time and self._client.access_token_duration:
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


class HisenseVidaaMqttTrackingSensor(HisenseVidaaBaseSensor):
    """Abstract base class for sensors monitoring live MQTT state and connection events."""

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry, default_on: str, default_off: str = "Off") -> None:
        super().__init__(client, entry)
        self._default_on = default_on
        self._default_off = default_off
        self._attr_native_value = default_off if not client.connected else default_on

    async def async_added_to_hass(self) -> None:
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_disconnected_callback(self._handle_disconnected)
        self._register_custom_callbacks()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)
        self._unregister_custom_callbacks()

    def _register_custom_callbacks(self) -> None:
        pass

    def _unregister_custom_callbacks(self) -> None:
        pass

    def _handle_connected(self) -> None:
        if self._attr_native_value == self._default_off:
            self._attr_native_value = self._default_on
        self._schedule_state_update()

    def _handle_disconnected(self) -> None:
        self._attr_native_value = self._default_off
        self._schedule_state_update()

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        raise NotImplementedError


class HisenseVidaaActiveAppSensor(HisenseVidaaMqttTrackingSensor):
    """Sensor reporting the foreground active application."""

    _attr_translation_key = "active_app"
    _attr_icon = "mdi:application"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry, default_on="Standby", default_off="Off")
        self._attr_unique_id = f"{self._entry_id}_active_app"
        self._app_dict: dict[str, str] = {}
        self._app_icons: dict[str, str] = {}
        self._favorite_apps: list[str] = []

    def _register_custom_callbacks(self) -> None:
        self._client.register_applist_callback(self._handle_applist_update)

    def _unregister_custom_callbacks(self) -> None:
        self._client.unregister_applist_callback(self._handle_applist_update)

    def _handle_applist_update(self, apps: list[dict[str, Any]]) -> None:
        if not apps:
            return
        self._app_dict = {}
        self._app_icons = {}
        self._favorite_apps = []
        for a in apps:
            if isinstance(a, dict) and (a.get("appId") or a.get("app_id")):
                a_id = str(a.get("appId") or a.get("app_id", ""))
                name = a.get("appName") or a.get("name", "")
                if name:
                    self._app_dict[a_id] = name
                    if a.get("isFav") in (True, "true", 1, "1"):
                        self._favorite_apps.append(name)
                    icon_raw = a.get("httpIcon")
                    if icon_raw and "http" in icon_raw:
                        clean_url = "http" + icon_raw.split("http", 1)[1]
                        self._app_icons[name] = clean_url
                        self._app_icons[a_id] = clean_url
        self._schedule_state_update()

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        statetype = state.get("statetype")
        if statetype == "fake_sleep_0" or not self._client.connected:
            self._attr_native_value = "Off"
        elif statetype == "app":
            app_name = state.get("name") or state.get("appName")
            app_id = str(state.get("appId") or state.get("activeAppId") or "")
            self._attr_native_value = app_name or self._app_dict.get(app_id, "App")
        elif statetype == "livetv":
            self._attr_native_value = "Live TV"
        elif statetype == "sourceswitch":
            self._attr_native_value = "TV Input"
        elif statetype == "launcher":
            self._attr_native_value = "Home Launcher"
        else:
            app_id = str(state.get("appId") or state.get("activeAppId") or "")
            if app_id:
                self._attr_native_value = self._app_dict.get(app_id, app_id)
        self._schedule_state_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs: dict[str, Any] = {
            "total_installed_apps": len(self._app_dict),
        }
        if self._favorite_apps:
            attrs["favorite_apps"] = self._favorite_apps
        if self._attr_native_value and self._attr_native_value in self._app_icons:
            attrs["icon_url"] = self._app_icons[self._attr_native_value]
        return attrs

    @property
    def entity_picture(self) -> str | None:
        """Return dynamic high-res app artwork from VIDAA CDN."""
        if self._attr_native_value and self._attr_native_value in self._app_icons:
            return self._app_icons[self._attr_native_value]
        return None

    @property
    def icon(self) -> str:
        """Return dynamic MDI icon for the active app or state."""
        val = (self._attr_native_value or "").lower()
        if "netflix" in val:
            return "mdi:netflix"
        if "youtube" in val:
            return "mdi:youtube"
        if "spotify" in val:
            return "mdi:spotify"
        if "plex" in val:
            return "mdi:plex"
        if "disney" in val:
            return "mdi:movie-open"
        if "prime" in val or "amazon" in val:
            return "mdi:video"
        if "live tv" in val or val == "tv":
            return "mdi:television-box"
        if "home launcher" in val or "launcher" in val:
            return "mdi:view-dashboard"
        if "tv input" in val or "none" in val:
            return "mdi:video-input-hdmi"
        if "standby" in val:
            return "mdi:television-ambient-light"
        if "off" in val:
            return "mdi:television-off"
        return "mdi:application"


class HisenseVidaaActiveSourceSensor(HisenseVidaaMqttTrackingSensor):
    """Sensor reporting current physical input source."""

    _attr_translation_key = "active_source"
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry, default_on="None", default_off="Off")
        self._attr_unique_id = f"{self._entry_id}_active_source"
        self._available_sources: list[str] = []
        self._connected_inputs: list[str] = []
        self._custom_labels: dict[str, str] = {}

    def _register_custom_callbacks(self) -> None:
        self._client.register_sourcelist_callback(self._handle_sourcelist_update)

    def _unregister_custom_callbacks(self) -> None:
        self._client.unregister_sourcelist_callback(self._handle_sourcelist_update)

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        statetype = state.get("statetype")
        if statetype == "fake_sleep_0" or not self._client.connected:
            self._attr_native_value = "Off"
        elif statetype == "sourceswitch":
            self._attr_native_value = (
                state.get("sourcename")
                or state.get("sourceName")
                or state.get("displayname")
                or "HDMI"
            )
        elif statetype == "livetv":
            self._attr_native_value = "TV"
        elif statetype in ("app", "launcher"):
            self._attr_native_value = "None"
        elif state.get("sourcename") or state.get("sourceName"):
            self._attr_native_value = state.get("sourcename") or state.get("sourceName")
        self._schedule_state_update()

    def _handle_sourcelist_update(self, sources: list[dict[str, Any]]) -> None:
        self._available_sources = []
        self._connected_inputs = []
        self._custom_labels = {}
        for s in sources:
            if isinstance(s, dict):
                src_name = s.get("sourcename") or s.get("sourceName") or s.get("displayname") or s.get("name")
                if src_name:
                    self._available_sources.append(src_name)
                    if s.get("has_signal") in ("1", 1, True):
                        self._connected_inputs.append(src_name)
                    custom_label = s.get("displayname2")
                    if custom_label and str(custom_label).strip():
                        self._custom_labels[src_name] = str(custom_label).strip()

                if (
                    s.get("is_signal") in ("1", 1, True)
                    or s.get("is_active")
                    or s.get("isactive")
                    or s.get("active")
                ):
                    self._attr_native_value = src_name
        self._schedule_state_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs: dict[str, Any] = {}
        if self._available_sources:
            attrs["available_sources"] = self._available_sources
        if self._connected_inputs:
            attrs["connected_inputs"] = self._connected_inputs
        if self._custom_labels:
            attrs["custom_labels"] = self._custom_labels
        return attrs

    @property
    def icon(self) -> str:
        """Return dynamic MDI icon based on active input source."""
        val = (self._attr_native_value or "").lower()
        if "hdmi" in val:
            return "mdi:video-input-hdmi"
        if "tv" in val:
            return "mdi:television-classic"
        if "av" in val:
            return "mdi:video-input-component"
        if "off" in val:
            return "mdi:power-plug-off"
        return "mdi:video-input-hdmi"
