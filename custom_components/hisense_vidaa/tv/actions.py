"""TV actions and command execution for Hisense VIDAA TV."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from .navigation import (
    get_next_cycled_source,
    match_app,
    resolve_command_key,
    resolve_source,
)
from .settings import (
    DEFAULT_MENU_ID_BACKLIGHT,
    DEFAULT_MENU_ID_BRIGHTNESS,
    DEFAULT_MENU_ID_CONTRAST,
    DEFAULT_MENU_ID_PICTURE_MODE,
    DEFAULT_MENU_ID_SOUND_MODE,
    find_menu_item_by_name,
)

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def query_initial_state(client: HisenseTvClient) -> None:
    """Queries initial state, volume, source list, app list, and settings from TV."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(client.topicTVUIBasepath + "actions/gettvstate", "")
        time.sleep(0.05)
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/getvolume", "")
        time.sleep(0.05)
        client.mqtt_client.publish(client.topicTVUIBasepath + "actions/sourcelist", "")
        time.sleep(0.05)
        client.mqtt_client.publish(client.topicTVUIBasepath + "actions/applist", "")
        time.sleep(0.05)
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/getdeviceinfo", "")
        time.sleep(0.05)
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/gettvinfo", "")


def show_message(
    client: HisenseTvClient, message: str, title: str | None = None, duration: int = 5
) -> bool:
    """Displays an on-screen toast popup notification on the TV."""
    if not client.connected or not client.mqtt_client:
        _LOGGER.debug("[%s] Cannot show toast message: TV MQTT client not connected", getattr(client, "ip", "unknown"))
        return False

    payload_dict = {
        "message": message,
        "title": title or "",
        "duration": duration,
        "type": "notify",
    }
    payload = json.dumps(payload_dict)
    client.mqtt_client.publish(client.topicTVUIBasepath + "actions/showmessage", payload)
    client.mqtt_client.publish(client.topicTVUIBasepath + "actions/toast", payload)
    return True


def send_key(client: HisenseTvClient, key: str) -> None:
    """Publishes a raw keypress event to the TV."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(client.topicRemoBasepath + "actions/sendkey", key)


def send_command(client: HisenseTvClient, command: str) -> bool:
    """Sends a key command to the TV, automatically resolving known key aliases."""
    if not command:
        return False
    cmd_clean = command.strip().lower()
    if cmd_clean.startswith("app:"):
        app_target = command.split(":", 1)[1].strip()
        return client._launch_app_by_name(app_target)
    if cmd_clean.startswith("source:"):
        src_target = command.split(":", 1)[1].strip()
        return client._change_source_by_name_or_id(src_target)
    if cmd_clean in (
        "input",
        "source",
        "cycle_source",
        "input_cycle",
        "source_cycle",
        "key_input",
        "key_source",
    ):
        return client.cycle_source()
    if cmd_clean in ("input_menu", "source_menu", "key_input_menu", "key_source_menu"):
        client.send_key("KEY_MENU")
        return True

    key_to_send = resolve_command_key(command)
    client.send_key(key_to_send)
    return True


def cycle_source(client: HisenseTvClient) -> bool:
    """Cycles to the next available input source."""
    next_source = get_next_cycled_source(client.sources, client.current_source)
    if not next_source:
        client.send_key("KEY_MENU")
        return True

    sid, sname = next_source
    client.change_source(sid, sname)
    return True


def launch_app_by_name(client: HisenseTvClient, name_or_id: str) -> bool:
    """Launches an app by name or app ID from cached applist."""
    matched = match_app(client.apps, name_or_id)
    if matched:
        client.launch_app(matched["appId"], matched["name"], matched["url"])
        return True

    target_clean = name_or_id.strip().lower()
    if target_clean in ("netflix", "app_netflix"):
        client.send_key("KEY_NETFLIX")
        return True
    if target_clean in ("youtube", "app_youtube"):
        client.send_key("KEY_YOUTUBE")
        return True
    if target_clean in ("prime", "prime video", "app_prime"):
        client.send_key("KEY_PRIME")
        return True

    return False


def change_source_by_name_or_id(client: HisenseTvClient, target: str) -> bool:
    """Switches to source by name (e.g. HDMI1, TV) or numeric sourceid."""
    sid, sname = resolve_source(client.sources, target)
    client.change_source(sid or target.strip(), sname)
    return True


def set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100)."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/changevolume", str(volume))


def change_source(
    client: HisenseTvClient, source_id: str, source_name: str | None = None
) -> None:
    """Switches the active input source on the TV."""
    if not client.connected or not client.mqtt_client:
        return

    sid = str(source_id)
    sname = source_name

    payload_dict: dict[str, Any] = {}
    if sid:
        payload_dict["sourceid"] = sid
    if sname:
        payload_dict["sourcename"] = sname
    if not payload_dict:
        payload_dict = {"sourceid": source_id}

    payload = json.dumps(payload_dict)
    client.mqtt_client.publish(client.topicTVUIBasepath + "actions/changesource", payload)

    # Dual publish for newer VIDAA firmware expecting source name
    if sname and sid != sname and str(sid).isdigit():
        payload_modern = json.dumps({"sourceid": sname, "sourcename": sname})
        client.mqtt_client.publish(client.topicTVUIBasepath + "actions/changesource", payload_modern)

    if str(sid).upper() == "TV" or (sname and str(sname).upper() == "TV") or str(source_id).lower() == "tv":
        client.send_key("KEY_LIVETV")


def launch_app(client: HisenseTvClient, app_id: str, app_name: str, url: str) -> None:
    """Launches an installed Smart TV application."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({
            "appId": app_id,
            "name": app_name,
            "url": url,
            "urlType": 37,
            "appName": app_name,
            "appUrl": url,
        })
        client.mqtt_client.publish(client.topicTVUIBasepath + "actions/launchapp", payload)


