"""Custom services registration and handlers for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    ATTR_ACTION,
    ATTR_APP,
    ATTR_DELAY,
    ATTR_KEY,
    ATTR_MENU_ID,
    ATTR_MENU_VALUE,
    ATTR_REPEAT,
    ATTR_TEXT,
    DOMAIN,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
)

_LOGGER = logging.getLogger(__name__)

__all__ = ["async_setup_services", "async_unload_services"]


def _get_target_clients(hass: HomeAssistant, call: ServiceCall) -> list[Any]:
    """Resolve target clients from service call parameters."""
    clients: list[Any] = []
    domain_data = hass.data.get(DOMAIN, {})
    target_ip = call.data.get("ip_address") or call.data.get("ip")
    target_mac = call.data.get("mac_address") or call.data.get("mac")
    target_entry_id = call.data.get("entry_id")

    for entry_id, data in domain_data.items():
        client = data.get("client") if isinstance(data, dict) else data
        if not client:
            continue
        if target_entry_id and entry_id != target_entry_id:
            continue
        if target_ip and getattr(client, "ip", None) != target_ip:
            continue
        if target_mac and getattr(client, "mac", None) != target_mac:
            continue
        clients.append(client)

    if not clients and not (target_entry_id or target_ip or target_mac):
        for entry_id, data in domain_data.items():
            client = data.get("client") if isinstance(data, dict) else data
            if client:
                clients.append(client)
    return clients


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register all custom services for the Hisense VIDAA TV integration."""

    async def handle_send_key(call: ServiceCall) -> None:
        """Handle send_key service call."""
        key = call.data.get(ATTR_KEY)
        repeat = call.data.get(ATTR_REPEAT, 1)
        delay = call.data.get(ATTR_DELAY, 0.2)

        for client in _get_target_clients(hass, call):
            for i in range(repeat):
                if i > 0 and delay > 0:
                    await asyncio.sleep(delay)
                await hass.async_add_executor_job(client.send_key, key)

    async def handle_launch_app(call: ServiceCall) -> None:
        """Handle launch_app service call."""
        app = call.data.get(ATTR_APP)
        for client in _get_target_clients(hass, call):
            matched_app = None
            for a in getattr(client, "apps", []):
                if isinstance(a, dict) and (
                    str(a.get("name", "")).lower() == app.lower()
                    or str(a.get("appName", "")).lower() == app.lower()
                    or str(a.get("appId", "")).lower() == app.lower()
                ):
                    matched_app = a
                    break

            if matched_app:
                await hass.async_add_executor_job(
                    client.launch_app,
                    str(matched_app.get("appId", "")),
                    str(matched_app.get("name") or matched_app.get("appName") or ""),
                    str(matched_app.get("url") or matched_app.get("appUrl") or ""),
                )
            else:
                await hass.async_add_executor_job(client.launch_app, "", app, app)

    async def handle_set_picture_setting(call: ServiceCall) -> None:
        """Handle set_picture_setting service call."""
        menu_id = call.data.get(ATTR_MENU_ID)
        menu_val = call.data.get(ATTR_MENU_VALUE)
        for client in _get_target_clients(hass, call):
            await hass.async_add_executor_job(client.set_picture_setting, menu_id, menu_val)

    async def handle_set_sound_setting(call: ServiceCall) -> None:
        """Handle set_sound_setting service call."""
        menu_id = call.data.get(ATTR_MENU_ID)
        menu_val = call.data.get(ATTR_MENU_VALUE)
        for client in _get_target_clients(hass, call):
            await hass.async_add_executor_job(client.set_sound_setting, menu_id, menu_val)

    async def handle_send_text_input(call: ServiceCall) -> None:
        """Handle send_text_input service call."""
        text = call.data.get(ATTR_TEXT, "")
        action = call.data.get(ATTR_ACTION, "insert")
        for client in _get_target_clients(hass, call):
            await hass.async_add_executor_job(client.send_text_input, text, action)

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_KEY):
        hass.services.async_register(DOMAIN, SERVICE_SEND_KEY, handle_send_key)

    if not hass.services.has_service(DOMAIN, SERVICE_LAUNCH_APP):
        hass.services.async_register(DOMAIN, SERVICE_LAUNCH_APP, handle_launch_app)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_PICTURE_SETTING):
        hass.services.async_register(DOMAIN, SERVICE_SET_PICTURE_SETTING, handle_set_picture_setting)

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SOUND_SETTING):
        hass.services.async_register(DOMAIN, SERVICE_SET_SOUND_SETTING, handle_set_sound_setting)

    if not hass.services.has_service(DOMAIN, SERVICE_SEND_TEXT_INPUT):
        hass.services.async_register(DOMAIN, SERVICE_SEND_TEXT_INPUT, handle_send_text_input)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister all custom services if no active entries remain."""
    domain_data = hass.data.get(DOMAIN, {})
    if domain_data:
        return

    services_to_remove = [
        SERVICE_SEND_KEY,
        SERVICE_LAUNCH_APP,
        SERVICE_SET_PICTURE_SETTING,
        SERVICE_SET_SOUND_SETTING,
        SERVICE_SEND_TEXT_INPUT,
    ]
    for service_name in services_to_remove:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)
