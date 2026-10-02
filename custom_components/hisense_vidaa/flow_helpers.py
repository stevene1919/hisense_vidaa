"""Helper functions and schema definitions for Hisense VIDAA config flow."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_CLIENT_ID,
    CONF_ENABLE_AUDIO_ONLY,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_SOUND_CONTROLS,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_SW_VERSION,
    CONF_USE_SSL,
    CONF_USERNAME,
    DEFAULT_ENABLE_AUDIO_ONLY,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_USE_SSL,
    DOMAIN,
)
from .crypto import check_certs_exist, resolve_certificates
from .discovery import get_arp_mac

if TYPE_CHECKING:
    from .client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def build_options_schema(pic_supported: bool, sound_supported: bool) -> vol.Schema:
    """Build the configuration options schema for initial setup and options flow."""
    return vol.Schema({
        vol.Optional(CONF_ENABLE_REMOTE, default=DEFAULT_ENABLE_REMOTE): bool,
        vol.Optional(CONF_ENABLE_WOL, default=DEFAULT_ENABLE_WOL): bool,
        vol.Optional(CONF_INCLUDE_APPS_IN_SOURCES, default=DEFAULT_INCLUDE_APPS_IN_SOURCES): bool,
        vol.Optional(CONF_ENABLE_MEDIA_CONTROLS, default=DEFAULT_ENABLE_MEDIA_CONTROLS): bool,
        vol.Optional(CONF_ENABLE_PICTURE_CONTROLS, default=pic_supported): bool,
        vol.Optional(CONF_ENABLE_SOUND_CONTROLS, default=sound_supported): bool,
        vol.Optional(CONF_ENABLE_AUDIO_ONLY, default=DEFAULT_ENABLE_AUDIO_ONLY): bool,
    })


def build_entry_options(
    user_input: dict[str, Any], pic_supported: bool, sound_supported: bool
) -> dict[str, Any]:
    """Map user input to config entry options dictionary."""
    return {
        CONF_ENABLE_REMOTE: user_input.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE),
        CONF_ENABLE_WOL: user_input.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL),
        CONF_INCLUDE_APPS_IN_SOURCES: user_input.get(CONF_INCLUDE_APPS_IN_SOURCES, DEFAULT_INCLUDE_APPS_IN_SOURCES),
        CONF_ENABLE_MEDIA_CONTROLS: user_input.get(CONF_ENABLE_MEDIA_CONTROLS, DEFAULT_ENABLE_MEDIA_CONTROLS),
        CONF_ENABLE_PICTURE_CONTROLS: user_input.get(CONF_ENABLE_PICTURE_CONTROLS, pic_supported),
        CONF_ENABLE_SOUND_CONTROLS: user_input.get(CONF_ENABLE_SOUND_CONTROLS, sound_supported),
        CONF_ENABLE_AUDIO_ONLY: user_input.get(CONF_ENABLE_AUDIO_ONLY, DEFAULT_ENABLE_AUDIO_ONLY),
    }


def resolve_ssl_certs(
    auth_profile: str,
) -> tuple[bool, str | None, str | None, bool]:
    """Resolves certificates from disk or profile.

    Returns: (success, certfile, keyfile, use_ssl)
    """
    if auth_profile == "legacy":
        return True, None, None, False

    resolved_cert, resolved_key = resolve_certificates(auth_profile)
    if check_certs_exist(resolved_cert, resolved_key):
        return True, resolved_cert, resolved_key, True

    return False, None, None, DEFAULT_USE_SSL


async def async_discover_device_details(
    hass: HomeAssistant, client: HisenseTvClient | None, default_ip: str | None
) -> dict[str, str | None]:
    """Discovers friendly device name, model, manufacturer, and sw_version from UPnP/DLNA."""
    title = f"Hisense TV ({default_ip})" if default_ip else "Hisense TV"
    details: dict[str, str | None] = {
        "title": title,
        "model": None,
        "manufacturer": None,
        "sw_version": None,
    }
    if not client:
        return details

    try:
        fp = await hass.async_add_executor_job(client.get_device_fingerprint, 1.5)
        discovered_name = fp.get("friendly_name") or fp.get("model_code")
        if (
            discovered_name
            and discovered_name.strip()
            and discovered_name.strip() != "Renderer"
        ):
            details["title"] = discovered_name.strip()
        if fp.get("model_code") or fp.get("model_name"):
            details["model"] = fp.get("model_code") or fp.get("model_name")
        if fp.get("manufacturer") or fp.get("brand"):
            details["manufacturer"] = fp.get("manufacturer") or fp.get("brand")
        if fp.get("firmware_version"):
            details["sw_version"] = fp.get("firmware_version")
    except Exception:
        pass

    return details


async def async_probe_device_capabilities(
    hass: HomeAssistant, client: HisenseTvClient | None, ip_address: str | None
) -> None:
    """Probe TV capabilities (picture/sound menus) to set intelligent default options."""
    if not client or not client.connected:
        return
    try:
        await hass.async_add_executor_job(client.get_picture_settings)
        await hass.async_add_executor_job(client.get_sound_settings)
        await asyncio.sleep(1.0)
    except Exception as e:
        _LOGGER.debug("[%s] Error during capability probe: %s", ip_address, e)


async def async_disconnect_existing_client(
    hass: HomeAssistant,
    ip_address: str | None,
    mac_address: str | None,
    entry_id: str | None = None,
) -> None:
    """Disconnect any running client for this IP/MAC to avoid MQTT session collision during pairing.

    ``entry_id`` restricts the disconnect to a single entry (the one being
    re-paired); when omitted, any matching client is disconnected.
    """
    entries = (
        hass.config_entries.async_entries(DOMAIN)
        if hasattr(getattr(hass, "config_entries", None), "async_entries")
        else []
    )
    for entry in entries:
        if entry_id is not None and entry.entry_id != entry_id:
            continue
        runtime_data = getattr(entry, "runtime_data", None)
        client = getattr(runtime_data, "client", runtime_data) if runtime_data else None
        if client and (
            getattr(client, "ip", None) == ip_address
            or (mac_address and getattr(client, "mac", None) == mac_address)
        ):
            _LOGGER.debug("Disconnecting existing running client for %s during pairing flow", ip_address)
            with contextlib.suppress(Exception):
                await hass.async_add_executor_job(client.disconnect)

    if hasattr(hass, "data") and isinstance(hass.data, dict) and DOMAIN in hass.data:
        for current_entry_id, entry_data in list(hass.data.get(DOMAIN, {}).items()):
            if entry_id is not None and current_entry_id != entry_id:
                continue
            client = entry_data.get("client") if isinstance(entry_data, dict) else entry_data
            if client and (
                getattr(client, "ip", None) == ip_address
                or (mac_address and getattr(client, "mac", None) == mac_address)
            ):
                _LOGGER.debug("Disconnecting existing running client for %s during pairing flow", ip_address)
                with contextlib.suppress(Exception):
                    await hass.async_add_executor_job(client.disconnect)


async def async_resolve_mac(hass: HomeAssistant, ip_address: str | None) -> str | None:
    """Resolves and formats the MAC address for a given IP using ARP."""
    if not ip_address:
        return None
    try:
        raw_mac = await hass.async_add_executor_job(get_arp_mac, ip_address)
        if raw_mac:
            return format_mac(raw_mac)
    except Exception:
        pass
    return None


def collect_client_auth_data(
    ip_address: str | None,
    auth_profile: str,
    use_ssl: bool,
    mac_address: str | None = None,
    client: HisenseTvClient | None = None,
    certfile: str | None = None,
    keyfile: str | None = None,
    model: str | None = None,
    manufacturer: str | None = None,
    sw_version: str | None = None,
) -> dict[str, Any]:
    """Collect authentication credentials and device attributes dictionary for config entry data."""
    data: dict[str, Any] = {
        CONF_IP_ADDRESS: ip_address,
        CONF_AUTH_PROFILE: auth_profile,
        CONF_USE_SSL: use_ssl,
    }
    if mac_address:
        data[CONF_MAC_ADDRESS] = mac_address
    if client:
        data.update({
            CONF_CLIENT_ID: client.client_id,
            CONF_USERNAME: client.username,
            CONF_PASSWORD: client.password,
            CONF_ACCESS_TOKEN: client.access_token,
            CONF_ACCESS_TOKEN_TIME: client.access_token_time,
            CONF_ACCESS_TOKEN_DURATION: client.access_token_duration,
            CONF_REFRESH_TOKEN: client.refresh_token,
            CONF_REFRESH_TOKEN_TIME: client.refresh_token_time,
            CONF_REFRESH_TOKEN_DURATION: client.refresh_token_duration,
        })
    if certfile:
        data[CONF_CERTFILE] = certfile
    if keyfile:
        data[CONF_KEYFILE] = keyfile
    if model:
        data[CONF_MODEL] = model
    if manufacturer:
        data[CONF_MANUFACTURER] = manufacturer
    if sw_version:
        data[CONF_SW_VERSION] = sw_version
    return data
