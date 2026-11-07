"""TV actions and command execution for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import functools
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
    async_get_picture_settings,
    async_get_sound_settings,
    async_set_backlight,
    async_set_brightness,
    async_set_contrast,
    async_set_picture_mode,
    async_set_picture_setting,
    async_set_sound_mode,
    async_set_sound_setting,
    get_picture_settings,
    get_sound_settings,
    set_backlight,
    set_brightness,
    set_contrast,
    set_picture_mode,
    set_picture_setting,
    set_sound_mode,
    set_sound_setting,
)

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def query_initial_state(client: HisenseTvClient, min_interval: float = 3.0) -> None:
    """Queries initial state, volume, source list, app list, and settings from TV."""
    if not (client.connected and client.mqtt_client):
        return

    now = time.time()
    with getattr(client, "_query_lock", contextlib.nullcontext()):
        last_time = getattr(client, "_last_initial_query_time", 0.0)
        if now - last_time < min_interval:
            _LOGGER.debug(
                "[%s] Suppressing duplicate query_initial_state call (%.2fs since last query)",
                client.ip,
                now - last_time,
            )
            return
        client._last_initial_query_time = now

        # The TV already broadcasts its live state automatically on
        # /remoteapp/mobile/broadcast/ui_service/state upon MQTT connect.
        # Do NOT publish actions/gettvstate: on VIDAA firmware, gettvstate
        # is the pairing challenge trigger that commands the TV to pop up a PIN.
        client.mqtt_client.publish(f"{client.topics.ui}actions/capability", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.platform}actions/getvolume", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.ui}actions/sourcelist", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.ui}actions/applist", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.platform}actions/getdeviceinfo", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.platform}actions/gettvinfo", "")


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
    client.mqtt_client.publish(f"{client.topics.ui}actions/showmessage", payload)
    client.mqtt_client.publish(f"{client.topics.ui}actions/toast", payload)
    return True


def send_key(client: HisenseTvClient, key: str) -> None:
    """Publishes a raw keypress event to the TV."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(f"{client.topics.remote}actions/sendkey", key)


def send_command(client: HisenseTvClient, command: str) -> bool:
    """Sends a key command to the TV, automatically resolving known key aliases."""
    if not command:
        return False
    normalized_command = command.strip().lower()
    if normalized_command.startswith("app:"):
        app_target = command.split(":", 1)[1].strip()
        return client._launch_app_by_name(app_target)
    if normalized_command.startswith("source:"):
        source_target = command.split(":", 1)[1].strip()
        return client._change_source_by_name_or_id(source_target)
    if normalized_command in (
        "input",
        "source",
        "cycle_source",
        "input_cycle",
        "source_cycle",
        "key_input",
        "key_source",
    ):
        return client.cycle_source()
    if normalized_command in ("input_menu", "source_menu", "key_input_menu", "key_source_menu"):
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

    next_source_id, next_source_name = next_source
    client.change_source(next_source_id, next_source_name)
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
    resolved_source_id, resolved_source_name = resolve_source(client.sources, target)
    client.change_source(resolved_source_id or target.strip(), resolved_source_name)
    return True


