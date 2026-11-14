"""Custom services registration and handlers for Hisense VIDAA TV."""

from __future__ import annotations

import functools
import logging
import os
from typing import Any

import yaml
from homeassistant.core import HomeAssistant, SupportsResponse

try:
    from homeassistant.helpers.service import async_set_service_schema
except ImportError:
    async_set_service_schema = None  # type: ignore[assignment]

from ..const import (
    DOMAIN,
    LEGACY_DOMAIN,
    SERVICE_CHANGE_CHANNEL,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
)
from .handlers import (
    handle_change_channel,
    handle_launch_app,
    handle_send_key,
    handle_send_key_sequence,
    handle_send_text_input,
    handle_set_picture_setting,
    handle_set_sound_setting,
)
from .schemas import (
    SERVICE_CHANGE_CHANNEL_SCHEMA,
    SERVICE_LAUNCH_APP_SCHEMA,
    SERVICE_SEND_KEY_SCHEMA,
    SERVICE_SEND_KEY_SEQUENCE_SCHEMA,
    SERVICE_SEND_TEXT_INPUT_SCHEMA,
    SERVICE_SET_PICTURE_SETTING_SCHEMA,
    SERVICE_SET_SOUND_SETTING_SCHEMA,
)
from .target import (
    _as_id_set,
    _async_target_entry_ids_from_registries,
    _extract_entry_client,
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
    "_extract_entry_client",
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
    services_map = [
        (
            SERVICE_SEND_KEY,
            functools.partial(handle_send_key, hass),
            SERVICE_SEND_KEY_SCHEMA,
        ),
        (
            SERVICE_SEND_KEY_SEQUENCE,
            functools.partial(handle_send_key_sequence, hass),
            SERVICE_SEND_KEY_SEQUENCE_SCHEMA,
        ),
        (
            SERVICE_CHANGE_CHANNEL,
            functools.partial(handle_change_channel, hass),
            SERVICE_CHANGE_CHANNEL_SCHEMA,
        ),
        (
            SERVICE_LAUNCH_APP,
            functools.partial(handle_launch_app, hass),
            SERVICE_LAUNCH_APP_SCHEMA,
        ),
        (
            SERVICE_SET_PICTURE_SETTING,
            functools.partial(handle_set_picture_setting, hass),
            SERVICE_SET_PICTURE_SETTING_SCHEMA,
        ),
        (
            SERVICE_SET_SOUND_SETTING,
            functools.partial(handle_set_sound_setting, hass),
            SERVICE_SET_SOUND_SETTING_SCHEMA,
        ),
        (
            SERVICE_SEND_TEXT_INPUT,
            functools.partial(handle_send_text_input, hass),
            SERVICE_SEND_TEXT_INPUT_SCHEMA,
        ),
    ]

    services_yaml_descriptions: dict[str, Any] = {}
    try:
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "services.yaml")
        if os.path.isfile(yaml_path):
            with open(yaml_path, encoding="utf-8") as f:
                services_yaml_descriptions = yaml.safe_load(f) or {}
    except Exception as err:
        _LOGGER.debug("Could not read services.yaml for legacy alias schemas: %s", err)

    for service_name, handler, schema in services_map:
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN,
                service_name,
                handler,
                schema=schema,
                supports_response=SupportsResponse.OPTIONAL,
            )

        # Register non-breaking alias under legacy domain (hisense_vidaa.<service>)
        if not hass.services.has_service(LEGACY_DOMAIN, service_name):
            def _make_legacy_handler(name: str, target_fn: Any):
                async def _legacy_service_handler(call: Any) -> Any:
                    _LOGGER.warning(
                        "Action '%s.%s' is deprecated and will be removed in a future release. "
                        "Please update your automations to use '%s.%s'.",
                        LEGACY_DOMAIN,
                        name,
                        DOMAIN,
                        name,
                    )
                    return await target_fn(call)

                return _legacy_service_handler

            hass.services.async_register(
                LEGACY_DOMAIN,
                service_name,
                _make_legacy_handler(service_name, handler),
                schema=schema,
                supports_response=SupportsResponse.OPTIONAL,
            )

            # Register schema in HA's description cache to prevent IntegrationNotFound
            # errors when Home Assistant builds action descriptions without hisense_vidaa installed.
            if async_set_service_schema is not None:
                try:
                    yaml_desc = services_yaml_descriptions.get(service_name) or {}
                    legacy_schema_desc = {
                        "name": f"[Deprecated] {yaml_desc.get('name', service_name)}",
                        "description": (
                            f"[Deprecated alias for {DOMAIN}.{service_name}] "
                            f"{yaml_desc.get('description', f'Please update automations to use {DOMAIN}.{service_name}.')}"
                        ),
                        "fields": yaml_desc.get("fields", {}),
                    }
                    if "target" in yaml_desc:
                        legacy_schema_desc["target"] = yaml_desc["target"]

                    async_set_service_schema(hass, LEGACY_DOMAIN, service_name, legacy_schema_desc)
                except Exception as err:
                    _LOGGER.debug("Could not register legacy service description schema for %s: %s", service_name, err)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister all custom services if no active entries remain."""
    loaded_entries: list[Any] = []
    if hasattr(hass, "config_entries") and hasattr(hass.config_entries, "async_loaded_entries"):
        try:
            res = hass.config_entries.async_loaded_entries(DOMAIN)
            if isinstance(res, list):
                loaded_entries = res
        except Exception:
            pass

    if len(loaded_entries) > 1:
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
        if hass.services.has_service(LEGACY_DOMAIN, service_name):
            hass.services.async_remove(LEGACY_DOMAIN, service_name)
