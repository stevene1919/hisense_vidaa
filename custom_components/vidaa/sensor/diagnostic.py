"""Diagnostic sensor entities for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime

from ..const import (
    AUTH_PROFILES,
    BRAND_MAP,
    BRAND_PROFILES,
    CONF_AUTH_PROFILE,
    CONF_BRAND,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_BRAND,
    DEFAULT_BRAND_OPTION,
)
from ..entity import VidaaEntity
from ..tv.fingerprint import format_drift_human

if TYPE_CHECKING:
    from ..client import VidaaClient

_LOGGER = logging.getLogger(__name__)


class VidaaBaseSensor(VidaaEntity, SensorEntity):
    """Base class for VIDAA sensors with safe state scheduling."""

    def _schedule_state_update(self) -> None:
        """Safely schedule state update if entity is added to hass."""
        if getattr(self, "hass", None) is not None:
            self.schedule_update_ha_state()


class VidaaSessionStatusSensor(VidaaBaseSensor):
    """Sensor displaying current authentication and session status."""

    _attr_translation_key = "session_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_session_status"
        self._reauth_required = False
        self._update_state()

    async def async_added_to_hass(self) -> None:
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_disconnected_callback(self._handle_disconnected)
        self._client.register_token_refreshed_callback(self._handle_state_change)
        self._client.register_auth_failed_callback(self._handle_auth_failed)
        self._client.register_device_info_callback(self._handle_state_change)
        self._update_state()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_disconnected_callback(self._handle_disconnected)
        self._client.unregister_token_refreshed_callback(self._handle_state_change)
        self._client.unregister_auth_failed_callback(self._handle_auth_failed)
        self._client.unregister_device_info_callback(self._handle_state_change)

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

    def _handle_auth_failed(self, client: VidaaClient) -> None:
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
        """Return diagnostic session and profile details."""
        raw_cid = self._client.client_id or ""
        masked_cid = f"{raw_cid[:8]}...{raw_cid[-4:]}" if len(raw_cid) > 12 else raw_cid
        entry_data = getattr(self._entry, "data", None)
        data_dict = entry_data if isinstance(entry_data, dict) else {}
        opts_dict = self._options if isinstance(self._options, dict) else {}

        auth_key = opts_dict.get(
            CONF_AUTH_PROFILE,
            data_dict.get(CONF_AUTH_PROFILE, getattr(self._client, "auth_profile", DEFAULT_AUTH_PROFILE)),
        )
        brand_key = opts_dict.get(
            CONF_BRAND,
            data_dict.get("brand_profile", data_dict.get(CONF_BRAND, DEFAULT_BRAND_OPTION)),
        )
        active_code = getattr(self._client, "brand", None)
        if not isinstance(active_code, str) or not active_code:
            active_code = data_dict.get(CONF_BRAND, DEFAULT_BRAND)
        if active_code == "auto":
            active_code = data_dict.get("resolved_brand", DEFAULT_BRAND)

        attrs: dict[str, Any] = {
            "client_id": masked_cid,
            "auth_profile": self._client.auth_profile,
            "configured_auth_profile": AUTH_PROFILES.get(str(auth_key), str(auth_key).title() if auth_key else "Auto"),
            "brand_profile": BRAND_PROFILES.get(str(brand_key), str(brand_key).title() if brand_key else "Auto"),
            "active_brand": BRAND_MAP.get(str(active_code), str(active_code).upper() if active_code else "Hisense"),
            "encryption": "TLSv1.2 (Port 36669)" if self._client.use_ssl else "Unencrypted (Port 36669)",
            "local_only": True,
        }
        offset = getattr(self._client, "clock_offset", 0) or 0
        if self._client.access_token_time:
            attrs["paired_at"] = datetime.fromtimestamp(self._client.access_token_time - offset, tz=UTC).isoformat()
            if self._client.access_token_duration:
                exp = (self._client.access_token_time + (self._client.access_token_duration * 86400)) - offset
                attrs["access_token_expires_at"] = datetime.fromtimestamp(exp, tz=UTC).isoformat()
        if self._client.refresh_token_time and self._client.refresh_token_duration:
            exp = (self._client.refresh_token_time + (self._client.refresh_token_duration * 86400)) - offset
            attrs["refresh_token_expires_at"] = datetime.fromtimestamp(exp, tz=UTC).isoformat()
        return attrs


class VidaaReportedNameSensor(VidaaBaseSensor):
    """Sensor displaying live reported friendly TV name and system hardware details."""

    _attr_translation_key = "reported_name"
    _attr_icon = "mdi:television-guide"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
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
        brand_code = getattr(self._client, "brand", DEFAULT_BRAND) or DEFAULT_BRAND
        brand_name = BRAND_MAP.get(brand_code, "VIDAA")
        self._attr_native_value = (
            getattr(self._client, "device_name", None)
            or (self._entry.title if self._entry else None)
            or getattr(self._client, "name", None)
            or f"{brand_name} TV ({self._client.ip})"
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


class VidaaClockDriftSensor(VidaaBaseSensor):
    """Sensor displaying TV internal clock drift relative to host time."""

    _attr_translation_key = "clock_drift"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_entity_registry_enabled_default = False

    def __init__(self, client: VidaaClient, entry: ConfigEntry) -> None:
        super().__init__(client, entry)
        self._attr_unique_id = f"{self._entry_id}_clock_drift"
        self._update_state()

    async def async_added_to_hass(self) -> None:
        self._client.register_connected_callback(self._handle_update)
        self._client.register_clock_drift_callback(self._handle_update)
        self._client.register_disconnected_callback(self._handle_update)
        self._update_state()

    async def async_will_remove_from_hass(self) -> None:
        self._client.unregister_connected_callback(self._handle_update)
        self._client.unregister_clock_drift_callback(self._handle_update)
        self._client.unregister_disconnected_callback(self._handle_update)

    def _handle_update(self, *args: Any) -> None:
        self._update_state()
        self._schedule_state_update()

    def _update_state(self) -> None:
        offset = getattr(self._client, "clock_offset", 0)
        if offset is None:
            self._attr_native_value = None
            self._attr_icon = "mdi:clock-outline"
            return
        self._attr_native_value = offset
        if abs(offset) < 60:
            self._attr_icon = "mdi:clock-check-outline"
        else:
            self._attr_icon = "mdi:clock-alert-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic clock details."""
        offset = getattr(self._client, "clock_offset", 0)
        if offset is None:
            return {
                "drift_seconds": None,
                "synchronized": False,
                "drift_human": "Unknown",
                "host_time": datetime.now(UTC).isoformat(),
            }
        now_ts = int(datetime.now(UTC).timestamp())
        tv_ts = getattr(self._client, "tv_timestamp", None)
        if tv_ts is None and offset != 0:
            tv_ts = now_ts + offset

        attrs: dict[str, Any] = {
            "drift_seconds": offset,
            "synchronized": abs(offset) < 60,
        }

        attrs["drift_human"] = format_drift_human(offset)

        if tv_ts:
            attrs["tv_time"] = datetime.fromtimestamp(tv_ts, tz=UTC).isoformat()
        attrs["host_time"] = datetime.now(UTC).isoformat()

        last_sync = getattr(self._client, "last_clock_sync", 0.0)
        if last_sync:
            attrs["last_synced"] = datetime.fromtimestamp(last_sync, tz=UTC).isoformat()

        return attrs


# Backwards-compatible aliases during migration
HisenseVidaaBaseSensor = VidaaBaseSensor
HisenseVidaaSessionStatusSensor = VidaaSessionStatusSensor
HisenseVidaaReportedNameSensor = VidaaReportedNameSensor
HisenseVidaaClockDriftSensor = VidaaClockDriftSensor
