"""Operational and metadata sensors for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..client import VidaaClient
from ..tv.media import parse_applist_payload, parse_sourcelist_payload
from ..tv.navigation import get_app_icon, get_source_icon
from .diagnostic import (
    HisenseVidaaAudioOutputSensor,
    HisenseVidaaAuthProfileSensor,
    HisenseVidaaBaseSensor,
    HisenseVidaaBrandProfileSensor,
    HisenseVidaaClockDriftSensor,
    HisenseVidaaReportedNameSensor,
    HisenseVidaaSessionStatusSensor,
    VidaaAudioOutputSensor,
    VidaaAuthProfileSensor,
    VidaaBaseSensor,
    VidaaBrandProfileSensor,
    VidaaClockDriftSensor,
    VidaaReportedNameSensor,
    VidaaSessionStatusSensor,
)

if TYPE_CHECKING:
    from .. import VidaaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

__all__ = [
    "HisenseVidaaActiveAppSensor",
    "HisenseVidaaActiveSourceSensor",
    "HisenseVidaaAudioOutputSensor",
    "HisenseVidaaAuthProfileSensor",
    "HisenseVidaaBaseSensor",
    "HisenseVidaaBrandProfileSensor",
    "HisenseVidaaClockDriftSensor",
    "HisenseVidaaMqttTrackingSensor",
    "HisenseVidaaReportedNameSensor",
    "HisenseVidaaSessionStatusSensor",
    "VidaaActiveAppSensor",
    "VidaaActiveSourceSensor",
    "VidaaAudioOutputSensor",
    "VidaaAuthProfileSensor",
    "VidaaBaseSensor",
    "VidaaBrandProfileSensor",
    "VidaaClockDriftSensor",
    "VidaaMqttTrackingSensor",
    "VidaaReportedNameSensor",
    "VidaaSessionStatusSensor",
    "async_setup_entry",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VidaaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VIDAA sensors based on a config entry."""
    client: VidaaClient = entry.runtime_data.client
    async_add_entities([
        VidaaSessionStatusSensor(client, entry),
        VidaaReportedNameSensor(client, entry),
        VidaaActiveAppSensor(client, entry),
        VidaaActiveSourceSensor(client, entry),
        VidaaAudioOutputSensor(client, entry),
        VidaaClockDriftSensor(client, entry),
    ])


class VidaaMqttTrackingSensor(VidaaBaseSensor):
    """Base class for sensors tracking live MQTT state and connection events."""

    def __init__(self, client: VidaaClient, entry: ConfigEntry, default_on: str, default_off: str = "Off") -> None:
        super().__init__(client, entry)
        self._default_on = default_on
        self._default_off = default_off
        if not client.connected:
            self._attr_native_value = default_off
        elif not client.is_on and default_on != "Standby":
            self._attr_native_value = "Standby"
        else:
            self._attr_native_value = default_on

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
            if not self._client.is_on and self._default_on != "Standby":
                self._attr_native_value = "Standby"
            else:
                self._attr_native_value = self._default_on
        self._schedule_state_update()

    def _handle_disconnected(self) -> None:
        self._attr_native_value = self._default_off
        self._schedule_state_update()

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        raise NotImplementedError


class VidaaActiveAppSensor(VidaaMqttTrackingSensor):
    """Sensor reporting the foreground active application."""

    _attr_translation_key = "active_app"
    _attr_icon = "mdi:application"

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry, default_on="Standby", default_off="Off")
        self._attr_unique_id = f"{self._entry_id}_active_app"
        self._app_dict: dict[str, str] = {}
        self._app_icons: dict[str, str] = {}
        self._favorite_apps: list[str] = []
        self._last_known_app: str | None = None

    def _register_custom_callbacks(self) -> None:
        self._client.register_applist_callback(self._handle_applist_update)

    def _unregister_custom_callbacks(self) -> None:
        self._client.unregister_applist_callback(self._handle_applist_update)

    def _handle_applist_update(self, apps: list[dict[str, Any]]) -> None:
        if apps:
            self._app_dict, self._app_icons, self._favorite_apps = parse_applist_payload(apps)
            self._schedule_state_update()

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return
        statetype = state.get("statetype")
        if not self._client.connected:
            self._attr_native_value = "Off"
        elif statetype == "fake_sleep_0" or not self._client.is_on:
            self._attr_native_value = "Standby"
        elif statetype == "app":
            name = state.get("name") or state.get("appName")
            app_id = str(state.get("appId") or state.get("activeAppId") or "")
            self._attr_native_value = name or self._app_dict.get(app_id, "App")
            self._last_known_app = self._attr_native_value
        elif statetype == "livetv":
            self._attr_native_value = "Live TV"
            self._last_known_app = "Live TV"
        elif statetype == "sourceswitch":
            self._attr_native_value = "TV Input"
        elif statetype in ("launcher", "remote_launcher"):
            self._attr_native_value = "Home Launcher"
            self._last_known_app = "Home Launcher"
        else:
            app_id = str(state.get("appId") or state.get("activeAppId") or "")
            if app_id:
                self._attr_native_value = self._app_dict.get(app_id, app_id)
                self._last_known_app = self._attr_native_value
        self._schedule_state_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs: dict[str, Any] = {"total_installed_apps": len(self._app_dict)}
        if self._last_known_app:
            attrs["last_known_app"] = self._last_known_app
        if self._favorite_apps:
            attrs["favorite_apps"] = self._favorite_apps
        if self._attr_native_value and self._attr_native_value in self._app_icons:
            attrs["icon_url"] = self._app_icons[self._attr_native_value]
        return attrs

    @property
    def entity_picture(self) -> str | None:
        """Return dynamic app icon artwork."""
        return self._app_icons.get(self._attr_native_value) if self._attr_native_value else None

    @property
    def icon(self) -> str:
        """Return dynamic MDI icon for the active app or state."""
        return get_app_icon(self._attr_native_value)


