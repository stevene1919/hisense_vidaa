"""Hisense VIDAA TV triggers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import Trigger

from .triggers.turn_on import TurnOnTrigger

TRIGGERS: dict[str, type[Trigger]] = {
    "turn_on": TurnOnTrigger,
}


async def async_get_triggers(_hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for Hisense VIDAA TV."""
    return TRIGGERS
