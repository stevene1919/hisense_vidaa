import logging
import threading
import time
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_MAC_ADDRESS,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaMediaPlayer(MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, client, mac, entry_id, name, options=None):
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._options = options or {}

        self._state = STATE_OFF
        self._volume = 0
        self._muted = False
        self._source = None
        self._source_list = []
        self._source_dict = {}
        self._app_list = []
        self._app_dict = {}
        self._channel_infos = {}

    async def async_added_to_hass(self) -> None:
        """Register callbacks and query initial state when entity is added."""
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_volume_callback(self._handle_volume_update)
        self._client.register_sourcelist_callback(self._handle_sourcelist_update)
        self._client.register_applist_callback(self._handle_applist_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

        # Query initial state now that callbacks are registered and active
        await self.hass.async_add_executor_job(self._client.query_initial_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._entry_id}_media_player"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        info = {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._name,
            "manufacturer": "Hisense",
            "model": "VIDAA TV",
        }

        if self._mac:
            cleaned_mac = self._mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}

        return info

    @property
    def state(self) -> str:
        if not self._client.connected:
            return STATE_OFF
        return self._state

    @property
    def available(self) -> bool:
        return bool(self._entry_id and (self._client.access_token or self._mac))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device-specific attributes."""
        attrs = {
            "mqtt_connected": self._client.connected,
            "auth_profile": self._client.auth_profile,
        }
        if self._mac:
            attrs["mac_address"] = self._mac
        return attrs

    @property
    def volume_level(self) -> float:
        return self._volume / 100.0

    @property
    def is_volume_muted(self) -> bool:
        return self._muted

    @property
    def source(self) -> str | None:
        return self._source

    @property
    def source_list(self) -> list[str]:
        # Filter physical inputs (HDMI, TV, AV)
        sources = [
            s for s in self._source_dict.keys()
            if "hdmi" in s.lower() or s.lower() in ("tv", "av")
        ]

        include_apps = self._options.get(
            CONF_INCLUDE_APPS_IN_SOURCES, DEFAULT_INCLUDE_APPS_IN_SOURCES
        )
        if include_apps and self._app_dict:
            # Include all installed apps sorted by name
            app_names = sorted(self._app_dict.keys())
            return sorted(sources) + app_names

        return sorted(sources)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        return (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )

    def turn_on(self) -> None:
        # Send Wake-on-LAN magic packet if enabled in options
        enable_wol = self._options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL)
        if enable_wol and self._mac:
            self._client.send_wake_on_lan(self._mac)

        # Send KEY_POWER via MQTT to wake/turn on the TV.
        if self._client.connected:
            _LOGGER.debug("TV MQTT connected. Sending KEY_POWER to turn on")
            self._client.send_key("KEY_POWER")
        else:
            _LOGGER.debug("TV MQTT not connected. Attempting background token refresh and reconnect to send KEY_POWER")
            def reconnect_and_send():
                try:
                    self._client.check_and_refresh_token()
                    self._client.mqtt_client.username_pw_set(
                        username=self._client.username,
                        password=self._client.access_token
                    )
                    self._client.mqtt_client.reconnect()
                    for _ in range(50):
                        if self._client.connected:
                            _LOGGER.debug("TV MQTT connected after reconnect. Sending KEY_POWER")
                            self._client.send_key("KEY_POWER")
                            break
                        time.sleep(0.1)
                except Exception as e:
                    _LOGGER.error("Failed to reconnect and send KEY_POWER: %s", e)

            threading.Thread(target=reconnect_and_send, daemon=True).start()

        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self) -> None:
        self._client.send_key("KEY_POWER")
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    def set_volume_level(self, volume: float) -> None:
        self._client.set_volume(int(volume * 100))

    def volume_up(self) -> None:
        self._client.send_key("KEY_VOLUMEUP")

    def volume_down(self) -> None:
        self._client.send_key("KEY_VOLUMEDOWN")

    def mute_volume(self, mute: bool) -> None:
        self._client.send_key("KEY_MUTE")

    def media_play(self) -> None:
        self._client.send_key("KEY_PLAY")

    def media_pause(self) -> None:
        self._client.send_key("KEY_PAUSE")

    def media_stop(self) -> None:
        self._client.send_key("KEY_STOP")

    def media_next_track(self) -> None:
        self._client.send_key("KEY_FORWARDS")

    def media_previous_track(self) -> None:
        self._client.send_key("KEY_BACK")

    def play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Launch an app, tune to channel, or execute key command."""
        type_lower = media_type.lower()
        if type_lower in ("app", "application") or media_id in self._app_dict:
            app = self._app_dict.get(media_id)
            if app:
                self._client.launch_app(app["appId"], app["name"], app["url"])
                return
            for a_name, a_info in self._app_dict.items():
                if a_name.lower() == media_id.lower():
                    self._client.launch_app(a_info["appId"], a_info["name"], a_info["url"])
                    return

        if type_lower in ("channel", "tvshow"):
            for char in str(media_id):
                if char.isdigit():
                    self._client.send_key(f"KEY_{char}")
                    time.sleep(0.1)
            return

        self._client.send_command(media_id)

    def select_source(self, source: str) -> None:
        # Determine if it's an app
        app = self._app_dict.get(source)
        if app:
            self._client.launch_app(app["appId"], app["name"], app["url"])
            return

        # Input source
        src = self._source_dict.get(source)
        if src:
            self._client.change_source(src["sourceid"])

    def _handle_state_update(self, data: dict[str, Any]) -> None:
        statetype = data.get("statetype")
        _LOGGER.debug("TV State updated: %s", statetype)

        if statetype == "fake_sleep_0":
            self._state = STATE_OFF
        else:
            was_off = (self._state == STATE_OFF)
            self._state = STATE_ON
            if statetype == "sourceswitch":
                self._source = data.get("sourcename") or data.get("displayname")
            elif statetype == "app":
                self._source = data.get("name")
            elif statetype == "livetv":
                self._source = "TV"

            if was_off or not self._source_dict or not self._app_dict:
                self.hass.add_job(self._client.query_initial_state)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_volume_update(self, data: dict[str, Any]) -> None:
        self._state = STATE_ON
        if data.get("volume_type") == 0:
            self._volume = data.get("volume_value", 0)
        elif data.get("volume_type") == 2:
            self._muted = (data.get("volume_value") == 1)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_sourcelist_update(self, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        self._source_dict = {item.get("sourcename"): item for item in data if item.get("sourcename")}
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_applist_update(self, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        self._app_list = data
        self._app_dict = {item.get("name"): item for item in data if item.get("name")}
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_disconnected(self) -> None:
        self._state = STATE_OFF
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = hass.data[DOMAIN][config_entry.entry_id]
    mac = config_entry.data.get(CONF_MAC_ADDRESS)
    options = config_entry.options

    entity = HisenseVidaaMediaPlayer(
        client=client,
        mac=mac,
        entry_id=config_entry.entry_id,
        name=config_entry.title,
        options=options,
    )
    async_add_entities([entity])
