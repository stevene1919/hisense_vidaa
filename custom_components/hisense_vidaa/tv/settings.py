"""Picture and Sound setting data structures, menu parsers, and constants for Hisense VIDAA TV."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Common default menu IDs across VIDAA / MTK firmware generations
DEFAULT_MENU_ID_PICTURE_MODE = 91
DEFAULT_MENU_ID_BACKLIGHT = 92
DEFAULT_MENU_ID_BRIGHTNESS = 93
DEFAULT_MENU_ID_CONTRAST = 94
DEFAULT_MENU_ID_COLOR = 95
DEFAULT_MENU_ID_SHARPNESS = 96

DEFAULT_MENU_ID_SOUND_MODE = 1
DEFAULT_MENU_ID_BASS = 2
DEFAULT_MENU_ID_TREBLE = 3
DEFAULT_MENU_ID_EQUALIZER = 4

# Standard Fallback Picture Modes
STANDARD_PICTURE_MODES = [
    "Standard",
    "Cinema Day",
    "Cinema Night",
    "Dynamic",
    "Sports",
    "Game",
    "Filmmaker Mode",
]

# Standard Fallback Sound Modes
STANDARD_SOUND_MODES = [
    "Standard",
    "Theatre",
    "Music",
    "Speech",
    "Late Night",
    "Sports",
]

__all__ = [
    "DEFAULT_MENU_ID_BACKLIGHT",
    "DEFAULT_MENU_ID_BASS",
    "DEFAULT_MENU_ID_BRIGHTNESS",
    "DEFAULT_MENU_ID_COLOR",
    "DEFAULT_MENU_ID_CONTRAST",
    "DEFAULT_MENU_ID_EQUALIZER",
    "DEFAULT_MENU_ID_PICTURE_MODE",
    "DEFAULT_MENU_ID_SHARPNESS",
    "DEFAULT_MENU_ID_SOUND_MODE",
    "DEFAULT_MENU_ID_TREBLE",
    "STANDARD_PICTURE_MODES",
    "STANDARD_SOUND_MODES",
    "SettingMenuItem",
    "find_menu_item_by_name",
    "parse_settings_payload",
]


@dataclass
class SettingMenuItem:
    """Represents a single setting menu option or slider."""

    menu_id: int
    name: str
    value: str | int | float
    options: list[str] = field(default_factory=list)
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def menu_name(self) -> str:
        """Alias for name."""
        return self.name

    @property
    def menu_value(self) -> str | int | float:
        """Alias for value."""
        return self.value

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SettingMenuItem | None:
        """Parses a menu item from raw TV JSON payload."""
        if not isinstance(data, dict):
            return None

        raw_id = None
        for key in ("menu_id", "id", "menuid"):
            if key in data and data[key] is not None:
                raw_id = data[key]
                break
        if raw_id is None:
            return None

        try:
            menu_id = int(raw_id)
        except (ValueError, TypeError):
            return None

        name = str(data.get("menu_name") or data.get("name") or f"Menu_{menu_id}").strip()
        value = data.get("menu_value") if data.get("menu_value") is not None else data.get("value", "")

        # Parse options if available
        options_raw = data.get("menu_opts") or data.get("options") or data.get("opts") or []
        options: list[str] = []
        if isinstance(options_raw, list):
            for opt in options_raw:
                if isinstance(opt, str):
                    options.append(opt.strip())
                elif isinstance(opt, dict) and "name" in opt:
                    options.append(str(opt["name"]).strip())
                elif isinstance(opt, dict) and "value" in opt:
                    options.append(str(opt["value"]).strip())

        min_val = data.get("min_value", data.get("min"))
        max_val = data.get("max_value", data.get("max"))
        step_val = data.get("step")

        return cls(
            menu_id=menu_id,
            name=name,
            value=value,
            options=options,
            min_value=min_val,
            max_value=max_val,
            step=step_val,
            raw_data=data,
        )


def parse_settings_payload(payload: dict[str, Any] | list[Any]) -> list[SettingMenuItem]:
    """Parses a TV settings JSON payload (either dict with menu_info/item list, or raw list) into SettingMenuItems."""
    items_to_parse: list[Any] = []
    if isinstance(payload, list):
        items_to_parse = payload
    elif isinstance(payload, dict):
        if "menu_info" in payload and isinstance(payload["menu_info"], list):
            items_to_parse = payload["menu_info"]
        elif "items" in payload and isinstance(payload["items"], list):
            items_to_parse = payload["items"]
        elif "data" in payload and isinstance(payload["data"], list):
            items_to_parse = payload["data"]
        elif "menu_id" in payload or "id" in payload:
            items_to_parse = [payload]

    results: list[SettingMenuItem] = []
    for raw_item in items_to_parse:
        item = SettingMenuItem.from_dict(raw_item)
        if item:
            results.append(item)
    return results


def find_menu_item_by_name(
    menu_items: list[SettingMenuItem] | dict[int, SettingMenuItem],
    target_name: str,
    default_id: int | None = None,
) -> SettingMenuItem | None:
    """Finds a SettingMenuItem matching target name or fallback ID."""
    items = list(menu_items.values()) if isinstance(menu_items, dict) else menu_items
    if not items:
        return None

    clean_target = re.sub(r"[^a-z0-9]", "", str(target_name).lower())

    # 1. Normalized exact match on name
    for item in items:
        norm_name = re.sub(r"[^a-z0-9]", "", str(item.name).lower())
        if clean_target and norm_name == clean_target:
            return item

    # 2. Substring match
    for item in items:
        norm_name = re.sub(r"[^a-z0-9]", "", str(item.name).lower())
        if clean_target and (clean_target in norm_name or norm_name in clean_target):
            return item

    # 3. Fallback by menu ID
    if default_id is not None:
        for item in items:
            if item.menu_id == default_id:
                return item

    return None
