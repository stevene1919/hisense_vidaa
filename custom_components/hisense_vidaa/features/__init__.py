"""Features and domain logic subpackage for Hisense VIDAA TV."""

from __future__ import annotations

from .navigation import (
    KEY_ALIASES,
    change_source_by_name_or_id,
    cycle_tv_source,
    get_next_cycled_source,
    launch_app_by_name,
    match_app,
    normalize_string,
    resolve_command_key,
    resolve_source,
)
from .probe import (
    FeatureProbeResult,
    create_client_from_creds,
    format_probe_results_markdown,
    generate_markdown_report,
    load_credentials_file,
    probe_tv_auth_methods,
    probe_tv_features,
    probe_tv_features_and_report,
    save_credentials_file,
)
from .settings import (
    DEFAULT_MENU_ID_BACKLIGHT,
    DEFAULT_MENU_ID_BRIGHTNESS,
    DEFAULT_MENU_ID_CONTRAST,
    DEFAULT_MENU_ID_PICTURE_MODE,
    DEFAULT_MENU_ID_SOUND_MODE,
    STANDARD_PICTURE_MODES,
    STANDARD_SOUND_MODES,
    SettingMenuItem,
    find_menu_item_by_name,
    parse_settings_payload,
)

__all__ = [
    "DEFAULT_MENU_ID_BACKLIGHT",
    "DEFAULT_MENU_ID_BRIGHTNESS",
    "DEFAULT_MENU_ID_CONTRAST",
    "DEFAULT_MENU_ID_PICTURE_MODE",
    "DEFAULT_MENU_ID_SOUND_MODE",
    "KEY_ALIASES",
    "STANDARD_PICTURE_MODES",
    "STANDARD_SOUND_MODES",
    "FeatureProbeResult",
    "SettingMenuItem",
    "change_source_by_name_or_id",
    "create_client_from_creds",
    "cycle_tv_source",
    "find_menu_item_by_name",
    "format_probe_results_markdown",
    "generate_markdown_report",
    "get_next_cycled_source",
    "launch_app_by_name",
    "load_credentials_file",
    "match_app",
    "normalize_string",
    "parse_settings_payload",
    "probe_tv_auth_methods",
    "probe_tv_features",
    "probe_tv_features_and_report",
    "resolve_command_key",
    "resolve_source",
    "save_credentials_file",
]
