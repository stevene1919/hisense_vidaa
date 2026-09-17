"""Backward-compatible re-exports for settings module.

Logic has moved to `features.settings`.
"""

from __future__ import annotations

try:
    from .features.settings import (
        DEFAULT_MENU_ID_BACKLIGHT,
        DEFAULT_MENU_ID_BASS,
        DEFAULT_MENU_ID_BRIGHTNESS,
        DEFAULT_MENU_ID_COLOR,
        DEFAULT_MENU_ID_CONTRAST,
        DEFAULT_MENU_ID_EQUALIZER,
        DEFAULT_MENU_ID_PICTURE_MODE,
        DEFAULT_MENU_ID_SHARPNESS,
        DEFAULT_MENU_ID_SOUND_MODE,
        DEFAULT_MENU_ID_TREBLE,
        STANDARD_PICTURE_MODES,
        STANDARD_SOUND_MODES,
        SettingMenuItem,
        find_menu_item_by_name,
        parse_settings_payload,
    )
except (ImportError, ValueError):
    from features.settings import (
        DEFAULT_MENU_ID_BACKLIGHT,
        DEFAULT_MENU_ID_BASS,
        DEFAULT_MENU_ID_BRIGHTNESS,
        DEFAULT_MENU_ID_COLOR,
        DEFAULT_MENU_ID_CONTRAST,
        DEFAULT_MENU_ID_EQUALIZER,
        DEFAULT_MENU_ID_PICTURE_MODE,
        DEFAULT_MENU_ID_SHARPNESS,
        DEFAULT_MENU_ID_SOUND_MODE,
        DEFAULT_MENU_ID_TREBLE,
        STANDARD_PICTURE_MODES,
        STANDARD_SOUND_MODES,
        SettingMenuItem,
        find_menu_item_by_name,
        parse_settings_payload,
    )

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