def set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100)."""
    if client.connected and client.mqtt_client:
        client.mqtt_client.publish(f"{client.topics.platform}actions/changevolume", str(volume))


def change_source(
    client: HisenseTvClient, source_id: str, source_name: str | None = None
) -> None:
    """Switches the active input source on the TV."""
    if not client.connected or not client.mqtt_client:
        return

    clean_source_id = str(source_id).strip()
    clean_source_name = source_name.strip() if source_name else None

    if not clean_source_name:
        resolved_id, resolved_name = resolve_source(getattr(client, "sources", []), clean_source_id)
        if resolved_name:
            clean_source_name = resolved_name
        if resolved_id:
            clean_source_id = resolved_id

    payload_dict: dict[str, Any] = {}
    if clean_source_id:
        payload_dict["sourceid"] = clean_source_id
    if clean_source_name:
        payload_dict["sourcename"] = clean_source_name
    if not payload_dict:
        payload_dict = {"sourceid": source_id}

    payload = json.dumps(payload_dict)
    client.mqtt_client.publish(f"{client.topics.ui}actions/changesource", payload)

    # Dual publish for newer VIDAA firmware expecting source name
    if clean_source_name and clean_source_id != clean_source_name and str(clean_source_id).isdigit():
        _LOGGER.debug(
            "[%s] changesource: also attempting name-as-id publish (sourceid=%s) for firmware expecting the display name",
            getattr(client, "ip", "unknown"),
            clean_source_name,
        )
        payload_modern = json.dumps({"sourceid": clean_source_name, "sourcename": clean_source_name})
        client.mqtt_client.publish(f"{client.topics.ui}actions/changesource", payload_modern)

    if (
        str(clean_source_id).upper() == "TV"
        or (clean_source_name and str(clean_source_name).upper() == "TV")
        or str(source_id).lower() == "tv"
    ):
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
        client.mqtt_client.publish(f"{client.topics.ui}actions/launchapp", payload)


def send_text_input(client: HisenseTvClient, text: str, action: str = "insert") -> None:
    """Sends virtual keyboard string input to active on-screen input/search field."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({"text": text, "action": action})
        client.mqtt_client.publish(f"{client.topics.platform}actions/txtinputdata", payload)
        client.mqtt_client.publish(f"{client.topics.platform}actions/bwsinputdata", payload)


def turn_on_tv(
    client: HisenseTvClient,
    mac_targets: list[str] | None = None,
) -> None:
    """Powers on or wakes the TV safely and idempotently."""
    if mac_targets:
        client.send_wake_on_lan(mac_targets, ip=getattr(client, "ip", None))

    if client.connected:
        if not client.is_on and getattr(client, "has_active_signal", False) is not True:
            _LOGGER.debug(
                "[%s] TV connected in standby/fake_sleep. Sending KEY_POWER to wake screen",
                getattr(client, "ip", "unknown"),
            )
            client.send_key("KEY_POWER")
        else:
            client.is_on = True
            _LOGGER.debug(
                "[%s] TV already connected and running. Skipping KEY_POWER to prevent powering down",
                getattr(client, "ip", "unknown"),
            )
    else:
        _LOGGER.debug(
            "[%s] TV MQTT not connected. Attempting reconnect to send KEY_POWER",
            getattr(client, "ip", "unknown"),
        )
        try:
            if client.ensure_connected():
                for _ in range(50):
                    if client.connected:
                        client.send_key("KEY_POWER")
                        break
                    time.sleep(0.1)
        except Exception as e:
            _LOGGER.error(
                "[%s] Failed to reconnect and send KEY_POWER: %s",
                getattr(client, "ip", "unknown"),
                e,
            )

    client.is_on = True


def turn_off_tv(client: HisenseTvClient) -> None:
    """Powers off the TV safely."""
    if client.connected and client.is_on:
        client.send_key("KEY_POWER")
    client.is_on = False


async def async_query_initial_state(client: HisenseTvClient, min_interval: float = 3.0) -> None:
    """Queries initial state, volume, source list, app list, and settings from TV asynchronously."""
    if not (client.connected and client.mqtt_client):
        return

    now = time.time()
    last_time = getattr(client, "_last_initial_query_time", 0.0)
    if now - last_time < min_interval:
        _LOGGER.debug(
            "[%s] Suppressing duplicate query_initial_state call (%.2fs since last query)",
            getattr(client, "ip", "unknown"),
            now - last_time,
        )
        return
    client._last_initial_query_time = now

    topics = [
        f"{client.topics.ui}actions/capability",
        f"{client.topics.platform}actions/getvolume",
        f"{client.topics.ui}actions/sourcelist",
        f"{client.topics.ui}actions/applist",
        f"{client.topics.platform}actions/getdeviceinfo",
        f"{client.topics.platform}actions/gettvinfo",
    ]
    for topic in topics:
        await client.async_publish(topic, "")
        await asyncio.sleep(0.05)


