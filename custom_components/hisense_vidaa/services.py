"""Custom services registration and handlers for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError

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


def _as_id_set(value: Any) -> set[str]:
    """Normalize a target selector value (single id or list of ids) into a set."""
    if not value:
        return set()
    if isinstance(value, str):
        return {value}
    return {str(item) for item in value}


def _async_target_entry_ids_from_registries(
    hass: HomeAssistant, call_data: dict[str, Any]
) -> set[str]:
    """Resolve area/floor/label targets to config entry ids via the HA registries.

    [F7-leg2]: the target selector also offers area, floor and label targeting;
    those live in their own keys of the service call data and were previously
    ignored, so such a call was broadcast to every TV instead.
    """
    area_ids = _as_id_set(call_data.get("area_id"))
    floor_ids = _as_id_set(call_data.get("floor_id"))
    label_ids = _as_id_set(call_data.get("label_id"))
    if not area_ids and not floor_ids and not label_ids:
        return set()

    from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

    if floor_ids:
        for area in ar.async_get(hass).areas.values():
            if area.floor_id in floor_ids:
                area_ids.add(area.id)

    entry_ids: set[str] = set()

    ent_reg = er.async_get(hass)
    for entity in ent_reg.entities.values():
        labels = getattr(entity, "labels", None) or ()
        if (
            (entity.area_id and entity.area_id in area_ids)
            or (label_ids and label_ids.intersection(labels))
        ) and entity.config_entry_id:
            entry_ids.add(entity.config_entry_id)

    dev_reg = dr.async_get(hass)
    for device in dev_reg.devices.values():
        labels = getattr(device, "labels", None) or ()
        if (device.area_id and device.area_id in area_ids) or (
            label_ids and label_ids.intersection(labels)
        ):
            entry_ids.update(device.config_entries)

    return entry_ids


def _get_target_clients(hass: HomeAssistant, call: ServiceCall) -> list[Any]:
    """Resolve target clients from service call parameters."""
    clients: list[Any] = []
    domain_data = hass.data.get(DOMAIN, {})
    target_ip = call.data.get("ip_address") or call.data.get("ip")
    target_mac = call.data.get("mac_address") or call.data.get("mac")
    target_entry_id = call.data.get("entry_id")

    target_entry_ids: set[str] = set()
    if target_entry_id:
        target_entry_ids.add(target_entry_id)

    target_entry_ids |= _async_target_entry_ids_from_registries(hass, call.data)

    entity_ids = call.data.get("entity_id")
    registry_ids_given = bool(
        entity_ids
        or call.data.get("device_id")
        or call.data.get("area_id")
        or call.data.get("floor_id")
        or call.data.get("label_id")
    )
    if entity_ids:
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        try:
            from homeassistant.helpers import entity_registry as er
            ent_reg = er.async_get(hass)
            for eid in entity_ids:
                entry = ent_reg.async_get(eid)
                if entry and entry.config_entry_id:
                    target_entry_ids.add(entry.config_entry_id)
        except Exception:
            pass

    device_ids = call.data.get("device_id")
    if device_ids:
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        try:
            from homeassistant.helpers import device_registry as dr
            dev_reg = dr.async_get(hass)
            for did in device_ids:
                device = dev_reg.async_get(did)
                if device:
                    for ce_id in device.config_entries:
                        target_entry_ids.add(ce_id)
        except Exception:
            pass

    # [F7-leg2]: ip/mac/entry_id are explicit targets too, so the broadcast
    # fallback below must never fire once anything targets the call.
    selector_given = bool(
        target_entry_ids or target_ip or target_mac or registry_ids_given
    )

    for entry_id, data in domain_data.items():
        client = data.get("client") if isinstance(data, dict) else data
        if not client:
            continue
        if target_entry_ids and entry_id not in target_entry_ids:
            continue
        # A registry-backed target (entity/device/area/floor/label) that resolves
        # to no entry matches nothing - it must not degrade into a broadcast.
        if registry_ids_given and not target_entry_ids:
            continue
        if target_ip and getattr(client, "ip", None) != target_ip:
            continue
        if target_mac and getattr(client, "mac", None) != target_mac:
            continue
        clients.append(client)

    if not clients and not selector_given:
        for entry_id, data in domain_data.items():
            client = data.get("client") if isinstance(data, dict) else data
            if client:
                clients.append(client)
    return clients


def _resolve_service_targets(hass: HomeAssistant, call: ServiceCall) -> list[Any]:
    """Resolve the clients addressed by a service call, or fail loudly.

    [F8-leg2]: a targeted call that matched nothing used to return `count: 0`
    silently, and a call against a disconnected TV silently did nothing.  Both
    now surface the pre-defined translation keys as ServiceValidationError.
    """
    clients = _get_target_clients(hass, call)
    if not clients:
        raise ServiceValidationError(
            "No matching Hisense VIDAA TV was found for the specified service call target.",
            translation_domain=DOMAIN,
            translation_key="no_target_device",
        )
    if not any(getattr(client, "connected", False) for client in clients):
        raise ServiceValidationError(
            "Cannot send command: TV is currently disconnected.",
            translation_domain=DOMAIN,
            translation_key="not_connected",
        )
    return clients


def _target_selector_fields() -> dict[Any, Any]:
    """Return the target-selector fields accepted by every service schema."""
    return {
        vol.Optional("entry_id"): str,
        vol.Optional("entity_id"): vol.Any(str, [str]),
        vol.Optional("device_id"): vol.Any(str, [str]),
        vol.Optional("area_id"): vol.Any(str, [str]),
        vol.Optional("floor_id"): vol.Any(str, [str]),
        vol.Optional("label_id"): vol.Any(str, [str]),
        vol.Optional("ip_address"): str,
        vol.Optional("ip"): str,
        vol.Optional("mac_address"): str,
        vol.Optional("mac"): str,
    }


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
                await hass.async_add_executor_job(client.send_command, key)

        return {
            "key": key,
            "repeat": repeat,
            "targets": [getattr(c, "ip", "unknown") for c in target_clients],
            "count": len(target_clients),
        }

    async def handle_launch_app(call: ServiceCall) -> dict[str, Any]:
        """Handle launch_app service call."""
        app = call.data.get(ATTR_APP)
        target_clients = _resolve_service_targets(hass, call)
        launched: list[dict[str, Any]] = []

        for client in target_clients:
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
                app_id = str(matched_app.get("appId", ""))
                app_name = str(matched_app.get("name") or matched_app.get("appName") or "")
                app_url = str(matched_app.get("url") or matched_app.get("appUrl") or "")
            else:
                app_id = ""
                app_name = app
                app_url = app

            await hass.async_add_executor_job(
                client.launch_app,
                app_id,
                app_name,
                app_url,
            )
            launched.append({
                "ip": getattr(client, "ip", "unknown"),
                "app_name": app_name,
                "app_id": app_id,
                "app_url": app_url,
            })

        return {
            "app": app,
            "targets": launched,
            "count": len(launched),
        }

    async def handle_set_picture_setting(call: ServiceCall) -> dict[str, Any]:
        """Handle set_picture_setting service call."""
        menu_id = call.data.get(ATTR_MENU_ID)
        menu_val = call.data.get(ATTR_MENU_VALUE)
        target_clients = _resolve_service_targets(hass, call)
        for client in target_clients:
            await hass.async_add_executor_job(client.set_picture_setting, menu_id, menu_val)
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
            await hass.async_add_executor_job(client.set_sound_setting, menu_id, menu_val)
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
            await hass.async_add_executor_job(client.send_text_input, text, action)
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
            SERVICE_LAUNCH_APP,
            handle_launch_app,
            vol.Schema({
                **_target_selector_fields(),
                vol.Required(ATTR_APP): str,
            }),
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

