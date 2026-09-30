"""Diagnostic sensor entities for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory

from .const import AUTH_PROFILES, CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE
from .entity import HisenseVidaaEntity

if TYPE_CHECKING:
    from .client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaBaseSensor(HisenseVidaaEntity, SensorEntity):
    """Base class for Hisense VIDAA sensors with safe state scheduling."""

    def _schedule_state_update(self) -> None:
        """Safely schedule state update if entity is added to hass."""
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()


class HisenseVidaaSessionStatusSensor(HisenseVidaaBaseSensor):
    """Sensor displaying current authentication and session status."""

    _attr_translation_key = "session_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_session_status"
        self._reauth_required = False
        self._update_state()

    async def async_added_to_hass(self) -> None:
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_disconnected_callback(self._handle_disconnected)
        self._client.register_token_refreshed_callback(self._handle_state_change)
        self._client.register_auth_failed_callback(self._handle_auth_failed)
        self._update_state()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_disconnected_callback(self._handle_disconnected)
        self._client.unregister_token_refreshed_callback(self._handle_state_change)
        self._client.unregister_auth_failed_callback(self._handle_auth_failed)

    def _handle_state_change(self, *args: Any) -> None:
        self._update_state()
        self._schedule_state_update()

    def _handle_connected(self, *args: Any) -> None:
        # A successful (re)connect clears the reauth latch.
        self._reauth_required = False
        self._update_state()
        self._schedule_state_update()

    def _handle_disconnected(self, *args: Any) -> None:
        # Must NOT overwrite a pending "Reauth Required" state.
        self._update_state()
        self._schedule_state_update()

    def _handle_auth_failed(self, client: HisenseTvClient) -> None:
        self._reauth_required = True
        self._attr_native_value = "Reauth Required"
        self._attr_icon = "mdi:shield-alert"
        self._schedule_state_update()

    def _update_state(self) -> None:
        if self._reauth_required:
            self._attr_native_value = "Reauth Required"
            self._attr_icon = "mdi:shield-alert"
        elif self._client.connected:
            self._attr_native_value = "Active"
            self._attr_icon = "mdi:shield-check"
        else:
            self._attr_native_value = "Standby"
            self._attr_icon = "mdi:shield-lock-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic session details."""
        attrs: dict[str, Any] = {
            "client_id": self._client.client_id,
            "auth_profile": self._client.auth_profile,
            "encryption": "TLSv1.2 (Port 36669)" if self._client.use_ssl else "Unencrypted (Port 36669)",
            "local_only": True,
        }
        if self._client.access_token_time:
            attrs["paired_at"] = datetime.fromtimestamp(self._client.access_token_time, tz=UTC).isoformat()
            if self._client.access_token_duration:
                exp = self._client.access_token_time + (self._client.access_token_duration * 86400)
                attrs["access_token_expires_at"] = datetime.fromtimestamp(exp, tz=UTC).isoformat()
        if self._client.refresh_token_time and self._client.refresh_token_duration:
            exp = self._client.refresh_token_time + (self._client.refresh_token_duration * 86400)
            attrs["refresh_token_expires_at"] = datetime.fromtimestamp(exp, tz=UTC).isoformat()
        return attrs


class HisenseVidaaAuthProfileSensor(HisenseVidaaBaseSensor):
    """Sensor displaying configured authentication profile."""

    _attr_translation_key = "auth_profile"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_auth_profile"
        key = self._options.get(
            CONF_AUTH_PROFILE,
            entry.data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE),
        )
        self._attr_native_value = AUTH_PROFILES.get(key, key.title())


class HisenseVidaaReportedNameSensor(HisenseVidaaBaseSensor):
    """Sensor displaying live reported friendly TV name and system hardware details."""

    _attr_translation_key = "reported_name"
    _attr_icon = "mdi:television-guide"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_reported_name"
        self._update_value()

    async def async_added_to_hass(self) -> None:
        self._client.register_connected_callback(self._handle_update)
        self._client.register_state_callback(self._handle_state_or_info)
        self._client.register_device_info_callback(self._handle_update)
        self._client.register_disconnected_callback(self._handle_update)
        self._update_value()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_connected_callback(self._handle_update)
        self._client.unregister_state_callback(self._handle_state_or_info)
        self._client.unregister_device_info_callback(self._handle_update)
        self._client.unregister_disconnected_callback(self._handle_update)

    def _handle_state_or_info(self, data: dict[str, Any]) -> None:
        if isinstance(data, dict) and any(
            k in data for k in ("devicename", "device_name", "friendly_name", "tv_name", "name")
        ):
            self._update_value()
            self._schedule_state_update()

    def _handle_update(self, *args: Any) -> None:
        self._update_value()
        self._schedule_state_update()

    def _handle_device_info(self, *args: Any) -> None:
        self._handle_update(*args)

    def _update_value(self) -> None:
        self._attr_native_value = (
            getattr(self._client, "device_name", None)
            or (self._entry.title if self._entry else None)
            or getattr(self._client, "name", None)
            or f"Hisense TV ({self._client.ip})"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic device details."""
        attrs: dict[str, Any] = {"ip_address": self._client.ip}
        if self._mac:
            attrs["mac_address"] = self._mac
        if self._client.model_name or self._model:
            attrs["model_name"] = self._client.model_name or self._model
        if self._client.manufacturer or self._manufacturer:
            attrs["manufacturer"] = self._client.manufacturer or self._manufacturer
        if self._client.firmware_version or self._sw_version:
            attrs["firmware_version"] = self._client.firmware_version or self._sw_version
        return attrs


class HisenseVidaaAudioOutputSensor(HisenseVidaaEntity, SensorEntity):
    """Sensor reporting active audio output (TV Speakers vs ARC/eARC)."""

    _attr_translation_key = "audio_output"
    _attr_icon = "mdi:audio-video"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: HisenseTvClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_audio_output"
        self._attr_native_value = "TV Speakers" if client.connected else "Off"

    def _schedule_state_update(self) -> None:
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_volume_callback(self._handle_volume_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_volume_callback(self._handle_volume_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)

    def _handle_connected(self) -> None:
        if self._attr_native_value == "Off":
            self._attr_native_value = "TV Speakers"
        self._schedule_state_update()

    def _handle_disconnected(self) -> None:
        self._attr_native_value = "Off"
        self._schedule_state_update()

    def _handle_volume_update(self, data: dict[str, Any]) -> None:
        if isinstance(data, dict):
            vol_type = data.get("volume_type")
            if vol_type in (1, "1"):
                self._attr_native_value = "ARC / eARC"
            elif vol_type in (0, "0"):
                self._attr_native_value = "TV Speakers"
            self._schedule_state_update()

    def _handle_state_update(self, state: dict[str, Any]) -> None:
        if isinstance(state, dict) and (state.get("statetype") == "fake_sleep_0" or not self._client.connected):
            self._attr_native_value = "Off"
            self._schedule_state_update()
