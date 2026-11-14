"""Helper functions for Hisense VIDAA TV."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    device = (
        device_reg.async_get(device_id, include_child_devices=False)
        if hasattr(device_reg, "async_get")
        else None
    )
    if device is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


@callback
def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises HomeAssistantError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id) if hasattr(ent_reg, "async_get") else None

    if (
        entity_entry is None
        or getattr(entity_entry, "device_id", None) is None
        or getattr(entity_entry, "platform", None) != DOMAIN
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity_id",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity_entry.device_id
