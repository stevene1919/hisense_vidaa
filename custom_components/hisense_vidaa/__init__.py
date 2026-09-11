"""Hisense VIDAA TV custom component integration."""

import asyncio
import logging
import os
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, issue_registry as ir

from .client import HisenseTvClient
from .const import (
    ATTR_APP,
    ATTR_DELAY,
    ATTR_KEY,
    ATTR_REPEAT,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_CLIENT_ID,
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
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_USE_SSL,
    DOMAIN,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = [
    "media_player",
    "remote",
    "sensor",
    "binary_sensor",
    "button",
    "notify",
    "select",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Hisense VIDAA TV integration services."""

    async def handle_send_key(call: ServiceCall) -> None:
        """Handle send_key service call."""
        key = call.data.get(ATTR_KEY)
        repeat = call.data.get(ATTR_REPEAT, 1)
        delay = call.data.get(ATTR_DELAY, 0.2)

        # Dispatch to target clients
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            client: HisenseTvClient = data.get("client") if isinstance(data, dict) else data
            if client:
                for i in range(repeat):
                    if i > 0 and delay > 0:
                        await asyncio.sleep(delay)
                    await hass.async_add_executor_job(client.send_key, key)

    async def handle_launch_app(call: ServiceCall) -> None:
        """Handle launch_app service call."""
        app = call.data.get(ATTR_APP)
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            client: HisenseTvClient = data.get("client") if isinstance(data, dict) else data
            if client:
                # Search app dict for matching app or send directly as url
                matched_app = None
                for a in getattr(client, "_app_list", []):
                    if isinstance(a, dict) and (
                        a.get("appName", "").lower() == app.lower()
                        or a.get("appId", "").lower() == app.lower()
                    ):
                        matched_app = a
                        break

                if matched_app:
                    await hass.async_add_executor_job(
                        client.launch_app,
                        matched_app.get("appId", ""),
                        matched_app.get("appName", ""),
                        matched_app.get("appUrl", ""),
                    )
                else:
                    await hass.async_add_executor_job(client.launch_app, "", app, app)

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_KEY):
        hass.services.async_register(DOMAIN, SERVICE_SEND_KEY, handle_send_key)

    if not hass.services.has_service(DOMAIN, SERVICE_LAUNCH_APP):
        hass.services.async_register(DOMAIN, SERVICE_LAUNCH_APP, handle_launch_app)

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
        client_id=data[CONF_CLIENT_ID],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        access_token=data[CONF_ACCESS_TOKEN],
        access_token_time=data[CONF_ACCESS_TOKEN_TIME],
        access_token_duration=data[CONF_ACCESS_TOKEN_DURATION],
        refresh_token=data[CONF_REFRESH_TOKEN],
        refresh_token_time=data[CONF_REFRESH_TOKEN_TIME],
        refresh_token_duration=data[CONF_REFRESH_TOKEN_DURATION],
        auth_profile=data.get(CONF_AUTH_PROFILE, "auto"),
        certfile=certfile,
        keyfile=keyfile,
        use_ssl=use_ssl,
    )

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

    client.on_token_refreshed = lambda c: hass.loop.call_soon_threadsafe(
        update_entry_tokens, c
    )
    client.register_auth_failed_callback(
        lambda c: hass.loop.call_soon_threadsafe(entry.async_start_reauth, hass)
    )

    # Check and refresh tokens in executor
    updated = await hass.async_add_executor_job(client.check_and_refresh_token)
    if updated:
        update_entry_tokens(client)

    # Start running background thread loop for MQTT client in executor
    await hass.async_add_executor_job(client.connect_and_run)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"client": client}

    platforms_to_setup = ["media_player", "sensor", "binary_sensor", "button"]
    if entry.options.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE):
        platforms_to_setup.append("remote")

    await hass.config_entries.async_forward_entry_setups(entry, platforms_to_setup)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        client = data.get("client") if isinstance(data, dict) else data
        if client:
            await hass.async_add_executor_job(client.disconnect)
    return unload_ok
