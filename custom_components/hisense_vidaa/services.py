"""Custom services registration and handlers for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    ATTR_ACTION,
    ATTR_APP,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_CHANNEL,
    ATTR_CONFIRM,
    ATTR_DELAY,
    ATTR_KEY,
    ATTR_MENU_ID,
    ATTR_MENU_VALUE,
    ATTR_REPEAT,
    ATTR_SEQUENCE,
    ATTR_TEXT,
    ATTR_URL,
    DOMAIN,
    SERVICE_CHANGE_CHANNEL,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
)
from .services_target import (
    _as_id_set,
    _async_target_entry_ids_from_registries,
    _get_target_clients,
    _resolve_service_targets,
    _target_selector_fields,
    _validate_launch_app_data,
    parse_key_sequence,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "_as_id_set",
    "_async_target_entry_ids_from_registries",
    "_get_target_clients",
    "_resolve_service_targets",
    "_target_selector_fields",
    "_validate_launch_app_data",
    "async_setup_services",
    "async_unload_services",
    "parse_key_sequence",
]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register all custom services for the Hisense VIDAA TV integration."""

    async def handle_send_key(call: ServiceCall) -> dict[str, Any]:
        """Handle send_key service call."""
        key = call.data.get(ATTR_KEY)
        repeat = call.data.get(ATTR_REPEAT, 1)
        delay = call.data.get(ATTR_DELAY, 0.2)
        target_clients = _resolve_service_targets(hass, call)

        for client in target_clients:
            for i in range(repeat):
                if i > 0 and delay > 0:
                    await asyncio.sleep(delay)
                try:
                    await hass.async_add_executor_job(client.send_command, key)
                except Exception as err:
                    raise HomeAssistantError(f"Failed to send key command '{key}': {err}") from err

        return {
            "key": key,
            "repeat": repeat,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    async def handle_send_key_sequence(call: ServiceCall) -> dict[str, Any]:
        """Handle send_key_sequence service call."""
        raw_sequence = call.data.get(ATTR_SEQUENCE)
        delay = float(call.data.get(ATTR_DELAY, 0.3))
        target_clients = _resolve_service_targets(hass, call)
        sequence = parse_key_sequence(raw_sequence)

        if not sequence:
            raise ServiceValidationError("No valid keys provided in sequence.")

        for client in target_clients:
            for i, key in enumerate(sequence):
                if i > 0 and delay > 0:
                    await asyncio.sleep(delay)
                try:
                    await hass.async_add_executor_job(client.send_command, key)
                except Exception as err:
                    raise HomeAssistantError(
                        f"Failed to execute key sequence at step '{key}': {err}"
                    ) from err

        return {
            "sequence": sequence,
            "delay": delay,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    async def handle_change_channel(call: ServiceCall) -> dict[str, Any]:
        """Handle change_channel service call by dispatching numeric digits."""
        raw_channel = str(call.data.get(ATTR_CHANNEL, "")).strip()
        confirm = bool(call.data.get(ATTR_CONFIRM, True))
        delay = float(call.data.get(ATTR_DELAY, 0.25))
        target_clients = _resolve_service_targets(hass, call)

        digits = [ch for ch in raw_channel if ch.isdigit()]
        if not digits:
            raise ServiceValidationError(
                f"Invalid channel '{raw_channel}': must contain at least one numeric digit."
            )

        for client in target_clients:
            for i, digit in enumerate(digits):
                if i > 0 and delay > 0:
                    await asyncio.sleep(delay)
                key = f"KEY_{digit}"
                try:
                    await hass.async_add_executor_job(client.send_command, key)
                except Exception as err:
                    raise HomeAssistantError(
                        f"Failed to send channel digit '{digit}': {err}"
                    ) from err

            if confirm:
                if delay > 0:
                    await asyncio.sleep(delay)
                try:
                    await hass.async_add_executor_job(client.send_command, "KEY_OK")
                except Exception as err:
                    raise HomeAssistantError(
                        f"Failed to send channel confirm command: {err}"
                    ) from err

        return {
            "channel": raw_channel,
            "digits": digits,
            "confirmed": confirm,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    async def handle_launch_app(call: ServiceCall) -> dict[str, Any]:
        """Handle launch_app service call."""
        app = str(call.data.get(ATTR_APP) or "")
        requested_app_id = str(call.data.get(ATTR_APP_ID) or "")
        target_clients = _resolve_service_targets(hass, call)
        launched: list[dict[str, Any]] = []
        lookup_ids = {value.lower() for value in (app, requested_app_id) if value}

        for client in target_clients:
            matched_app = None
            for a in getattr(client, "apps", []):
                if isinstance(a, dict) and (
                    (app and str(a.get("name") or a.get("appName") or "").lower() == app.lower())
                    or str(a.get("appId") or a.get("app_id") or "").lower() in lookup_ids
                ):
                    matched_app = a
                    break

            if matched_app:
                app_id = str(matched_app.get("appId") or matched_app.get("app_id") or "")
                app_name = str(matched_app.get("name") or matched_app.get("appName") or "")
                app_url = str(matched_app.get("url") or matched_app.get("appUrl") or "")
            else:
                app_id = ""
                app_name = app or requested_app_id
                app_url = app

            app_id = requested_app_id or app_id
            app_name = str(call.data.get(ATTR_APP_NAME, app_name))
            app_url = str(call.data.get(ATTR_URL, app_url))

            try:
                await hass.async_add_executor_job(
                    client.launch_app,
                    app_id,
                    app_name,
                    app_url,
                )
            except Exception as err:
                raise HomeAssistantError(f"Failed to launch app '{app_name}': {err}") from err

            launched.append({
                "ip": getattr(client, "ip", "unknown"),
                "app_name": app_name,
                "app_id": app_id,
                "app_url": app_url,
            })

        return {
            "app": app or requested_app_id,
            "targets": launched,
            "count": len(launched),
        }

    async def handle_set_picture_setting(call: ServiceCall) -> dict[str, Any]:
        """Handle set_picture_setting service call."""
        menu_id = call.data.get(ATTR_MENU_ID)
        menu_val = call.data.get(ATTR_MENU_VALUE)
        target_clients = _resolve_service_targets(hass, call)
        for client in target_clients:
            try:
                await hass.async_add_executor_job(client.set_picture_setting, menu_id, menu_val)
            except Exception as err:
                raise HomeAssistantError(f"Failed to set picture setting (menu_id={menu_id}): {err}") from err
        return {
            "menu_id": menu_id,
            "menu_value": menu_val,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    async def handle_set_sound_setting(call: ServiceCall) -> dict[str, Any]:
        """Handle set_sound_setting service call."""
        menu_id = call.data.get(ATTR_MENU_ID)
        menu_val = call.data.get(ATTR_MENU_VALUE)
        target_clients = _resolve_service_targets(hass, call)
        for client in target_clients:
            try:
                await hass.async_add_executor_job(client.set_sound_setting, menu_id, menu_val)
            except Exception as err:
                raise HomeAssistantError(f"Failed to set sound setting (menu_id={menu_id}): {err}") from err
        return {
            "menu_id": menu_id,
            "menu_value": menu_val,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    async def handle_send_text_input(call: ServiceCall) -> dict[str, Any]:
        """Handle send_text_input service call."""
        text = call.data.get(ATTR_TEXT, "")
        action = call.data.get(ATTR_ACTION, "insert")
        target_clients = _resolve_service_targets(hass, call)
        for client in target_clients:
            try:
                await hass.async_add_executor_job(client.send_text_input, text, action)
            except Exception as err:
                raise HomeAssistantError(f"Failed to send text input: {err}") from err
        return {
            "text": text,
            "action": action,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    # [F8-leg2]: without a schema a bad `repeat`/`delay` reached the handler and
    # raised a raw TypeError, and the strings.json `exceptions` keys were dead.
    services_map = [
        (
            SERVICE_SEND_KEY,
            handle_send_key,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_KEY): str,
                vol.Optional(ATTR_REPEAT, default=1): vol.Coerce(int),
                vol.Optional(ATTR_DELAY, default=0.2): vol.Coerce(float),
            }),
        ),
        (
            SERVICE_SEND_KEY_SEQUENCE,
            handle_send_key_sequence,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_SEQUENCE): vol.Any([str], str),
                vol.Optional(ATTR_DELAY, default=0.3): vol.Coerce(float),
            }),
        ),
        (
            SERVICE_CHANGE_CHANNEL,
            handle_change_channel,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_CHANNEL): vol.Any(int, str),
                vol.Optional(ATTR_CONFIRM, default=True): vol.Coerce(bool),
                vol.Optional(ATTR_DELAY, default=0.25): vol.Coerce(float),
            }),
        ),
        (
            SERVICE_LAUNCH_APP,
            handle_launch_app,
            vol.Schema(
                vol.All(
                    {
                        **_target_selector_fields(),
                        vol.Optional(ATTR_APP): str,
                        vol.Optional(ATTR_APP_ID): vol.Coerce(str),
                        vol.Optional(ATTR_APP_NAME): str,
                        vol.Optional(ATTR_URL): str,
                    },
                    _validate_launch_app_data,
                )
            ),
        ),
        (
            SERVICE_SET_PICTURE_SETTING,
            handle_set_picture_setting,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_MENU_ID): vol.Coerce(int),
                vol.Required(ATTR_MENU_VALUE): vol.Coerce(str),
            }),
        ),
        (
            SERVICE_SET_SOUND_SETTING,
            handle_set_sound_setting,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_MENU_ID): vol.Coerce(int),
                vol.Required(ATTR_MENU_VALUE): vol.Coerce(str),
            }),
        ),
        (
            SERVICE_SEND_TEXT_INPUT,
            handle_send_text_input,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_TEXT): str,
                vol.Optional(ATTR_ACTION, default="insert"): str,
            }),
        ),
    ]

    for service_name, handler, schema in services_map:
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN,
                service_name,
                handler,
                schema=schema,
                supports_response=SupportsResponse.OPTIONAL,
            )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister all custom services if no active entries remain."""
    loaded_entries: list[Any] = []
    if hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_loaded_entries"):
        with contextlib.suppress(Exception):
            res = hass.config_entries.async_loaded_entries(DOMAIN)
            if isinstance(res, list):
                loaded_entries = res

    if not loaded_entries and hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_entries"):
        with contextlib.suppress(Exception):
            res = hass.config_entries.async_entries(DOMAIN)
            if isinstance(res, list):
                loaded_entries = [e for e in res if getattr(e, "runtime_data", None) is not None]

    if not loaded_entries and hasattr(hass, "data") and isinstance(hass.data, dict) and hass.data.get(DOMAIN):
        return

    if loaded_entries:
        return

    services_to_remove = [
        SERVICE_SEND_KEY,
        SERVICE_SEND_KEY_SEQUENCE,
        SERVICE_CHANGE_CHANNEL,
        SERVICE_LAUNCH_APP,
        SERVICE_SET_PICTURE_SETTING,
        SERVICE_SET_SOUND_SETTING,
        SERVICE_SEND_TEXT_INPUT,
    ]
    for service_name in services_to_remove:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)

