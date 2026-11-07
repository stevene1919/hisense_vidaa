"""Control actions mixin for Hisense VIDAA media player platform."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..const import (
    CONF_ENABLE_WOL,
    CONF_SECONDARY_MAC_ADDRESS,
    DEFAULT_ENABLE_WOL,
)
from ..tv.media import async_execute_play_media, async_execute_select_source

if TYPE_CHECKING:
    from . import HisenseVidaaMediaPlayer

_LOGGER = logging.getLogger(__name__)


class MediaPlayerControlsMixin:
    """Control and command mixin for HisenseVidaaMediaPlayer."""

    async def async_turn_on(self: HisenseVidaaMediaPlayer) -> None:
        """Turn on or wake the TV."""
        mac_targets = []
        if self._options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL):
            if self._mac:
                mac_targets.append(self._mac)
            sec_mac = self._options.get(CONF_SECONDARY_MAC_ADDRESS)
            if sec_mac and sec_mac not in mac_targets:
                mac_targets.append(sec_mac)

        await self._client.async_turn_on(mac_targets if mac_targets else None)
        self.async_write_ha_state()

    async def async_turn_off(self: HisenseVidaaMediaPlayer) -> None:
        """Turn off the TV."""
        await self._client.async_turn_off()
        self.async_write_ha_state()

    async def async_set_volume_level(self: HisenseVidaaMediaPlayer, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        await self._client.async_set_volume(int(volume * 100))

    async def async_volume_up(self: HisenseVidaaMediaPlayer) -> None:
        """Step volume up."""
        await self._client.async_send_key("KEY_VOLUMEUP")

    async def async_volume_down(self: HisenseVidaaMediaPlayer) -> None:
        """Step volume down."""
        await self._client.async_send_key("KEY_VOLUMEDOWN")

    async def async_mute_volume(self: HisenseVidaaMediaPlayer, mute: bool) -> None:
        """Mute or unmute volume idempotently."""
        # KEY_MUTE is a toggle: only send it when the requested state differs from
        # the state tracked from TV broadcasts, so idempotent automations don't flip
        # the TV on every run.
        if bool(mute) == bool(self._muted):
            return
        await self._client.async_send_key("KEY_MUTE")

    async def async_media_play(self: HisenseVidaaMediaPlayer) -> None:
        """Send play command."""
        await self._client.async_send_key("KEY_PLAY")

    async def async_media_pause(self: HisenseVidaaMediaPlayer) -> None:
        """Send pause command."""
        await self._client.async_send_key("KEY_PAUSE")

    async def async_media_stop(self: HisenseVidaaMediaPlayer) -> None:
        """Send stop command."""
        await self._client.async_send_key("KEY_STOP")

    async def async_media_next_track(self: HisenseVidaaMediaPlayer) -> None:
        """Send next track command."""
        await self._client.async_send_key("KEY_FORWARDS")

    async def async_media_previous_track(self: HisenseVidaaMediaPlayer) -> None:
        """Send previous track command."""
        await self._client.async_send_key("KEY_BACK")

    async def async_play_media(
        self: HisenseVidaaMediaPlayer, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Launch an app, tune to channel, open URL/deep-link, or execute key command."""
        await async_execute_play_media(
            self._client, self._app_dict, media_type, media_id
        )

    async def async_select_source(self: HisenseVidaaMediaPlayer, source: str) -> None:
        """Select input source or smart application."""
        await async_execute_select_source(
            self._client, self._source_dict, self._app_dict, source
        )

    async def async_select_sound_mode(self: HisenseVidaaMediaPlayer, sound_mode: str) -> None:
        """Select sound mode."""
        await self._client.async_set_sound_mode(sound_mode)
        self.async_write_ha_state()
