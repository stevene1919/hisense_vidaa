"""Media player platform for Hisense VIDAA TV integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..client import VidaaClient
from ..const import (
    AUTH_PROFILES,
    BRAND_MAP,
    BRAND_PROFILES,
    CONF_AUTH_PROFILE,
    CONF_BRAND,
    CONF_ENABLE_CEC_NAMES,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_SOURCES,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_BRAND,
    DEFAULT_BRAND_OPTION,
    DEFAULT_ENABLE_CEC_NAMES,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
)
from ..entity import VidaaEntity
from ..tv.media import (
    build_media_channel_label,
    build_media_player_current_source,
    build_media_player_source_list,
    is_live_tv_source,
)
from ..tv.settings import (
    DEFAULT_MENU_ID_SOUND_MODE,
    find_menu_item_by_name,
)
from .controls import MediaPlayerControlsMixin
from .state_handler import MediaPlayerStateHandlerMixin

if TYPE_CHECKING:
    from .. import VidaaConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

__all__ = ["HisenseVidaaMediaPlayer", "VidaaMediaPlayer", "async_setup_entry"]


class VidaaMediaPlayer(
    MediaPlayerControlsMixin,
    MediaPlayerStateHandlerMixin,
    VidaaEntity,
    MediaPlayerEntity,
):
    """Media player entity representing a VIDAA Smart TV."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(
        self,
        client: VidaaClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the media player entity."""
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
        self._debounce_handle: asyncio.TimerHandle | None = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks and query initial state when entity is added."""
        self._client.register_connected_callback(self._handle_connected)
        self._client.register_state_callback(self._handle_state_update)
        self._client.register_volume_callback(self._handle_volume_update)
        self._client.register_sourcelist_callback(self._handle_sourcelist_update)
        self._client.register_applist_callback(self._handle_applist_update)
        self._client.register_sound_callback(self._handle_sound_update)
        self._client.register_disconnected_callback(self._handle_disconnected)

        # Sync state now that callbacks are registered and active.
        # Do not assume "on": the broker is also reachable in standby (fake_sleep).
        if getattr(self._client, "connected", False):
            self._state = STATE_ON if self._client.is_on else STATE_OFF
            if not self._source_dict or not self._app_dict:
                await self._client.async_query_initial_state()

        if (entry := getattr(self, "registry_entry", None)) and getattr(entry, "device_id", None):
            runtime_data = getattr(self._entry, "runtime_data", None)
            if runtime_data and getattr(runtime_data, "turn_on", None):
                from ..triggers.turn_on import async_get_turn_on_trigger

                self.async_on_remove(
                    runtime_data.turn_on.async_register(
                        self.hass, async_get_turn_on_trigger(entry.device_id)
                    )
                )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when entity is removed."""
        if self._debounce_handle:
            self._debounce_handle.cancel()
            self._debounce_handle = None
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
        """Return the current playback state."""
        if not self._client.connected or not self._client.is_on:
            return STATE_OFF
        return STATE_ON

    @property
    def assumed_state(self) -> bool:
        """Return True when TV is on so frontend displays playback and channel controls."""
        enable_controls = self._options.get(
            CONF_ENABLE_MEDIA_CONTROLS, DEFAULT_ENABLE_MEDIA_CONTROLS
        )
        return bool(enable_controls and self._client and self._client.is_on)

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return bool(self._entry_id and (self._client.access_token or self._mac))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device-specific, Live TV, and configuration metadata attributes."""
        auth_key = self._options.get(
            CONF_AUTH_PROFILE,
            self._entry.data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE),
        )
        brand_key = self._options.get(
            CONF_BRAND,
            self._entry.data.get("brand_profile", self._entry.data.get(CONF_BRAND, DEFAULT_BRAND_OPTION)),
        )
        active_code = getattr(self._client, "brand", None) or self._entry.data.get(CONF_BRAND, DEFAULT_BRAND)
        if active_code == "auto":
            active_code = self._entry.data.get("resolved_brand", DEFAULT_BRAND)

        attributes: dict[str, Any] = {
            "mqtt_connected": self._client.connected,
            "auth_profile": AUTH_PROFILES.get(auth_key, str(auth_key).title() if auth_key else "Auto"),
            "brand_profile": BRAND_PROFILES.get(brand_key, str(brand_key).title() if brand_key else "Auto"),
            "active_brand": BRAND_MAP.get(active_code, str(active_code).upper() if active_code else "Hisense"),
        }
        if self._client:
            if getattr(self._client, "device_name", None):
                attributes["reported_name"] = self._client.device_name
            if getattr(self._client, "model_name", None):
                attributes["model"] = self._client.model_name
            if getattr(self._client, "firmware_version", None):
                attributes["software_version"] = self._client.firmware_version
        if self._mac:
            attributes["mac_address"] = self._mac
        if self._connected_device:
            attributes["connected_device"] = self._connected_device
        if self._channel_infos:
            attributes["channel_infos"] = self._channel_infos
        return attributes

    @property
    def icon(self) -> str | None:
        """Return dynamic MDI icon based on active source or application."""
        if self._state == STATE_OFF:
            return "mdi:television-off"
        src = (self.source or self._source or "").lower()
        if "netflix" in src:
            return "mdi:netflix"
        if "youtube" in src or "yt" in src:
            return "mdi:youtube"
        if "prime" in src or "amazon" in src:
            return "mdi:amazon"
        if "disney" in src:
            return "mdi:television-classic"
        if "plex" in src:
            return "mdi:plex"
        if "spotify" in src:
            return "mdi:spotify"
        if "apple" in src:
            return "mdi:apple"
        if "browser" in src or "web" in src:
            return "mdi:web"
        if "hdmi" in src:
            return "mdi:hdmi-port"
        if "tv" in src or "tuner" in src or "live" in src:
            return "mdi:television-guide"
        if "av" in src or "component" in src:
            return "mdi:video-input-component"
        return "mdi:television"

    @property
    def media_channel(self) -> str | None:
        """Channel currently tuned to for TV tuner sources."""
        return build_media_channel_label(self._channel_name, self._channel_num)

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0 if self._volume is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source(self) -> str | None:
        """Return the current input source or active app."""
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

    def is_live_tv(self) -> bool:
        """Return True if the TV is actively tuned to Live TV / Broadcast Tuner."""
        return is_live_tv_source(
            source_name=self._source,
            statetype=getattr(self._client, "statetype", None),
            source_id=getattr(self._client, "current_source_id", None),
        )

    @property
    def media_content_type(self) -> MediaType | None:
        """Return the content type of currently playing media."""
        if self._state == STATE_OFF:
            return None
        if self.is_live_tv():
            return MediaType.CHANNEL
        if self._source and self._source in self._app_dict:
            return MediaType.APP
        return None

    @property
    def source_list(self) -> list[str]:
        """Return list of available input sources and apps."""
        enable_cec = self._options.get(CONF_ENABLE_CEC_NAMES, DEFAULT_ENABLE_CEC_NAMES)
        include_apps = self._options.get(
            CONF_INCLUDE_APPS_IN_SOURCES, DEFAULT_INCLUDE_APPS_IN_SOURCES
        )
        configured_sources = self._options.get(CONF_SOURCES)
        return build_media_player_source_list(
            source_dict=self._source_dict,
            app_dict=self._app_dict,
            current_source=self._source,
            connected_device=self._connected_device,
            enable_cec=enable_cec,
            include_apps=include_apps,
            configured_sources=configured_sources,
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
        """Return the current sound mode if supported."""
        return getattr(self._client, "sound_mode", None)

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return the list of available sound modes if supported by the TV."""
        sm_item = find_menu_item_by_name(
            getattr(self._client, "sound_settings", None),
            "Sound Mode",
            DEFAULT_MENU_ID_SOUND_MODE,
        )
        if sm_item and sm_item.options:
            return sm_item.options
        return None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        base = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )
        if self.sound_mode_list:
            base |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VidaaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VIDAA media player from a config entry."""
    client: VidaaClient = config_entry.runtime_data.client
    async_add_entities([VidaaMediaPlayer(client=client, entry=config_entry)])


# Backwards-compatible alias during migration
HisenseVidaaMediaPlayer = VidaaMediaPlayer
