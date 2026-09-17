import logging
import threading
import time
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import HisenseTvClient
from .const import (
    CONF_ENABLE_CEC_NAMES,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_SECONDARY_MAC_ADDRESS,
    DEFAULT_ENABLE_CEC_NAMES,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DOMAIN,
)
from .entity import HisenseVidaaEntity
from .tv.media import (
    build_media_channel_label,
    build_media_player_current_source,
    build_media_player_source_list,
    execute_play_media,
    execute_select_source,
)
from .tv.settings import (
    DEFAULT_MENU_ID_SOUND_MODE,
    STANDARD_SOUND_MODES,
    find_menu_item_by_name,
)

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaMediaPlayer(HisenseVidaaEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(
        self,
        client: HisenseTvClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(client=client, entry=entry)
        self._attr_unique_id = f"{self._entry_id}_media_player"
        self._volume = 0
        self._muted = False
        self._source = None
        self._source_list = []
        self._source_dict = {}
        self._app_list = []
        self._app_dict = {}
        self._channel_infos = {}
        self._connected_device = None
        self._channel_name = None
        self._channel_num = None
        self._volume_type = 0
        self._state = STATE_ON if getattr(client, "connected", False) else STATE_OFF

    async def async_added_to_hass(self) -> None:
        """Register callbacks and query initial state when entity is added."""
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_volume_callback(self._handle_volume_update)
        self._client.register_sourcelist_callback(self._handle_sourcelist_update)
        self._client.register_applist_callback(self._handle_applist_update)
        self._client.register_sound_callback(self._handle_sound_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

        # Sync state and query initial state now that callbacks are registered and active
        if getattr(self._client, "connected", False):
            self._state = STATE_ON
            await self.hass.async_add_executor_job(self._client.query_initial_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        self._client.unregister_connected_callback(self._handle_connected)
        self._client.unregister_state_callback(self._handle_state_update)
        self._client.unregister_volume_callback(self._handle_volume_update)
        self._client.unregister_sourcelist_callback(self._handle_sourcelist_update)
        self._client.unregister_applist_callback(self._handle_applist_update)
        self._client.unregister_sound_callback(self._handle_sound_update)
        self._client.unregister_disconnected_callback(self._handle_disconnected)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def state(self) -> str:
        if not self._client.connected or not self._client.is_on:
            return STATE_OFF
        return STATE_ON

    @property
    def available(self) -> bool:
        return bool(self._entry_id and (self._client.access_token or self._mac))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device-specific and Live TV metadata attributes."""
        attrs: dict[str, Any] = {
            "mqtt_connected": self._client.connected,
            "auth_profile": self._client.auth_profile,
        }
        if self._mac:
            attrs["mac_address"] = self._mac
        if self._connected_device:
            attrs["connected_device"] = self._connected_device
        ch_name = self._channel_name or (self._client.current_channel if self._client else None)
        if ch_name:
            attrs["channel_name"] = ch_name
        ch_num = self._channel_num or (self._client.channel_number if self._client else None)
        if ch_num:
            attrs["channel_num"] = ch_num
            attrs["channel_number"] = ch_num
        if self._client and self._client.current_program:
                attrs["program_title"] = self._client.current_program
        if self._volume_type is not None:
            attrs["audio_output"] = "ARC / eARC" if self._volume_type == 1 else "TV Speakers"
        return attrs

    @property
    def media_channel(self) -> str | None:
        """Channel currently tuned to for TV tuner sources."""
        return build_media_channel_label(self._channel_name, self._channel_num)

    @property
    def volume_level(self) -> float:
        return self._volume / 100.0

    @property
    def is_volume_muted(self) -> bool:
        return self._muted

    @property
    def source(self) -> str | None:
        enable_cec = self._options.get(CONF_ENABLE_CEC_NAMES, DEFAULT_ENABLE_CEC_NAMES)
        return build_media_player_current_source(
            source=self._source,
            connected_device=self._connected_device,
            enable_cec=enable_cec,
        )

    @property
    def media_image_url(self) -> str | None:
        """Return dynamic artwork URL for currently playing app."""
        if self._source and self._source in self._app_dict:
            app_info = self._app_dict[self._source]
            icon = app_info.get("httpIcon")
            if icon and "http" in icon:
                return "http" + icon.split("http", 1)[1]
        return None

    @property
    def source_list(self) -> list[str]:
        enable_cec = self._options.get(CONF_ENABLE_CEC_NAMES, DEFAULT_ENABLE_CEC_NAMES)
        include_apps = self._options.get(
            CONF_INCLUDE_APPS_IN_SOURCES, DEFAULT_INCLUDE_APPS_IN_SOURCES
        )
        return build_media_player_source_list(
            source_dict=self._source_dict,
            app_dict=self._app_dict,
            current_source=self._source,
            connected_device=self._connected_device,
            enable_cec=enable_cec,
            include_apps=include_apps,
        )

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media or Live TV program."""
        if self._state == STATE_OFF:
            return None
        if self._client and self._client.current_program:
            return self._client.current_program
        return self._source

    @property
    def media_series_title(self) -> str | None:
        """Return the channel or series title if watching Live TV."""
        if self._state == STATE_OFF:
            return None
        if self._channel_name or (self._client and self._client.current_channel):
            ch_name = self._channel_name or self._client.current_channel
            ch_num = self._channel_num or (self._client.channel_number if self._client else None)
            if ch_num:
                return f"{ch_name} ({ch_num})"
            return ch_name
        return None

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return getattr(self._client, "sound_mode", None)

    @property
    def sound_mode_list(self) -> list[str]:
        """Return the list of available sound modes."""
        sm_item = find_menu_item_by_name(
            getattr(self._client, "sound_settings", None),
            "Sound Mode",
            DEFAULT_MENU_ID_SOUND_MODE,
        )
        if sm_item and sm_item.options:
            return sm_item.options
        return STANDARD_SOUND_MODES

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        base = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.SELECT_SOUND_MODE
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )
        enable_controls = self._options.get(
            CONF_ENABLE_MEDIA_CONTROLS, DEFAULT_ENABLE_MEDIA_CONTROLS
        )
        if enable_controls:
            base |= (
                MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )
        return base

    def turn_on(self) -> None:
        # Send Wake-on-LAN magic packet if enabled in options
        enable_wol = self._options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL)
        if enable_wol:
            mac_targets = []
            if self._mac:
                mac_targets.append(self._mac)
            sec_mac = self._options.get(CONF_SECONDARY_MAC_ADDRESS)
            if sec_mac and sec_mac not in mac_targets:
                mac_targets.append(sec_mac)
            if mac_targets:
                self._client.send_wake_on_lan(mac_targets, ip=getattr(self._client, "ip", None))

        # Send KEY_POWER via MQTT to wake/turn on the TV if in standby/fake sleep.
        if self._client.connected:
            if not self._client.is_on:
                _LOGGER.debug("TV MQTT connected in standby/fake_sleep. Sending KEY_POWER to wake screen")
                self._client.send_key("KEY_POWER")
            else:
                _LOGGER.debug("TV already connected and running. Skipping KEY_POWER to prevent powering down")
        else:
            _LOGGER.debug("TV MQTT not connected. Attempting background token refresh and reconnect to send KEY_POWER")
            def reconnect_and_send():
                try:
                    if self._client.ensure_connected():
                        for _ in range(50):
                            if self._client.connected:
                                _LOGGER.debug("TV MQTT connected after reconnect. Sending KEY_POWER")
                                self._client.send_key("KEY_POWER")
                                break
                            time.sleep(0.1)
                except Exception as e:
                    _LOGGER.error("Failed to reconnect and send KEY_POWER: %s", e)

            threading.Thread(target=reconnect_and_send, daemon=True).start()

        self._client.is_on = True
        self.schedule_update_ha_state()

    def turn_off(self) -> None:
        if self._client.connected and self._client.is_on:
            self._client.send_key("KEY_POWER")
        self._client.is_on = False
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
        """Launch an app, tune to channel, open URL/deep-link, or execute key command."""
        execute_play_media(self._client, self._app_dict, media_type, media_id)

    def select_source(self, source: str) -> None:
        """Select input source or smart application."""
        execute_select_source(self._client, self._source_dict, self._app_dict, source)

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        self._client.set_sound_mode(sound_mode)
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_sound_update(self, data: dict[str, Any]) -> None:
        """Handle sound setting updates from TV."""
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_state_update(self, data: dict[str, Any]) -> None:
        statetype = data.get("statetype")
        _LOGGER.debug("TV State updated: %s", statetype)

        if statetype == "fake_sleep_0":
            if self._client:
                self._client.is_on = False
            self._state = STATE_OFF
            self._connected_device = None
            self._channel_name = None
            self._channel_num = None
        elif statetype == "fake_sleep_1":
            if self._client:
                self._client.is_on = True
            was_off = (self._state == STATE_OFF)
            self._state = STATE_ON
            if (was_off or not self._source_dict or not self._app_dict) and hasattr(self.hass, "add_job"):
                self.hass.add_job(self._client.query_initial_state)
        else:
            if self._client:
                self._client.is_on = True
            was_off = (self._state == STATE_OFF)
            self._state = STATE_ON
            if statetype == "sourceswitch":
                self._source = data.get("sourcename") or data.get("displayname")
                self._connected_device = data.get("displayname2") or data.get("source_detail")
                self._channel_name = None
                self._channel_num = None
            elif statetype == "app":
                self._source = data.get("name")
                self._connected_device = None
                self._channel_name = None
                self._channel_num = None
            elif statetype == "livetv":
                self._source = "TV"
                self._connected_device = None
                self._channel_name = data.get("channel_name")
                self._channel_num = data.get("channel_num")

            if (was_off or not self._source_dict or not self._app_dict) and hasattr(self.hass, "add_job"):
                self.hass.add_job(self._client.query_initial_state)

        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_volume_update(self, data: dict[str, Any]) -> None:
        if self._client:
            self._client.is_on = True
        self._state = STATE_ON
        vol_type = data.get("volume_type")
        if vol_type in (0, 1):
            self._volume_type = int(vol_type)
            self._volume = data.get("volume_value", self._volume)
        elif vol_type == 2:
            self._muted = (data.get("volume_value") == 1)

        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_sourcelist_update(self, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        if self._client:
            self._client.is_on = True
        self._source_dict = {item.get("sourcename"): item for item in data if item.get("sourcename")}
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_applist_update(self, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        if self._client:
            self._client.is_on = True
        self._app_list = data
        self._app_dict = {item.get("name"): item for item in data if item.get("name")}
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_connected(self) -> None:
        if self._client:
            self._client.is_on = True
        self._state = STATE_ON
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()

    def _handle_disconnected(self) -> None:
        if self._client:
            self._client.is_on = False
        self._state = STATE_OFF
        if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
        elif self.hass:
            self.schedule_update_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: HisenseTvClient = data["client"]
    async_add_entities([HisenseVidaaMediaPlayer(client=client, entry=config_entry)])
