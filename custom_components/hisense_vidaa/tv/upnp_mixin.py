"""UPnP and DLNA control delegation mixin for HisenseTvClient."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import HisenseTvClient


class TvUpnpMixin:
    """Delegator mixin forwarding UPnP AV and volume calls to internal upnp client."""

    async def async_upnp_get_volume(self: HisenseTvClient) -> int | None:
        """Retrieves master volume level (0-100) via UPnP RenderingControl."""
        return await self.upnp.async_get_volume()

    async def async_upnp_set_volume(self: HisenseTvClient, volume: int) -> bool:
        """Sets master volume level (0-100) via UPnP RenderingControl."""
        return await self.upnp.async_set_volume(volume)

    async def async_upnp_get_mute(self: HisenseTvClient) -> bool | None:
        """Retrieves master mute status via UPnP RenderingControl."""
        return await self.upnp.async_get_mute()

    async def async_upnp_set_mute(self: HisenseTvClient, mute: bool) -> bool:
        """Sets master mute status (True/False) via UPnP RenderingControl."""
        return await self.upnp.async_set_mute(mute)

    async def async_upnp_get_transport_info(self: HisenseTvClient) -> dict[str, str] | None:
        """Retrieves playback transport info (PLAYING, STOPPED, etc.) via UPnP AVTransport."""
        return await self.upnp.async_get_transport_info()

    async def async_upnp_probe(self: HisenseTvClient) -> dict[str, Any] | None:
        """Probes UPnP endpoint for fast sub-second reachability and status."""
        return await self.upnp.async_probe()
