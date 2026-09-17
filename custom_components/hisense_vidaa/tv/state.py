"""State models and telemetry parsers for Hisense VIDAA TV."""

from __future__ import annotations

import contextlib
from typing import Any

try:
    from .settings import parse_settings_payload
except (ImportError, ValueError):
    from tv.settings import parse_settings_payload


def apply_state_update(client: Any, data: Any) -> None:
    """Updates client runtime state attributes from TV state payload."""
    if not isinstance(data, dict):
        return

    statetype = str(data.get("statetype", "")).lower()
    if "sleep" in statetype or "off" in statetype or statetype == "fake_sleep_0":
        client.state = "off"
    elif statetype in ("screen_saver", "screensaver"):
        client.state = "screensaver"
    elif statetype or data.get("is_power_on") in (1, "1", True):
        client.state = "on"

    if "sourcename" in data:
        client.current_source = data["sourcename"]
    if "sourceid" in data:
        client.current_source_id = str(data["sourceid"])
    if "appname" in data:
        client.current_app = data["appname"]
    if "appid" in data:
        client.current_app_id = str(data["appid"])
    if "channel_name" in data:
        client.current_channel = data["channel_name"]
    if "program_title" in data:
        client.current_program = data["program_title"]
    if "channel_num" in data:
        client.channel_number = str(data["channel_num"])
    if "audio_output" in data:
        client.audio_output_mode = str(data["audio_output"])
    if "hdr_mode" in data:
        client.hdr_mode = str(data["hdr_mode"])
    if "audio_format" in data:
        client.audio_format = str(data["audio_format"])
    if "devicename" in data or "device_name" in data or "friendly_name" in data:
        name = data.get("devicename") or data.get("device_name") or data.get("friendly_name")
        if name and str(name).strip() and str(name).strip() != "Renderer":
            client.device_name = str(name).strip()
    if "sleep_time" in data:
        with contextlib.suppress(ValueError, TypeError):
            client.sleep_timer = int(data["sleep_time"])


def apply_device_info_update(client: Any, data: Any) -> None:
    """Updates client device information attributes from TV device info payload."""
    if not isinstance(data, dict):
        return

    name = (
        data.get("devicename")
        or data.get("device_name")
        or data.get("friendly_name")
        or data.get("tv_name")
        or data.get("name")
    )
    if name and str(name).strip() and str(name).strip() != "Renderer":
        client.device_name = str(name).strip()

    model = (
        data.get("model_name")
        or data.get("model_code")
        or data.get("model")
        or data.get("modelNumber")
    )
    if model and str(model).strip():
        client.model_name = str(model).strip()

    mfg = data.get("manufacturer") or data.get("brand")
    if mfg and str(mfg).strip():
        client.manufacturer = str(mfg).strip()

    fw = data.get("firmware_version") or data.get("sw_version") or data.get("version")
    if fw and str(fw).strip():
        client.firmware_version = str(fw).strip()


def apply_volume_update(client: Any, data: Any) -> None:
    """Updates client volume and mute attributes from TV volume payload."""
    if not isinstance(data, dict):
        return

    if "volume_value" in data:
        with contextlib.suppress(ValueError, TypeError):
            client.volume = int(data["volume_value"])
    elif "volume" in data:
        with contextlib.suppress(ValueError, TypeError):
            client.volume = int(data["volume"])

    if "volume_type" in data:
        client.muted = bool(data["volume_type"] == 1 or data["volume_type"] == "1")
    elif "is_mute" in data:
        client.muted = bool(data["is_mute"] in (1, "1", True))
    elif "muted" in data:
        client.muted = bool(data["muted"])


def apply_picture_update(client: Any, data: Any) -> None:
    """Updates client picture settings from TV picture settings payload."""
    parsed_items = parse_settings_payload(data)
    for item in parsed_items:
        client.picture_settings[item.menu_id] = item
        name_clean = item.name.lower()
        if "mode" in name_clean:
            client.picture_mode = str(item.value)
        elif "backlight" in name_clean:
            with contextlib.suppress(ValueError, TypeError):
                client.backlight = int(item.value)
        elif "brightness" in name_clean:
            with contextlib.suppress(ValueError, TypeError):
                client.brightness = int(item.value)
        elif "contrast" in name_clean:
            with contextlib.suppress(ValueError, TypeError):
                client.contrast = int(item.value)


def apply_sound_update(client: Any, data: Any) -> None:
    """Updates client sound settings from TV sound settings payload."""
    parsed_items = parse_settings_payload(data)
    for item in parsed_items:
        client.sound_settings[item.menu_id] = item
        if "mode" in item.name.lower():
            client.sound_mode = str(item.value)
