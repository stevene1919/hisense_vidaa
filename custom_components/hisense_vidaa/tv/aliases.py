"""Key and smart application alias definitions for Hisense VIDAA TV."""

from __future__ import annotations

from .aliases_apps import (
    ALL_APP_ALIASES,
    GLOBAL_APP_ALIASES,
    REGIONAL_APP_ALIASES_ASIA,
    REGIONAL_APP_ALIASES_AU_NZ,
    REGIONAL_APP_ALIASES_EASTERN_EU,
    REGIONAL_APP_ALIASES_NA,
    REGIONAL_APP_ALIASES_UK_EU,
)
from .aliases_keys import KEY_ALIASES

# ------------------------------------------------------------------------------
# Combined Complete Aliases Map
# ------------------------------------------------------------------------------
ALL_KEY_AND_APP_ALIASES: dict[str, str] = {
    **KEY_ALIASES,
    **ALL_APP_ALIASES,
}

__all__ = [
    "ALL_APP_ALIASES",
    "ALL_KEY_AND_APP_ALIASES",
    "GLOBAL_APP_ALIASES",
    "KEY_ALIASES",
    "REGIONAL_APP_ALIASES_ASIA",
    "REGIONAL_APP_ALIASES_AU_NZ",
    "REGIONAL_APP_ALIASES_EASTERN_EU",
    "REGIONAL_APP_ALIASES_NA",
    "REGIONAL_APP_ALIASES_UK_EU",
]