async def async_show_message(
    client: HisenseTvClient, message: str, title: str | None = None, duration: int = 5
) -> bool:
    """Displays an on-screen toast popup notification on the TV asynchronously."""
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
    await client.async_publish(f"{client.topics.ui}actions/showmessage", payload)
    await client.async_publish(f"{client.topics.ui}actions/toast", payload)
    return True


async def async_send_key(client: HisenseTvClient, key: str) -> None:
    """Publishes a raw keypress event to the TV asynchronously."""
    if client.connected and client.mqtt_client:
        await client.async_publish(f"{client.topics.remote}actions/sendkey", key)


async def async_send_command(client: HisenseTvClient, command: str) -> bool:
    """Sends a key command to the TV asynchronously, automatically resolving known key aliases."""
    if not command:
        return False
    normalized_command = command.strip().lower()
    if normalized_command.startswith("app:"):
        app_target = command.split(":", 1)[1].strip()
        return await client.async_launch_app_by_name(app_target)
    if normalized_command.startswith("source:"):
        source_target = command.split(":", 1)[1].strip()
        return await client.async_change_source_by_name_or_id(source_target)
    if normalized_command in (
        "input",
        "source",
        "cycle_source",
        "input_cycle",
        "source_cycle",
        "key_input",
        "key_source",
    ):
        return await client.async_cycle_source()
    if normalized_command in ("input_menu", "source_menu", "key_input_menu", "key_source_menu"):
        await client.async_send_key("KEY_MENU")
        return True

    key_to_send = resolve_command_key(command)
    await client.async_send_key(key_to_send)
    return True


async def async_cycle_source(client: HisenseTvClient) -> bool:
    """Cycles to the next available input source asynchronously."""
    next_source = get_next_cycled_source(client.sources, client.current_source)
    if not next_source:
        await client.async_send_key("KEY_MENU")
        return True

    next_source_id, next_source_name = next_source
    await client.async_change_source(next_source_id, next_source_name)
    return True


async def async_launch_app_by_name(client: HisenseTvClient, name_or_id: str) -> bool:
    """Launches an app by name or app ID from cached applist asynchronously."""
    matched = match_app(client.apps, name_or_id)
    if matched:
        await client.async_launch_app(matched["appId"], matched["name"], matched["url"])
        return True

    target_clean = name_or_id.strip().lower()
    if target_clean in ("netflix", "app_netflix"):
        await client.async_send_key("KEY_NETFLIX")
        return True
    if target_clean in ("youtube", "app_youtube"):
        await client.async_send_key("KEY_YOUTUBE")
        return True
    if target_clean in ("prime", "prime video", "app_prime"):
        await client.async_send_key("KEY_PRIME")
        return True

    return False


async def async_change_source_by_name_or_id(client: HisenseTvClient, target: str) -> bool:
    """Switches to source by name (e.g. HDMI1, TV) or numeric sourceid asynchronously."""
    resolved_source_id, resolved_source_name = resolve_source(client.sources, target)
    await client.async_change_source(resolved_source_id or target.strip(), resolved_source_name)
    return True


async def async_set_volume(client: HisenseTvClient, volume: int) -> None:
    """Sets the absolute volume on the TV (0–100) asynchronously."""
    if client.connected and client.mqtt_client:
        await client.async_publish(f"{client.topics.platform}actions/changevolume", str(volume))


