"""Config flow for Hisense VIDAA TV integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.core import callback

from .client import HisenseTvClient
from .const import (
    DEFAULT_AUTH_PROFILE,
    DEFAULT_BRAND,
    DEFAULT_BRAND_OPTION,
    DEFAULT_USE_SSL,
    DOMAIN,
)
from .flow import (
    CertsFlowMixin,
    DiscoveryFlowMixin,
    HisenseVidaaOptionsFlowHandler,
    ReauthFlowMixin,
    UserFlowMixin,
)
from .protocol.pairing import async_probe_pairing_challenge

if TYPE_CHECKING:
    from . import HisenseVidaaConfigEntry

__all__ = ["HisenseTvClient", "HisenseVidaaConfigFlow", "async_probe_pairing_challenge"]


class HisenseVidaaConfigFlow(
    config_entries.ConfigFlow,
    DiscoveryFlowMixin,
    ReauthFlowMixin,
    CertsFlowMixin,
    UserFlowMixin,
    domain=DOMAIN,
):
    """Handle a config flow for Hisense VIDAA TV."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self.ip_address: str | None = None
        self.mac_address: str | None = None
        self.auth_profile: str = DEFAULT_AUTH_PROFILE
        self.certfile: str | None = None
        self.keyfile: str | None = None
        self.use_ssl: bool = DEFAULT_USE_SSL
        self.client: HisenseTvClient | None = None
        self.discovered_title: str | None = None
        self.model: str | None = None
        self.manufacturer: str | None = None
        self.brand: str = DEFAULT_BRAND
        self.brand_profile: str = DEFAULT_BRAND_OPTION
        self.sw_version: str | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._pairing_error: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: HisenseVidaaConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HisenseVidaaOptionsFlowHandler()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfigure initiated from 3-dots menu in HA UI."""
        return await super().async_step_reconfigure(user_input)
