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
]


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
    clean_src = clean_source_label(source)

    # Check app dictionary for direct match or cleaned match
    app = app_dict.get(source) or app_dict.get(clean_src)
    if app:
        client.launch_app(app.get("appId", ""), app.get("name", ""), app.get("url", ""))
        return

    # Input source match
    src = source_dict.get(source) or source_dict.get(clean_src)
    if src:
        sid = str(src.get("sourceid") or src.get("sourcename") or "")
        sname = str(src.get("sourcename") or clean_src)
        client.change_source(sid, sname)
        return

    client.change_source(clean_src)
