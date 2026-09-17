"""Media execution, playback commands, and source resolution for Hisense VIDAA TV."""

from __future__ import annotations

import time
from typing import Any

__all__ = [
    "build_media_channel_label",
    "build_media_player_current_source",
    "build_media_player_source_list",
    "clean_source_label",
    "execute_play_media",
    "execute_select_source",
    "parse_applist_payload",
    "parse_sourcelist_payload",
]


def parse_applist_payload(
    apps: list[dict[str, Any]] | None,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Parses raw TV app list payload into app_dict, icon_map, and favorite_apps.

    Returns:
        (app_dict: {app_id: name}, app_icons: {name_or_id: clean_url}, favorite_apps: [name, ...])
    """
    app_dict: dict[str, str] = {}
    app_icons: dict[str, str] = {}
    favorite_apps: list[str] = []
    if not apps:
        return app_dict, app_icons, favorite_apps

    for a in apps:
        if isinstance(a, dict) and (a.get("appId") or a.get("app_id")):
            a_id = str(a.get("appId") or a.get("app_id", ""))
            name = a.get("appName") or a.get("name", "")
            if name:
                app_dict[a_id] = name
                if a.get("isFav") in (True, "true", 1, "1"):
                    favorite_apps.append(name)
                icon_raw = a.get("httpIcon")
                if icon_raw and "http" in icon_raw:
                    clean_url = "http" + icon_raw.split("http", 1)[1]
                    app_icons[name] = clean_url
                    app_icons[a_id] = clean_url

    return app_dict, app_icons, favorite_apps


def parse_sourcelist_payload(
    sources: list[dict[str, Any]] | None,
) -> tuple[list[str], list[str], dict[str, str], str | None]:
    """Parses raw TV source list payload.

    Returns:
        (available_sources: [name, ...], connected_inputs: [name, ...], custom_labels: {name: custom_label}, active_source: str | None)
    """
    available_sources: list[str] = []
    connected_inputs: list[str] = []
    custom_labels: dict[str, str] = {}
    active_source: str | None = None
    if not sources:
        return available_sources, connected_inputs, custom_labels, active_source

    for s in sources:
        if isinstance(s, dict):
            src_name = s.get("sourcename") or s.get("sourceName") or s.get("displayname") or s.get("name")
            if src_name:
                available_sources.append(src_name)
                if s.get("has_signal") in ("1", 1, True):
                    connected_inputs.append(src_name)
                custom_label = s.get("displayname2")
                if custom_label and str(custom_label).strip():
                    custom_labels[src_name] = str(custom_label).strip()

            if (
                s.get("is_signal") in ("1", 1, True)
                or s.get("is_active")
                or s.get("isactive")
                or s.get("active")
            ):
                active_source = src_name

    return available_sources, connected_inputs, custom_labels, active_source


def clean_source_label(source: str) -> str:
    """Strips trailing HDMI-CEC device annotations (e.g. 'HDMI 2 (PlayStation 5)' -> 'HDMI 2')."""
    return source.split(" (")[0].strip() if " (" in source else source.strip()


def build_media_channel_label(channel_name: str | None, channel_num: str | None) -> str | None:
    """Formats human-readable Live TV channel identifier."""
    if channel_name and channel_num:
        return f"{channel_num} {channel_name}"
    return channel_name or channel_num


def build_media_player_current_source(
    source: str | None,
    connected_device: str | None,
    enable_cec: bool = True,
) -> str | None:
    """Builds the active source name, optionally augmenting with HDMI-CEC connected device names."""
    if enable_cec and source and connected_device and "hdmi" in source.lower():
        return f"{source} ({connected_device})"
    return source


def build_media_player_source_list(
    source_dict: dict[str, dict[str, Any]],
    app_dict: dict[str, dict[str, Any]],
    current_source: str | None = None,
    connected_device: str | None = None,
    enable_cec: bool = True,
    include_apps: bool = True,
) -> list[str]:
    """Builds the full sorted list of selectable inputs and smart TV apps."""
    sources: list[str] = []
    for s in source_dict.keys():
        if "hdmi" in s.lower() or s.lower() in ("tv", "av"):
            if enable_cec and s == current_source and connected_device and "hdmi" in s.lower():
                sources.append(f"{s} ({connected_device})")
            else:
                sources.append(s)

    if include_apps and app_dict:
        app_names = sorted(app_dict.keys())
        return sorted(sources) + app_names

    return sorted(sources)


def execute_play_media(
    client: Any,
    app_dict: dict[str, dict[str, Any]],
    media_type: str,
    media_id: str,
) -> None:
    """Executes media playback command: launches app, tunes channel number, or sends key."""
    type_lower = media_type.lower()
    if type_lower in ("app", "application", "url", "deep_link", "video", "music") or "://" in media_id:
        # Check app dictionary for direct match or scheme match
        app = app_dict.get(media_id)
        if app:
            client.launch_app(app["appId"], app["name"], app["url"])
            return
        for a_name, a_info in app_dict.items():
            if a_name.lower() == media_id.lower() or a_info.get("url", "").lower() == media_id.lower():
                client.launch_app(a_info["appId"], a_info["name"], a_info["url"])
                return

        # Direct URL / deep-link launch
        if "://" in media_id or type_lower in ("url", "deep_link"):
            client.launch_app("", media_id, media_id)
            return

    if type_lower in ("channel", "tvshow"):
        for char in str(media_id):
            if char.isdigit():
                client.send_key(f"KEY_{char}")
                time.sleep(0.1)
            elif char in (".", "-"):
                client.send_key("KEY_CHANNELDOT")
                time.sleep(0.1)
        return

    client.send_command(media_id)


def execute_select_source(
    client: Any,
    source_dict: dict[str, dict[str, Any]],
    app_dict: dict[str, dict[str, Any]],
    source: str,
) -> None:
    """Resolves and selects a source input or smart TV application."""
    if not source:
        return
    clean_src = clean_source_label(source)
    source_lower = source.strip().lower()
    clean_lower = clean_src.strip().lower()

    # 1. Check app dictionary (exact and case-insensitive)
    app = app_dict.get(source) or app_dict.get(clean_src)
    if not app:
        for name, a in app_dict.items():
            if isinstance(a, dict) and name.lower() in (source_lower, clean_lower):
                app = a
                break
    if app:
        client.launch_app(str(app.get("appId", "")), str(app.get("name", "")), str(app.get("url", "")))
        return

    # 2. Input source match (exact and case-insensitive)
    src = source_dict.get(source) or source_dict.get(clean_src)
    if not src:
        for name, s in source_dict.items():
            if isinstance(s, dict) and name.lower() in (source_lower, clean_lower):
                src = s
                break
    if src:
        sid = str(src.get("sourceid") or src.get("sourcename") or "")
        sname = str(src.get("sourcename") or clean_src)
        client.change_source(sid, sname)
        return

    client.change_source(clean_src)