def get_picture_settings(client: HisenseTvClient) -> None:
    """Requests current picture settings menu information from the TV."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(
            client.topicTVPSBasepath + "actions/picturesetting",
            json.dumps({"action": "get_menu_info"}),
        )


def set_picture_setting(
    client: HisenseTvClient, menu_id: int, menu_value: str | int | float
) -> None:
    """Changes a specific picture setting value."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({
            "action": "notify_value_changed",
            "menu_id": int(menu_id),
            "menu_value": str(menu_value),
        })
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/picturesetting", payload)
        if int(menu_id) in client.picture_settings:
            client.picture_settings[int(menu_id)].value = menu_value


def set_picture_mode(client: HisenseTvClient, mode: str) -> None:
    """Sets the TV picture mode preset."""
    pm_item = find_menu_item_by_name(client.picture_settings, "Picture Mode", DEFAULT_MENU_ID_PICTURE_MODE)
    menu_id = pm_item.menu_id if pm_item else DEFAULT_MENU_ID_PICTURE_MODE
    client.set_picture_setting(menu_id, mode)
    client.picture_mode = mode


def set_backlight(client: HisenseTvClient, level: int) -> None:
    """Sets the TV backlight level (0–100)."""
    bl_item = find_menu_item_by_name(client.picture_settings, "Backlight", DEFAULT_MENU_ID_BACKLIGHT)
    menu_id = bl_item.menu_id if bl_item else DEFAULT_MENU_ID_BACKLIGHT
    clamped = max(0, min(100, int(level)))
    client.set_picture_setting(menu_id, clamped)
    client.backlight = clamped


def set_brightness(client: HisenseTvClient, level: int) -> None:
    """Sets the TV brightness level (0–100)."""
    br_item = find_menu_item_by_name(client.picture_settings, "Brightness", DEFAULT_MENU_ID_BRIGHTNESS)
    menu_id = br_item.menu_id if br_item else DEFAULT_MENU_ID_BRIGHTNESS
    clamped = max(0, min(100, int(level)))
    client.set_picture_setting(menu_id, clamped)
    client.brightness = clamped


def set_contrast(client: HisenseTvClient, level: int) -> None:
    """Sets the TV contrast level (0–100)."""
    ct_item = find_menu_item_by_name(client.picture_settings, "Contrast", DEFAULT_MENU_ID_CONTRAST)
    menu_id = ct_item.menu_id if ct_item else DEFAULT_MENU_ID_CONTRAST
    clamped = max(0, min(100, int(level)))
    client.set_picture_setting(menu_id, clamped)
    client.contrast = clamped


def get_sound_settings(client: HisenseTvClient) -> None:
    """Requests current sound settings menu information from the TV."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(
            client.topicTVPSBasepath + "actions/soundsetting",
            json.dumps({"action": "get_menu_info"}),
        )


def set_sound_setting(
    client: HisenseTvClient, menu_id: int, menu_value: str | int | float
) -> None:
    """Changes a specific sound setting value."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({
            "action": "notify_value_changed",
            "menu_id": int(menu_id),
            "menu_value": str(menu_value),
        })
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/soundsetting", payload)
        if int(menu_id) in client.sound_settings:
            client.sound_settings[int(menu_id)].value = menu_value


def set_sound_mode(client: HisenseTvClient, mode: str) -> None:
    """Sets the TV sound mode preset."""
    sm_item = find_menu_item_by_name(client.sound_settings, "Sound Mode", DEFAULT_MENU_ID_SOUND_MODE)
    menu_id = sm_item.menu_id if sm_item else DEFAULT_MENU_ID_SOUND_MODE
    client.set_sound_setting(menu_id, mode)
    client.sound_mode = mode


def send_text_input(client: HisenseTvClient, text: str, action: str = "insert") -> None:
    """Sends virtual keyboard string input to active on-screen input/search field."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({"text": text, "action": action})
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/txtinputdata", payload)
        client.mqtt_client.publish(client.topicTVPSBasepath + "actions/bwsinputdata", payload)
