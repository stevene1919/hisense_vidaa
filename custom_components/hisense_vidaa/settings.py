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

    @property
    def menu_name(self) -> str:
        """Alias for name."""
        return self.name

    @property
    def menu_value(self) -> str | int | float:
        """Alias for value."""
        return self.value

    @property
    def menu_type(self) -> str:
        """Return inferred or raw menu type."""
        return str(self.raw_data.get("menu_type") or ("list" if self.options else "slider" if self.min_value is not None else "setting"))


def normalize_setting_name(name: str) -> str:
    """Normalizes setting name for fuzzy key lookup."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def parse_settings_payload(payload_dict: dict[str, Any]) -> dict[int, SettingMenuItem]:
    """Parses a full menu_info response from the TV into a dictionary of SettingMenuItems."""
    items: dict[int, SettingMenuItem] = {}
    if not isinstance(payload_dict, dict):
        return items

    menu_info = (
        payload_dict.get("menu_info")
        or payload_dict.get("menu_list")
        or payload_dict.get("items")
        or []
    )

    if isinstance(menu_info, list):
        for raw in menu_info:
            item = SettingMenuItem.from_dict(raw)
            if item:
                items[item.menu_id] = item

    return items


def find_menu_item_by_name(
    items: dict[int, SettingMenuItem] | list | None,
    target_name: str,
    default_id: int | None = None,
) -> SettingMenuItem | None:
    """Finds a setting item by name or alias."""
    if not items:
        return None
    if isinstance(items, list):
        parsed_items = {}
        for x in items:
            if isinstance(x, SettingMenuItem):
                parsed_items[x.menu_id] = x
            elif isinstance(x, dict) and "menu_id" in x:
                item = SettingMenuItem.from_dict(x)
                if item:
                    parsed_items[item.menu_id] = item
        items = parsed_items

    if not isinstance(items, dict):
        return None

    norm_target = normalize_setting_name(target_name)
    for item in items.values():
        if normalize_setting_name(item.name) == norm_target:
            return item
        if norm_target in normalize_setting_name(item.name):
            return item

    if default_id is not None and default_id in items:
        return items[default_id]

    return None
