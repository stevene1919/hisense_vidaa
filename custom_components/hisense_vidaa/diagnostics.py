"""Diagnostics support for Hisense VIDAA TV."""

from __future__ import annotations

import contextlib
import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "access_token",
    "refresh_token",
    "password",
    "username",
    "client_id",
    "mac_address",
    "mac_wifi",
    "mac_ethernet",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    client = data.get("client")

    tv_diagnostics = None
    if client:
        now = int(time.time())
        token_expires_in = None
        if client.access_token_time and client.access_token_duration:
            expiry = client.access_token_time + (client.access_token_duration * 86400)
            token_expires_in = expiry - now

        fp = None
        with contextlib.suppress(Exception):
            fp = await hass.async_add_executor_job(client.get_device_fingerprint, 1.5)

        tv_diagnostics = {
            "connected": client.connected,
            "auth_profile": client.auth_profile,
            "source": getattr(client, "source", None),
            "current_app": getattr(client, "current_app", None),
            "volume": getattr(client, "volume", None),
            "muted": getattr(client, "muted", False),
            "tv_state": getattr(client, "tv_state", None),
            "access_token_duration_days": client.access_token_duration,
            "access_token_expires_in_seconds": token_expires_in,
            "refresh_token_duration_days": client.refresh_token_duration,
            "has_refresh_token": bool(client.refresh_token),
            "topic_tv_ui": getattr(client, "topicTVUIBasepath", None),
            "topic_tv_ps": getattr(client, "topicTVPSBasepath", None),
            "topic_mobile": getattr(client, "topicMobiBasepath", None),
        }

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": getattr(entry, "version", 1),
            "domain": getattr(entry, "domain", DOMAIN),
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "pref_disable_new_entities": getattr(entry, "pref_disable_new_entities", False),
            "pref_disable_polling": getattr(entry, "pref_disable_polling", False),
        },
        "client": tv_diagnostics,
        "device_fingerprint": fp,
    }
