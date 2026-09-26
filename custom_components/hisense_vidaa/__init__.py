"""Hisense VIDAA TV custom component integration."""

import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir

from .client import HisenseTvClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_CLIENT_ID,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_USE_SSL,
    CONF_USERNAME,
    DEFAULT_ENABLE_NOTIFY,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_USE_SSL,
    DOMAIN,
)
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


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Hisense VIDAA TV integration services."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hisense VIDAA TV from a config entry."""
    data = entry.data
    mac = data.get(CONF_MAC_ADDRESS)
    if not mac:
        try:
            from homeassistant.helpers.device_registry import format_mac

            from .discovery import get_arp_mac

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
        auth_profile=entry.options.get(CONF_AUTH_PROFILE, data.get(CONF_AUTH_PROFILE, "auto")),
        certfile=certfile,
        keyfile=keyfile,
        use_ssl=use_ssl,
    )
    client._loop = hass.loop

    # Check for missing certificates and manage Repairs issue
    if use_ssl and (not client.certfile or not client.keyfile or not os.path.isfile(client.certfile) or not os.path.isfile(client.keyfile)):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"certificate_missing_{entry.entry_id}",
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="certificate_missing",
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

    client.register_token_refreshed_callback(
        lambda c: hass.loop.call_soon_threadsafe(update_entry_tokens, c)
    )
    client.register_auth_failed_callback(
        lambda c: hass.loop.call_soon_threadsafe(entry.async_start_reauth, hass)
    )

    # Check and refresh tokens in executor
    updated = await hass.async_add_executor_job(client.check_and_refresh_token)
    if updated:
        update_entry_tokens(client)

    # Start running background thread loop for MQTT client in executor
    platforms_to_setup = [
        "media_player",
        "sensor",
        "binary_sensor",
        "button",
        "switch",
        "select",
    ]
    if entry.options.get(
        CONF_ENABLE_PICTURE_CONTROLS, DEFAULT_ENABLE_PICTURE_CONTROLS
    ):
        platforms_to_setup.append("number")
    if entry.options.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE):
        platforms_to_setup.append("remote")
    if entry.options.get(
        CONF_ENABLE_NOTIFY,
        getattr(client, "has_notifications", DEFAULT_ENABLE_NOTIFY),
    ):
        platforms_to_setup.append("notify")

    # Start running background thread loop for MQTT client in executor
    await hass.async_add_executor_job(client.connect_and_run)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "platforms": platforms_to_setup,
        "options": dict(entry.options),
    }

    await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    if isinstance(entry_data, dict) and entry_data.get("options") == dict(entry.options):
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    if isinstance(entry_data, dict):
        platforms = entry_data.get("platforms", PLATFORMS)
        client = entry_data.get("client")
    else:
        platforms = PLATFORMS
        client = entry_data

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, platforms
    )
    if unload_ok:
        data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        unloaded_client = data.get("client") if isinstance(data, dict) else (client or data)
        if unloaded_client:
            await hass.async_add_executor_job(unloaded_client.disconnect)
        await async_unload_services(hass)
    return unload_ok