class VidaaActiveSourceSensor(VidaaMqttTrackingSensor):
    """Sensor reporting current physical input source."""

    _attr_translation_key = "active_source"
    _attr_icon = "mdi:video-input-hdmi"

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry, default_on="Standby", default_off="Off")
        self._attr_unique_id = f"{self._entry_id}_active_source"
        self._available_sources: list[str] = []
        self._connected_inputs: list[str] = []
        self._custom_labels: dict[str, str] = {}
        self._connected_device: str | None = None
        self._channel_name: str | None = None
        self._channel_num: str | None = None
        self._last_known_source: str | None = None

    def _register_custom_callbacks(self) -> None:
        self._client.register_sourcelist_callback(self._handle_sourcelist_update)

    def _unregister_custom_callbacks(self) -> None:
        self._client.unregister_sourcelist_callback(self._handle_sourcelist_update)

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        statetype = state.get("statetype")
        if not self._client.connected:
            self._attr_native_value = "Off"
            self._connected_device = self._channel_name = self._channel_num = None
        elif statetype == "fake_sleep_0" or not self._client.is_on:
            self._attr_native_value = "Standby"
            self._connected_device = self._channel_name = self._channel_num = None
        elif statetype == "sourceswitch":
            self._attr_native_value = state.get("sourcename") or state.get("sourceName") or state.get("displayname") or "HDMI"
            self._last_known_source = self._attr_native_value
            self._connected_device = (
                state.get("displayname2")
                or state.get("source_detail")
                or self._custom_labels.get(self._attr_native_value)
            )
            self._channel_name = self._channel_num = None
        elif statetype == "livetv":
            self._attr_native_value = "TV"
            self._last_known_source = "TV"
            self._connected_device = None
            self._channel_name = state.get("channel_name")
            self._channel_num = state.get("channel_num")
        elif statetype in ("app", "launcher", "remote_launcher"):
            self._attr_native_value = "None"
            self._connected_device = self._channel_name = self._channel_num = None
        elif state.get("sourcename") or state.get("sourceName"):
            self._attr_native_value = state.get("sourcename") or state.get("sourceName")
            self._last_known_source = self._attr_native_value
            self._connected_device = (
                state.get("displayname2")
                or state.get("source_detail")
                or self._custom_labels.get(self._attr_native_value)
            )
        self._schedule_state_update()

    def _handle_sourcelist_update(self, sources: list[dict[str, Any]]) -> None:
        if sources:
            self._available_sources, self._connected_inputs, self._custom_labels, active_src = parse_sourcelist_payload(sources)
            if active_src:
                self._last_known_source = active_src
                if self._client.connected and self._client.is_on:
                    self._attr_native_value = active_src
            if (
                self._attr_native_value
                and self._attr_native_value in self._custom_labels
                and not self._connected_device
            ):
                self._connected_device = self._custom_labels[self._attr_native_value]
            self._schedule_state_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs: dict[str, Any] = {}
        if self._attr_native_value and self._attr_native_value not in ("Off", "Standby", "None"):
            attrs["raw_source"] = self._attr_native_value
            if self._connected_device and "hdmi" in str(self._attr_native_value).lower():
                attrs["display_name"] = f"{self._attr_native_value} ({self._connected_device})"
        if self._last_known_source:
            attrs["last_known_source"] = self._last_known_source
        for key, val in (
            ("available_sources", self._available_sources),
            ("connected_inputs", self._connected_inputs),
            ("custom_labels", self._custom_labels),
            ("connected_device", self._connected_device),
            ("channel_name", self._channel_name),
            ("channel_num", self._channel_num),
        ):
            if val:
                attrs[key] = val
        return attrs

    @property
    def icon(self) -> str:
        """Return dynamic MDI icon based on active input source."""
        return get_source_icon(self._attr_native_value)


# Backwards-compatible aliases during migration
HisenseVidaaMqttTrackingSensor = VidaaMqttTrackingSensor
HisenseVidaaActiveAppSensor = VidaaActiveAppSensor
HisenseVidaaActiveSourceSensor = VidaaActiveSourceSensor