async def async_change_source(
    client: HisenseTvClient, source_id: str, source_name: str | None = None
) -> None:
    """Switches the active input source on the TV asynchronously."""
    if not client.connected or not client.mqtt_client:
        return

    clean_source_id = str(source_id).strip()
    clean_source_name = source_name.strip() if source_name else None
    if not clean_source_name:
        resolved_id, resolved_name = resolve_source(getattr(client, "sources", []), clean_source_id)
        if resolved_name:
            clean_source_name = resolved_name
        if resolved_id:
            clean_source_id = resolved_id

    payload_dict: dict[str, Any] = {}
    if clean_source_id:
        payload_dict["sourceid"] = clean_source_id
    if clean_source_name:
        payload_dict["sourcename"] = clean_source_name
    if not payload_dict:
        payload_dict = {"sourceid": source_id}

    payload = json.dumps(payload_dict)
    await client.async_publish(f"{client.topics.ui}actions/changesource", payload)

    # Dual publish for newer VIDAA firmware expecting source name
    if clean_source_name and clean_source_id != clean_source_name and str(clean_source_id).isdigit():
        _LOGGER.debug(
            "[%s] changesource: also attempting name-as-id publish (sourceid=%s) for firmware expecting the display name",
            getattr(client, "ip", "unknown"),
            clean_source_name,
        )
        payload_modern = json.dumps({"sourceid": clean_source_name, "sourcename": clean_source_name})
        await client.async_publish(f"{client.topics.ui}actions/changesource", payload_modern)

    if (
        str(clean_source_id).upper() == "TV"
        or (clean_source_name and str(clean_source_name).upper() == "TV")
        or str(source_id).lower() == "tv"
    ):
        await client.async_send_key("KEY_LIVETV")


