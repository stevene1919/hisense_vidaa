"""Auto-discovery flow mixin for Hisense VIDAA TV (SSDP & Zeroconf)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_IP_ADDRESS
from .discovery import parse_ssdp_discovery, parse_zeroconf_discovery
from .flow_helpers import async_resolve_mac

if TYPE_CHECKING:
    from .config_flow import HisenseVidaaConfigFlow

_LOGGER = logging.getLogger(__name__)


class DiscoveryFlowMixin:
    """Mixin for SSDP and Zeroconf device discovery steps."""

    async def _async_handle_discovery(
        self: HisenseVidaaConfigFlow, parsed: Any
    ) -> config_entries.ConfigFlowResult:
        """Handle common SSDP and Zeroconf device resolution and flow routing."""
        if not parsed or not parsed.host:
            return self.async_abort(reason="not_vidaa_tv" if parsed is None else "cannot_connect")

        self.ip_address = parsed.host
        self.discovered_title = parsed.title
        self.manufacturer = getattr(parsed, "manufacturer", None)
        self.model = getattr(parsed, "model", None)
        self.mac_address = parsed.mac_address
        if not self.mac_address and parsed.host:
            self.mac_address = await async_resolve_mac(self.hass, parsed.host)

        unique_id = self.mac_address or parsed.unique_id
        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: self.ip_address}
            )

        return await self.async_step_discovery_confirm()

    async def async_step_ssdp(
        self: HisenseVidaaConfigFlow, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle SSDP discovery."""
        parsed = await self.hass.async_add_executor_job(
            parse_ssdp_discovery, discovery_info
        )
        return await self._async_handle_discovery(parsed)

    async def async_step_zeroconf(
        self: HisenseVidaaConfigFlow, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle Zeroconf / mDNS discovery."""
        parsed = await self.hass.async_add_executor_job(
            parse_zeroconf_discovery, discovery_info
        )
        return await self._async_handle_discovery(parsed)

    async def async_step_discovery_confirm(
        self: HisenseVidaaConfigFlow, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery setup with user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._resolve_ssl_certs():
                try:
                    return await self._async_init_client_and_auth()
                except AbortFlow:
                    # HA flow control (e.g. already_configured) must never be
                    # turned into cannot_connect.
                    raise
                except Exception as e:
                    _LOGGER.warning(
                        "[%s] Failed to connect or initiate auth with TV: %s",
                        self.ip_address,
                        e,
                    )
                    errors["base"] = "cannot_connect"
            else:
                return await self.async_step_certs()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self.discovered_title or self.ip_address or "Hisense TV",
                "ip_address": self.ip_address or "",
            },
            errors=errors,
        )
