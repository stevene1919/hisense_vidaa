"""Hisense VIDAA TV custom component integration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.trigger import PluggableAction

from .client import HisenseTvClient, VidaaClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_BRAND,
    CONF_CERTFILE,
    CONF_CLIENT_ID,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_REFRESH_IN_STANDBY,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_SW_VERSION,
    CONF_USE_SSL,
    CONF_USERNAME,
    DEFAULT_BRAND,
    DEFAULT_BRAND_OPTION,
    DEFAULT_ENABLE_NOTIFY,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_REFRESH_IN_STANDBY,
    DEFAULT_USE_SSL,
    DOMAIN,
    LEGACY_DOMAIN,
)
from .protocol import resolve_ca_certificate, resolve_certificates
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "media_player",
    "remote",
    "sensor",
    "binary_sensor",
    "button",
    "switch",
    "notify",
    "select",
    "number",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
DEFAULT_CLOCK_SYNC_INTERVAL = timedelta(hours=2)


@dataclass
class VidaaData:
    """Runtime data for VIDAA Smart TV integration."""

    client: VidaaClient
    platforms: list[str]
    options: dict[str, Any]
    turn_on: PluggableAction | None = None


# Backwards-compatible alias during migration
HisenseVidaaData = VidaaData

type VidaaConfigEntry = ConfigEntry[VidaaData]
type HisenseVidaaConfigEntry = VidaaConfigEntry


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry to new configuration version."""
    _LOGGER.debug(
        "Migrating config entry '%s' from version %s.%s",
        entry.title,
        entry.version,
        entry.minor_version,
    )

    if entry.version == 1:
        # Migrate entity registry if needed
        try:
            ent_reg = er.async_get(hass)
            entities: list[Any] = []
            if hasattr(er, "async_entries_for_config_entry"):
                entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            elif hasattr(ent_reg, "entities"):
                if hasattr(ent_reg.entities, "get_entries_for_config_entry_id"):
                    entities = list(ent_reg.entities.get_entries_for_config_entry_id(entry.entry_id))
                elif isinstance(ent_reg.entities, dict):
                    entities = [e for e in ent_reg.entities.values() if getattr(e, "config_entry_id", None) == entry.entry_id]
            for reg_entry in entities:
                if getattr(reg_entry, "platform", None) == LEGACY_DOMAIN:
                    object.__setattr__(reg_entry, "platform", DOMAIN)
        except Exception as err:
            _LOGGER.debug("Non-fatal error migrating entity registry entries: %s", err)

        # Migrate device registry identifiers
        try:
            dev_reg = dr.async_get(hass)
            device = dev_reg.async_get_device(identifiers={(LEGACY_DOMAIN, entry.entry_id)})
            if device:
                dev_reg.async_update_device(
                    device.id,
                    merge_identifiers={(DOMAIN, entry.entry_id), (LEGACY_DOMAIN, entry.entry_id)},
                )
        except Exception as err:
            _LOGGER.debug("Non-fatal error updating device registry: %s", err)

        # Migrate domain attribute if still legacy
        if getattr(entry, "domain", None) == LEGACY_DOMAIN:
            object.__setattr__(entry, "domain", DOMAIN)

        hass.config_entries.async_update_entry(
            entry,
            version=2,
            minor_version=1,
        )
        _LOGGER.info(
            "Successfully migrated config entry '%s' to version 2.1",
            entry.title,
        )

    return True


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the VIDAA Smart TV integration services."""
    await async_setup_services(hass)

    # Automatically check for and migrate any remaining legacy entries
    if hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_entries"):
        for legacy_entry in hass.config_entries.async_entries(LEGACY_DOMAIN):
            _LOGGER.info("Found legacy %s config entry '%s'; migrating to %s", LEGACY_DOMAIN, legacy_entry.title, DOMAIN)
            await async_migrate_entry(hass, legacy_entry)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HisenseVidaaConfigEntry) -> bool:
    """Set up VIDAA Smart TV from a config entry."""
    version = getattr(entry, "version", None)
    if isinstance(version, int) and version < 2:
        await async_migrate_entry(hass, entry)

    # [F2-leg2/F2-leg4/F2-leg6]: services are registered by async_setup, but
    # async_unload_entry removes them once the last entry goes away and
    # async_setup is never called again (e.g. after an options reload).  Keep
    # the registration idempotent and re-assert it on every setup.
    await async_setup_services(hass)

    data = entry.data
    mac = data.get(CONF_MAC_ADDRESS)
    if not mac:
        try:
            from homeassistant.helpers.device_registry import format_mac

            from .tv.fingerprint import get_arp_mac

            raw_mac = await hass.async_add_executor_job(
                get_arp_mac, data[CONF_IP_ADDRESS]
            )
            if raw_mac:
                mac = format_mac(raw_mac)
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_MAC_ADDRESS: mac},
                    unique_id=entry.unique_id or mac,
                )
        except Exception:
            pass

    use_ssl = entry.options.get(CONF_USE_SSL, data.get(CONF_USE_SSL, DEFAULT_USE_SSL))
    certfile = entry.options.get(CONF_CERTFILE, data.get(CONF_CERTFILE))
    keyfile = entry.options.get(CONF_KEYFILE, data.get(CONF_KEYFILE))
    auth_profile = entry.options.get(CONF_AUTH_PROFILE, data.get(CONF_AUTH_PROFILE, "auto"))

    ca_cert = None
    if use_ssl and auth_profile not in ("legacy", "static"):
        certfile, keyfile = await hass.async_add_executor_job(
            resolve_certificates, auth_profile, certfile, keyfile
        )
        ca_cert = await hass.async_add_executor_job(
            resolve_ca_certificate, None
        )

    brand_pref = entry.options.get(CONF_BRAND, data.get(CONF_BRAND, DEFAULT_BRAND_OPTION))
    if brand_pref == "auto":
        client_brand = data.get("resolved_brand") or data.get("detected_brand") or DEFAULT_BRAND
    else:
        client_brand = brand_pref

    client = HisenseTvClient(
        ip=data[CONF_IP_ADDRESS],
        mac=mac,
        client_id=data.get(CONF_CLIENT_ID),
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        access_token=data.get(CONF_ACCESS_TOKEN),
        access_token_time=data.get(CONF_ACCESS_TOKEN_TIME),
        access_token_duration=data.get(CONF_ACCESS_TOKEN_DURATION),
        refresh_token=data.get(CONF_REFRESH_TOKEN),
        refresh_token_time=data.get(CONF_REFRESH_TOKEN_TIME),
        refresh_token_duration=data.get(CONF_REFRESH_TOKEN_DURATION),
        auth_profile=auth_profile,
        refresh_in_standby=entry.options.get(CONF_REFRESH_IN_STANDBY, DEFAULT_REFRESH_IN_STANDBY),
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        use_ssl=use_ssl,
        brand=client_brand,
        session=async_get_clientsession(hass),
    )
    client._loop = hass.loop

    brand_changed = (
        (brand_pref != "auto" and client.brand != data.get(CONF_BRAND))
        or (brand_pref == "auto" and client.brand != data.get("resolved_brand"))
    )
    if client.client_id != data.get(CONF_CLIENT_ID) or brand_changed:
        new_data = {
            **data,
            CONF_CLIENT_ID: client.client_id,
            CONF_USERNAME: client.username,
            CONF_PASSWORD: client.password,
            CONF_ACCESS_TOKEN: client.access_token,
            CONF_REFRESH_TOKEN: client.refresh_token,
        }
        if brand_pref == "auto":
            new_data["resolved_brand"] = client.brand
        else:
            new_data[CONF_BRAND] = client.brand
            new_data["resolved_brand"] = client.brand
        hass.config_entries.async_update_entry(entry, data=new_data)
        data = new_data

    # Check for missing certificates off the event loop and manage Repairs issue
    certs_valid = (
        await hass.async_add_executor_job(
            lambda: bool(
                client.certfile
                and client.keyfile
                and os.path.isfile(client.certfile)
                and os.path.isfile(client.keyfile)
            )
        )
        if use_ssl
        else True
    )

    if use_ssl and not certs_valid:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"certificate_missing_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="certificate_missing",
            data={"entry_id": entry.entry_id},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, f"certificate_missing_{entry.entry_id}")

    # Callback to persist token updates in Home Assistant config entry
    def update_entry_tokens(refreshed_client: HisenseTvClient) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: refreshed_client.access_token,
                CONF_ACCESS_TOKEN_TIME: refreshed_client.access_token_time,
                CONF_ACCESS_TOKEN_DURATION: refreshed_client.access_token_duration,
                CONF_REFRESH_TOKEN: refreshed_client.refresh_token,
                CONF_REFRESH_TOKEN_TIME: refreshed_client.refresh_token_time,
                CONF_REFRESH_TOKEN_DURATION: refreshed_client.refresh_token_duration,
            },
        )

    client.register_token_refreshed_callback(update_entry_tokens)

    def _handle_auth_failed(failed_client: HisenseTvClient) -> None:
        """Raise a persistent Repairs issue and start the reauth flow."""
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"auth_token_invalidated_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="auth_token_invalidated",
            translation_placeholders={"ip_address": failed_client.ip},
            # [F5-leg2/F6-leg6]: gives the fix flow the entry it must re-pair.
            data={"entry_id": entry.entry_id},
        )
        entry.async_start_reauth(hass)

    client.register_auth_failed_callback(_handle_auth_failed)

    if not client.access_token or not client.client_id or not client.username:
        _LOGGER.warning(
            "[%s] Missing credentials or authentication tokens; starting reauthentication",
            client.ip,
        )
        _handle_auth_failed(client)
    else:
        # Check and refresh tokens
        updated = await client.async_check_and_refresh_token()
        if updated:
            update_entry_tokens(client)

    # Start running background task for MQTT client
    platforms_to_setup = [
        "media_player",
        "sensor",
        "binary_sensor",
        "button",
        "switch",
        "select",
    ]
    entity_reg = er.async_get(hass)

    # Prune retired diagnostic sensors (Brand Profile and Auth Profile are consolidated into media_player attributes)
    for suffix in ("brand_profile", "auth_profile"):
        unique_id = f"{entry.entry_id}_{suffix}"
        if entity_id := entity_reg.async_get_entity_id("sensor", DOMAIN, unique_id):
            entity_reg.async_remove(entity_id)
    if entry.options.get(
        CONF_ENABLE_PICTURE_CONTROLS, DEFAULT_ENABLE_PICTURE_CONTROLS
    ):
        platforms_to_setup.append("number")
    else:
        for suffix in ("backlight", "brightness", "contrast"):
            unique_id = f"{entry.entry_id}_{suffix}"
            if entity_id := entity_reg.async_get_entity_id("number", DOMAIN, unique_id):
                entity_reg.async_remove(entity_id)

    if entry.options.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE):
        platforms_to_setup.append("remote")
    else:
        unique_id = f"{entry.entry_id}_remote"
        if entity_id := entity_reg.async_get_entity_id("remote", DOMAIN, unique_id):
            entity_reg.async_remove(entity_id)

    if entry.options.get(
        CONF_ENABLE_NOTIFY,
        getattr(client, "has_notifications", DEFAULT_ENABLE_NOTIFY),
    ):
        platforms_to_setup.append("notify")
    else:
        unique_id = f"{entry.entry_id}_notify"
        if entity_id := entity_reg.async_get_entity_id("notify", DOMAIN, unique_id):
            entity_reg.async_remove(entity_id)

    # Connect to MQTT broker
    try:
        await client.async_connect_and_run()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to Hisense TV at {client.ip}: {err}"
        ) from err

    entry.runtime_data = HisenseVidaaData(
        client=client,
        platforms=platforms_to_setup,
        options=dict(entry.options),
        turn_on=PluggableAction(),
    )

    await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Periodic background TV clock synchronization
    async def _async_sync_tv_clock(_now: Any = None) -> None:
        """Periodically syncs the TV UPnP hardware clock."""
        if not client.connected or not client.is_on:
            return
        try:
            await client.async_sync_clock(2.0)
        except Exception as err:
            _LOGGER.debug("[%s] Periodic clock sync failed: %s", client.ip, err)

    entry.async_on_unload(
        async_track_time_interval(hass, _async_sync_tv_clock, DEFAULT_CLOCK_SYNC_INTERVAL)
    )

    # Wake transition clock synchronization
    last_power_state = [client.is_on]

    def _on_state_change(_state: dict[str, Any]) -> None:
        was_on = last_power_state[0]
        now_on = client.is_on
        last_power_state[0] = now_on
        if not was_on and now_on:
            hass.async_create_background_task(
                _async_sync_tv_clock(),
                f"vidaa_wake_clock_sync_{entry.entry_id}",
            )

    client.register_state_callback(_on_state_change)
    entry.async_on_unload(lambda: client.unregister_state_callback(_on_state_change))

    # Live MQTT device registry enrichment callback
    def _on_device_info_update(_data: dict[str, Any]) -> None:
        try:
            from homeassistant.helpers import device_registry as dr

            dev_reg = dr.async_get(hass)
            device = None
            if hasattr(dev_reg, "async_get_device_by_identifier"):
                device = dev_reg.async_get_device_by_identifier(
                    (DOMAIN, entry.entry_id), entry.entry_id
                )
            if not device and hasattr(dev_reg, "async_get_device"):
                device = dev_reg.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
            if device:
                updates: dict[str, Any] = {}
                if client.model_name and client.model_name != device.model:
                    updates["model"] = client.model_name
                if client.manufacturer and client.manufacturer != device.manufacturer:
                    updates["manufacturer"] = client.manufacturer
                if client.firmware_version and client.firmware_version != device.sw_version:
                    updates["sw_version"] = client.firmware_version
                if updates:
                    dev_reg.async_update_device(device.id, **updates)
                    new_data = dict(entry.data)
                    data_changed = False
                    if "model" in updates and updates["model"] != new_data.get(CONF_MODEL):
                        new_data[CONF_MODEL] = updates["model"]
                        data_changed = True
                    if "manufacturer" in updates and updates["manufacturer"] != new_data.get(CONF_MANUFACTURER):
                        new_data[CONF_MANUFACTURER] = updates["manufacturer"]
                        data_changed = True
                    if "sw_version" in updates and updates["sw_version"] != new_data.get(CONF_SW_VERSION):
                        new_data[CONF_SW_VERSION] = updates["sw_version"]
                        data_changed = True
                    if data_changed:
                        hass.config_entries.async_update_entry(entry, data=new_data)
        except Exception as err:
            _LOGGER.debug("[%s] Dynamic device registry enrichment failed: %s", client.ip, err)

    client.register_device_info_callback(_on_device_info_update)
    entry.async_on_unload(
        lambda: client.unregister_device_info_callback(_on_device_info_update)
    )

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: HisenseVidaaConfigEntry, device_entry: Any
) -> bool:
    """Remove a config entry from a device (stale device cleanup)."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: HisenseVidaaConfigEntry) -> None:
    """Clean up the persistent Repairs issues belonging to a removed entry."""
    # [F4-leg2/F5-leg6]: is_persistent issues survive entry removal and would
    # keep showing an unfixable card for a TV that is no longer configured.
    ir.async_delete_issue(hass, DOMAIN, f"certificate_missing_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"auth_token_invalidated_{entry.entry_id}")


async def update_listener(hass: HomeAssistant, entry: HisenseVidaaConfigEntry) -> None:
    """Handle options update."""
    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data and runtime_data.options == dict(entry.options):
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HisenseVidaaConfigEntry) -> bool:
    """Unload a config entry."""
    runtime_data = getattr(entry, "runtime_data", None)
    platforms = runtime_data.platforms if runtime_data else PLATFORMS
    client = runtime_data.client if runtime_data else None

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, platforms
    )
    if unload_ok:
        if client:
            await client.async_disconnect()
        await async_unload_services(hass)
    return unload_ok
