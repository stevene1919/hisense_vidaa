"""State updates and broadcast callbacks mixin for Hisense VIDAA media player platform."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_OFF, STATE_ON

from ..const import CONF_PLAYBACK_DEBOUNCE, DEFAULT_PLAYBACK_DEBOUNCE
from ..tv.media import (
    parse_applist_data,
    parse_media_state_broadcast,
    parse_sourcelist_data,
    parse_sourcelist_payload,
    parse_volume_broadcast,
)

if TYPE_CHECKING:
    from . import HisenseVidaaMediaPlayer, VidaaMediaPlayer

_LOGGER = logging.getLogger(__name__)


class MediaPlayerStateHandlerMixin:
    """Telemetry and broadcast handling mixin for VidaaMediaPlayer."""

    def _schedule_ha_update(self: VidaaMediaPlayer) -> None:
        """Schedules a Home Assistant state update if the entity is added to hass."""
        if getattr(self, "hass", None):
            self.schedule_update_ha_state()

    def _handle_sound_update(self: HisenseVidaaMediaPlayer, data: dict[str, Any]) -> None:
        """Handle sound setting updates from TV."""
        self._schedule_ha_update()

    def _apply_state_payload(self: HisenseVidaaMediaPlayer, parsed: dict[str, Any]) -> None:
        """Applies parsed state broadcast payload."""
        statetype = parsed["statetype"]
        was_off = (self._state == STATE_OFF)
        self._state = STATE_ON if parsed["is_on"] else STATE_OFF

        if parsed["is_on"] and statetype not in ("fake_sleep_0", "fake_sleep_1"):
            if statetype in ("sourceswitch", "app", "livetv"):
                self._source = parsed["source"]
                self._app_id = parsed.get("app_id") if statetype == "app" else None
                self._connected_device = parsed["connected_device"]
                self._channel_name = parsed["channel_name"]
                self._channel_num = parsed["channel_num"]
        elif not parsed["is_on"]:
            self._app_id = None
            self._connected_device = None
            self._channel_name = None
            self._channel_num = None

        if (
            parsed["is_on"]
            and (was_off or not self._source_dict or not self._app_dict)
            and self.hass
        ):
            self.hass.async_create_background_task(
                self._client.async_query_initial_state(),
                "vidaa_media_player_initial_state",
            )

        self._schedule_ha_update()

    def _handle_state_update(self: VidaaMediaPlayer, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return

        parsed = parse_media_state_broadcast(data)
        if self._client:
            self._client.is_on = parsed["is_on"]

        # Cancel any pending debounce timer
        if self._debounce_handle:
            self._debounce_handle.cancel()
            self._debounce_handle = None

        # Power off or waking from sleep transitions apply immediately
        debounce = float(self._options.get(CONF_PLAYBACK_DEBOUNCE, DEFAULT_PLAYBACK_DEBOUNCE))
        loop = getattr(self.hass, "loop", None)
        if not parsed["is_on"] or debounce <= 0 or not self.hass or not loop:
            self._apply_state_payload(parsed)
            return

        def _timed_apply() -> None:
            self._debounce_handle = None
            self._apply_state_payload(parsed)

        self._debounce_handle = loop.call_later(debounce, _timed_apply)

    def _handle_volume_update(self: HisenseVidaaMediaPlayer, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        self._volume, self._volume_type, self._muted = parse_volume_broadcast(
            data, self._volume, self._volume_type, self._muted
        )
        self._schedule_ha_update()

    def _handle_sourcelist_update(self: HisenseVidaaMediaPlayer, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        self._source_dict = parse_sourcelist_data(data)
        _, _, _, active_source = parse_sourcelist_payload(data)
        if active_source and self._client and self._client.connected:
            if not self._client.current_source:
                self._client.current_source = active_source
            if not self._source:
                self._source = active_source
            if self._client.is_on:
                self._state = STATE_ON
        self._schedule_ha_update()

    def _handle_applist_update(self: HisenseVidaaMediaPlayer, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        self._app_list, self._app_dict = parse_applist_data(data)
        self._schedule_ha_update()

    def _handle_connected(self: HisenseVidaaMediaPlayer) -> None:
        # Power state is set by the retained state broadcast that follows the connect.
        self._state = STATE_ON if (self._client and self._client.is_on) else STATE_OFF
        self._schedule_ha_update()

    def _handle_disconnected(self: HisenseVidaaMediaPlayer) -> None:
        if self._client:
            self._client.is_on = False
        self._state = STATE_OFF
        self._schedule_ha_update()
