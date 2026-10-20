"""Target resolution, schema selectors, and data validators for Hisense VIDAA TV services."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import ATTR_APP, ATTR_APP_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "_as_id_set",
    "_async_target_entry_ids_from_registries",
    "_get_target_clients",
    "_resolve_service_targets",
    "_target_selector_fields",
    "_validate_launch_app_data",
    "parse_key_sequence",
]


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

    Target selector offers area, floor, and label targeting. These reside in their
    own keys of the service call data.
    """
    area_ids = _as_id_set(call_data.get("area_id"))
    floor_ids = _as_id_set(call_data.get("floor_id"))
    label_ids = _as_id_set(call_data.get("label_id"))
    if not area_ids and not floor_ids and not label_ids:
        return set()

    from homeassistant.helpers import (
        area_registry as ar,
        device_registry as dr,
        entity_registry as er,
    )

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

    if not loaded_entries and hasattr(hass, "data") and isinstance(hass.data, dict) and DOMAIN in hass.data:
        from types import SimpleNamespace

        for eid, edata in hass.data.get(DOMAIN, {}).items():
            loaded_entries.append(SimpleNamespace(entry_id=eid, runtime_data=edata))

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

    # ip/mac/entry_id are explicit targets, so the broadcast fallback must never fire
    # once anything targets the call.
    selector_given = bool(
        target_entry_ids or target_ip or target_mac or registry_ids_given
    )

    for entry in loaded_entries:
        runtime_data = getattr(entry, "runtime_data", None)
        if isinstance(runtime_data, dict):
            client = runtime_data.get("client")
        elif runtime_data is not None:
            client = getattr(runtime_data, "client", runtime_data)
        else:
            client = None
        if not client:
            continue
        if target_entry_ids and entry.entry_id not in target_entry_ids:
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
        for entry in loaded_entries:
            runtime_data = getattr(entry, "runtime_data", None)
            if isinstance(runtime_data, dict):
                client = runtime_data.get("client")
            elif runtime_data is not None:
                client = getattr(runtime_data, "client", runtime_data)
            else:
                client = None
            if client:
                clients.append(client)
    return clients


def _resolve_service_targets(hass: HomeAssistant, call: ServiceCall) -> list[Any]:
    """Resolve the clients addressed by a service call, or fail loudly."""
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


def _validate_launch_app_data(data: dict[str, Any]) -> dict[str, Any]:
    """Require an app name/URL or an application ID for launch_app."""
    if not data.get(ATTR_APP) and not data.get(ATTR_APP_ID):
        raise vol.Invalid("Provide either 'app' or 'app_id'.")
    return data


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


def parse_key_sequence(raw_sequence: Any) -> list[str]:
    """Parses raw key sequence string (comma-separated) or list/tuple into cleaned keys."""
    if isinstance(raw_sequence, str):
        return [k.strip() for k in raw_sequence.split(",") if k.strip()]
    if isinstance(raw_sequence, (list, tuple)):
        return [str(k).strip() for k in raw_sequence if str(k).strip()]
    return []
