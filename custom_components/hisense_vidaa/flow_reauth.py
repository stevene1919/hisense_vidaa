"""Reauthentication and reconfiguration flow mixin for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    AUTH_PROFILE_SELECTOR,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_USE_SSL,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_USE_SSL,
)
from .flow_helpers import async_resolve_mac

if TYPE_CHECKING:
    from .config_flow import HisenseVidaaConfigFlow

_LOGGER = logging.getLogger(__name__)


class ReauthFlowMixin:
    """Mixin for reauthentication and reconfiguration flow steps."""

    async def _async_finish_reauth(
        self: HisenseVidaaConfigFlow, reason: str = "reauth_successful"
    ) -> config_entries.ConfigFlowResult:
        """Update existing config entry with new credentials and reload."""
        if self._reauth_entry:
            auth_data = self._get_client_auth_data()
            if self.client:
                await self.hass.async_add_executor_job(self.client.disconnect)
                self.client = None
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={**self._reauth_entry.data, **auth_data},
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
        return self.async_abort(reason=reason)

    async def async_step_reauth(
        self: HisenseVidaaConfigFlow, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthorization initiated by Home Assistant."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self.ip_address = entry_data[CONF_IP_ADDRESS]
        self.mac_address = entry_data.get(CONF_MAC_ADDRESS)
        if not self.mac_address and self.ip_address:
            self.mac_address = await async_resolve_mac(self.hass, self.ip_address)
        self.auth_profile = entry_data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
        # [F3-leg2]: reauth must keep the transport settings of the entry it is
        # re-authenticating (a legacy/non-TLS entry would otherwise be rewritten
        # as use_ssl=True by _get_client_auth_data on success).
        self.use_ssl = entry_data.get(CONF_USE_SSL, DEFAULT_USE_SSL)
        self.certfile = entry_data.get(CONF_CERTFILE)
        self.keyfile = entry_data.get(CONF_KEYFILE)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self: HisenseVidaaConfigFlow, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Dialog to confirm reauth and trigger PIN."""
        errors: dict[str, str] = {}
        if user_input is not None:
            from .client import HisenseTvClient

            self.client = HisenseTvClient(
                self.ip_address,
                self.mac_address,
                auth_profile=self.auth_profile,
                certfile=self.certfile if self.use_ssl else None,
                keyfile=self.keyfile if self.use_ssl else None,
                use_ssl=self.use_ssl,
            )
            try:
                await self.client.async_start_auth()

                if self.auth_profile == "legacy" and self._reauth_entry:
                    return await self._async_finish_reauth(reason="reauth_successful")

                return await self.async_step_auth()
            except Exception as e:
                _LOGGER.warning("[%s] Failed to connect to TV for reauth: %s", self.ip_address, e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"ip_address": self.ip_address or ""},
            errors=errors,
        )

    async def async_step_reconfigure(
        self: HisenseVidaaConfigFlow, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfigure initiated from 3-dots menu in HA UI."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        errors: dict[str, str] = {}
        current_data = self._reauth_entry.data if self._reauth_entry else {}
        default_ip = current_data.get(CONF_IP_ADDRESS, "")
        default_profile = current_data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)

        if user_input is not None:
            self.ip_address = user_input[CONF_IP_ADDRESS]
            self.auth_profile = user_input.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
            self.mac_address = current_data.get(CONF_MAC_ADDRESS)
            if not self.mac_address and self.ip_address:
                self.mac_address = await async_resolve_mac(self.hass, self.ip_address)

            if self.auth_profile in ("auto", "legacy"):
                if not self._resolve_ssl_certs():
                    return await self.async_step_certs()
            else:
                return await self.async_step_certs()

            try:
                return await self._async_init_client_and_auth(
                    is_reauth=True, reauth_reason="reconfigure_successful"
                )
            except Exception as e:
                _LOGGER.warning("[%s] Failed to initiate reconfigure pairing: %s", self.ip_address, e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS, default=default_ip): str,
                vol.Optional(
                    CONF_AUTH_PROFILE, default=default_profile
                ): AUTH_PROFILE_SELECTOR,
            }),
            errors=errors,
        )