async def async_launch_app(client: HisenseTvClient, app_id: str, app_name: str, url: str) -> None:
    """Launches an installed Smart TV application asynchronously."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({
            "appId": app_id,
            "name": app_name,
            "url": url,
            "urlType": 37,
            "appName": app_name,
            "appUrl": url,
        })
        await client.async_publish(f"{client.topics.ui}actions/launchapp", payload)


async def async_send_text_input(client: HisenseTvClient, text: str, action: str = "insert") -> None:
    """Sends virtual keyboard string input to active on-screen input/search field asynchronously."""
    if client.connected and client.mqtt_client:
        payload = json.dumps({"text": text, "action": action})
        await client.async_publish(f"{client.topics.platform}actions/txtinputdata", payload)
        await client.async_publish(f"{client.topics.platform}actions/bwsinputdata", payload)


async def async_turn_on_tv(
    client: HisenseTvClient,
    mac_targets: list[str] | None = None,
) -> None:
    """Powers on or wakes the TV safely and idempotently asynchronously."""
    if mac_targets:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, functools.partial(client.send_wake_on_lan, mac_targets, ip=getattr(client, "ip", None))
        )

    if client.connected:
        if not client.is_on and getattr(client, "has_active_signal", False) is not True:
            _LOGGER.debug(
                "[%s] TV connected in standby/fake_sleep. Sending KEY_POWER to wake screen",
                getattr(client, "ip", "unknown"),
            )
            await client.async_send_key("KEY_POWER")
        else:
            client.is_on = True
            _LOGGER.debug(
                "[%s] TV already connected and running. Skipping KEY_POWER to prevent powering down",
                getattr(client, "ip", "unknown"),
            )
    else:
        _LOGGER.debug(
            "[%s] TV MQTT not connected. Attempting reconnect to send KEY_POWER",
            getattr(client, "ip", "unknown"),
        )
        try:
            if await client.async_ensure_connected():
                for _ in range(50):
                    if client.connected:
                        await client.async_send_key("KEY_POWER")
                        break
                    await asyncio.sleep(0.1)
        except Exception as e:
            _LOGGER.error(
                "[%s] Failed to reconnect and send KEY_POWER: %s",
                getattr(client, "ip", "unknown"),
                e,
            )

    client.is_on = True


async def async_turn_off_tv(client: HisenseTvClient) -> None:
    """Powers off the TV safely asynchronously."""
    if client.connected and client.is_on:
        await client.async_send_key("KEY_POWER")
    client.is_on = False


class TvActionsMixin:
    """Mixin providing TV command execution, settings, and navigation actions."""

    def query_initial_state(self) -> None:
        """Queries initial state, volume, source list, app list, and settings from TV."""
        query_initial_state(self)  # type: ignore[arg-type]

    async def async_query_initial_state(self, min_interval: float = 3.0) -> None:
        """Queries initial state, volume, source list, app list, and settings asynchronously."""
        await async_query_initial_state(self, min_interval=min_interval)  # type: ignore[arg-type]

    def turn_on(self, mac_targets: list[str] | None = None) -> None:
        """Powers on or wakes the TV safely and idempotently."""
        turn_on_tv(self, mac_targets=mac_targets)  # type: ignore[arg-type]

    async def async_turn_on(self, mac_targets: list[str] | None = None) -> None:
        """Powers on or wakes the TV safely and idempotently asynchronously."""
        await async_turn_on_tv(self, mac_targets=mac_targets)  # type: ignore[arg-type]

    def turn_off(self) -> None:
        """Powers off the TV safely."""
        turn_off_tv(self)  # type: ignore[arg-type]

    async def async_turn_off(self) -> None:
        """Powers off the TV safely asynchronously."""
        await async_turn_off_tv(self)  # type: ignore[arg-type]

    def show_message(self, message: str, title: str | None = None, duration: int = 5) -> bool:
        """Displays an on-screen toast popup notification on the TV."""
        return show_message(self, message=message, title=title, duration=duration)  # type: ignore[arg-type]

    async def async_show_message(self, message: str, title: str | None = None, duration: int = 5) -> bool:
        """Displays an on-screen toast popup notification on the TV asynchronously."""
        return await async_show_message(self, message=message, title=title, duration=duration)  # type: ignore[arg-type]

    def send_key(self, key: str) -> None:
        """Publishes a raw keypress event to the TV."""
        send_key(self, key=key)  # type: ignore[arg-type]

    async def async_send_key(self, key: str) -> None:
        """Publishes a raw keypress event to the TV asynchronously."""
        await async_send_key(self, key=key)  # type: ignore[arg-type]

    def send_command(self, command: str) -> bool:
        """Sends a key command to the TV, automatically resolving known key aliases."""
        return send_command(self, command=command)  # type: ignore[arg-type]

    async def async_send_command(self, command: str) -> bool:
        """Sends a key command to the TV asynchronously, resolving known key aliases."""
        return await async_send_command(self, command=command)  # type: ignore[arg-type]

    def cycle_source(self) -> bool:
        """Cycles to the next available input source."""
        return cycle_source(self)  # type: ignore[arg-type]

    async def async_cycle_source(self) -> bool:
        """Cycles to the next available input source asynchronously."""
        return await async_cycle_source(self)  # type: ignore[arg-type]

    def _launch_app_by_name(self, name_or_id: str) -> bool:
        """Launches an app by name or app ID from cached applist."""
        return launch_app_by_name(self, name_or_id=name_or_id)  # type: ignore[arg-type]

    async def async_launch_app_by_name(self, name_or_id: str) -> bool:
        """Launches an app by name or app ID from cached applist asynchronously."""
        return await async_launch_app_by_name(self, name_or_id=name_or_id)  # type: ignore[arg-type]

    def _change_source_by_name_or_id(self, target: str) -> bool:
        """Switches to source by name (e.g. HDMI1, TV) or numeric sourceid."""
        return change_source_by_name_or_id(self, target=target)  # type: ignore[arg-type]

    async def async_change_source_by_name_or_id(self, target: str) -> bool:
        """Switches to source by name or numeric sourceid asynchronously."""
        return await async_change_source_by_name_or_id(self, target=target)  # type: ignore[arg-type]

    def set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100)."""
        set_volume(self, volume=volume)  # type: ignore[arg-type]

    async def async_set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100) asynchronously."""
        await async_set_volume(self, volume=volume)  # type: ignore[arg-type]

    def change_source(self, source_id: str, source_name: str | None = None) -> None:
        """Switches the active input source on the TV."""
        change_source(self, source_id=source_id, source_name=source_name)  # type: ignore[arg-type]

    async def async_change_source(self, source_id: str, source_name: str | None = None) -> None:
        """Switches the active input source on the TV asynchronously."""
        await async_change_source(self, source_id=source_id, source_name=source_name)  # type: ignore[arg-type]

    def launch_app(self, app_id: str, app_name: str, url: str) -> None:
        """Launches an installed Smart TV application."""
        launch_app(self, app_id=app_id, app_name=app_name, url=url)  # type: ignore[arg-type]

    async def async_launch_app(self, app_id: str, app_name: str, url: str) -> None:
        """Launches an installed Smart TV application asynchronously."""
        await async_launch_app(self, app_id=app_id, app_name=app_name, url=url)  # type: ignore[arg-type]

    def get_picture_settings(self) -> None:
        """Requests current picture settings menu information from the TV."""
        get_picture_settings(self)  # type: ignore[arg-type]

    async def async_get_picture_settings(self) -> None:
        """Requests current picture settings menu information from the TV asynchronously."""
        await async_get_picture_settings(self)  # type: ignore[arg-type]

    def set_picture_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific picture setting value."""
        set_picture_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    async def async_set_picture_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific picture setting value asynchronously."""
        await async_set_picture_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    def set_picture_mode(self, mode: str) -> None:
        """Sets the TV picture mode preset."""
        set_picture_mode(self, mode=mode)  # type: ignore[arg-type]

    async def async_set_picture_mode(self, mode: str) -> None:
        """Sets the TV picture mode preset asynchronously."""
        await async_set_picture_mode(self, mode=mode)  # type: ignore[arg-type]

    def set_backlight(self, level: int) -> None:
        """Sets the TV backlight level (0–100)."""
        set_backlight(self, level=level)  # type: ignore[arg-type]

    async def async_set_backlight(self, level: int) -> None:
        """Sets the TV backlight level (0–100) asynchronously."""
        await async_set_backlight(self, level=level)  # type: ignore[arg-type]

    def set_brightness(self, level: int) -> None:
        """Sets the TV brightness level (0–100)."""
        set_brightness(self, level=level)  # type: ignore[arg-type]

    async def async_set_brightness(self, level: int) -> None:
        """Sets the TV brightness level (0–100) asynchronously."""
        await async_set_brightness(self, level=level)  # type: ignore[arg-type]

    def set_contrast(self, level: int) -> None:
        """Sets the TV contrast level (0–100)."""
        set_contrast(self, level=level)  # type: ignore[arg-type]

    async def async_set_contrast(self, level: int) -> None:
        """Sets the TV contrast level (0–100) asynchronously."""
        await async_set_contrast(self, level=level)  # type: ignore[arg-type]

    def get_sound_settings(self) -> None:
        """Requests current sound settings menu information from the TV."""
        get_sound_settings(self)  # type: ignore[arg-type]

    async def async_get_sound_settings(self) -> None:
        """Requests current sound settings menu information from the TV asynchronously."""
        await async_get_sound_settings(self)  # type: ignore[arg-type]

    def set_sound_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific sound setting value."""
        set_sound_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    async def async_set_sound_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific sound setting value asynchronously."""
        await async_set_sound_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    def set_sound_mode(self, mode: str) -> None:
        """Sets the TV sound mode preset."""
        set_sound_mode(self, mode=mode)  # type: ignore[arg-type]

    async def async_set_sound_mode(self, mode: str) -> None:
        """Sets the TV sound mode preset asynchronously."""
        await async_set_sound_mode(self, mode=mode)  # type: ignore[arg-type]

    def send_text_input(self, text: str, action: str = "insert") -> None:
        """Sends virtual keyboard string input to active on-screen input/search field."""
        send_text_input(self, text=text, action=action)  # type: ignore[arg-type]

    async def async_send_text_input(self, text: str, action: str = "insert") -> None:
        """Sends virtual keyboard string input asynchronously."""
        await async_send_text_input(self, text=text, action=action)  # type: ignore[arg-type]

