"""Media execution, playback commands, and source resolution for Hisense VIDAA TV."""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import HisenseTvClient

__all__ = [
    "build_media_channel_label",
    "build_media_player_current_source",
    "build_media_player_source_list",
    "clean_source_label",
    "execute_play_media",
    "execute_select_source",
    "parse_applist_data",
    "parse_applist_payload",
    "parse_media_state_broadcast",
    "parse_sourcelist_data",
    "parse_sourcelist_payload",
    "parse_volume_broadcast",
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

    for app in apps:
        if isinstance(app, dict) and (app.get("appId") or app.get("app_id")):
            app_id = str(app.get("appId") or app.get("app_id", ""))
            name = app.get("appName") or app.get("name", "")
            if name:
                app_dict[app_id] = name
                if app.get("isFav") in (True, "true", 1, "1"):
                    favorite_apps.append(name)
                raw_icon_url = app.get("httpIcon")
                if raw_icon_url and "http" in raw_icon_url:
                    clean_url = "http" + raw_icon_url.split("http", 1)[1]
                    app_icons[name] = clean_url
                    app_icons[app_id] = clean_url

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

    for source in sources:
        if isinstance(source, dict):
            source_name = (
                source.get("sourcename")
                or source.get("sourceName")
                or source.get("displayname")
                or source.get("name")
            )
            if source_name:
                available_sources.append(source_name)
                if source.get("has_signal") in ("1", 1, True):
                    connected_inputs.append(source_name)
                custom_label = source.get("displayname2")
                if custom_label and str(custom_label).strip():
                    custom_labels[source_name] = str(custom_label).strip()

            if (
                source.get("is_signal") in ("1", 1, True)
                or source.get("is_active")
                or source.get("isactive")
                or source.get("active")
            ):
                active_source = source_name

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
    for source_name in source_dict.keys():
        if "hdmi" in source_name.lower() or source_name.lower() in ("tv", "av"):
            if enable_cec and source_name == current_source and connected_device and "hdmi" in source_name.lower():
                sources.append(f"{source_name} ({connected_device})")
            else:
                sources.append(source_name)

    if include_apps and app_dict:
        app_names = sorted(app_dict.keys())
        return sorted(sources) + app_names

    return sorted(sources)


def execute_play_media(
    client: HisenseTvClient,
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
            client.launch_app(
                str(app.get("appId") or app.get("app_id") or ""),
                str(app.get("name") or ""),
                str(app.get("url") or app.get("appUrl") or ""),
            )
            return
        for app_name, app_info in app_dict.items():
            if app_name.lower() == media_id.lower() or (
                str(app_info.get("url") or "").lower() == media_id.lower()
            ):
                client.launch_app(
                    str(app_info.get("appId") or app_info.get("app_id") or ""),
                    str(app_info.get("name") or app_name),
                    str(app_info.get("url") or app_info.get("appUrl") or ""),
                )
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
    client: HisenseTvClient,
    source_dict: dict[str, dict[str, Any]],
    app_dict: dict[str, dict[str, Any]],
    source: str,
) -> None:
    """Resolves and selects a source input or smart TV application."""
    if not source:
        return
    cleaned_source = clean_source_label(source)
    source_lower = source.strip().lower()
    cleaned_lower = cleaned_source.strip().lower()

    # 1. Check app dictionary (exact and case-insensitive)
    app = app_dict.get(source) or app_dict.get(cleaned_source)
    if not app:
        for app_name, app_data in app_dict.items():
            if isinstance(app_data, dict) and app_name.lower() in (source_lower, cleaned_lower):
                app = app_data
                break
    if app:
        client.launch_app(str(app.get("appId", "")), str(app.get("name", "")), str(app.get("url", "")))
        return

    # 2. Input source match (exact and case-insensitive)
    matched_source = source_dict.get(source) or source_dict.get(cleaned_source)
    if not matched_source:
        for source_name, source_data in source_dict.items():
            if isinstance(source_data, dict) and source_name.lower() in (source_lower, cleaned_lower):
                matched_source = source_data
                break
    if matched_source:
        resolved_source_id = str(matched_source.get("sourceid") or matched_source.get("sourcename") or "")
        resolved_source_name = str(matched_source.get("sourcename") or cleaned_source)
        client.change_source(resolved_source_id, resolved_source_name)
        return

    client.change_source(cleaned_source)


def parse_media_state_broadcast(
    data: dict[str, Any],
) -> dict[str, Any]:
    """Parses raw TV state broadcast message into structured media player state fields."""
    statetype = data.get("statetype")
    statetype_l = str(statetype or "").lower()
    result: dict[str, Any] = {
        "statetype": statetype,
        "is_on": True,
        "state": "on",
        "source": None,
        "connected_device": None,
        "channel_name": None,
        "channel_num": None,
    }

    # Keep this in lock-step with tv/state.py: only fake_sleep_0 (exact) or any
    # statetype containing "off" is off; fake_sleep_1 is the TV waking up.
    if statetype_l == "fake_sleep_0" or "off" in statetype_l:
        result["is_on"] = False
        result["state"] = "off"
    elif statetype_l == "fake_sleep_1":
        result["is_on"] = True
        result["state"] = "on"
    elif statetype == "sourceswitch":
        result["source"] = data.get("sourcename") or data.get("displayname")
        result["connected_device"] = data.get("displayname2") or data.get("source_detail")
    elif statetype == "app":
        result["source"] = data.get("name")
    elif statetype == "livetv":
        result["source"] = "TV"
        result["channel_name"] = data.get("channel_name")
        result["channel_num"] = data.get("channel_num")

    return result


def parse_volume_broadcast(
    data: dict[str, Any],
    current_volume: int,
    current_volume_type: int,
    current_muted: bool,
) -> tuple[int, int, bool]:
    """Parses incoming volume broadcast. Returns (volume, volume_type, muted)."""
    # Coerce string payloads (the TV sometimes sends "0"/"1"/"2") the same way
    # tv/state.py::apply_volume_update tolerates them.
    vol_type = data.get("volume_type")
    volume = current_volume
    volume_type = current_volume_type
    muted = current_muted

    if vol_type in (0, "0", 1, "1"):
        volume_type = int(vol_type)
        with contextlib.suppress(ValueError, TypeError):
            volume = int(data.get("volume_value", current_volume))
    elif vol_type in (2, "2"):
        muted = data.get("volume_value") in (1, "1", True)

    return volume, volume_type, muted


def parse_sourcelist_data(data: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """Builds a lookup dictionary of sources keyed by sourcename."""
    result: dict[str, dict[str, Any]] = {}
    if not data:
        return result
    for item in data:
        if not isinstance(item, dict):
            continue
        # Accept the same key spellings as parse_sourcelist_payload.
        name = (
            item.get("sourcename")
            or item.get("sourceName")
            or item.get("displayname")
            or item.get("name")
        )
        if name:
            result[name] = item
    return result


def parse_applist_data(
    data: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Builds a list and dictionary of installed apps keyed by name."""
    if not data:
        return [], {}
    app_dict: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        # Accept the same key spellings as parse_applist_payload.
        name = item.get("name") or item.get("appName")
        if name:
            app_dict[name] = item
    return data, app_dict

