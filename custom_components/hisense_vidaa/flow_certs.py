"""Certificate handling mixin for Hisense VIDAA config flow."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_CERTFILE, CONF_KEYFILE, CONF_USE_SSL, DEFAULT_USE_SSL
from .crypto import check_certs_exist, get_profile_default_cert_paths
from .flow_helpers import resolve_ssl_certs

if TYPE_CHECKING:
    from .config_flow import HisenseVidaaConfigFlow

_LOGGER = logging.getLogger(__name__)


class CertsFlowMixin:
    """Mixin for SSL certificate selection and validation in config flows."""

    def _resolve_ssl_certs(self: HisenseVidaaConfigFlow) -> bool:
        """Attempts to resolve certificates from disk or profile."""
        success, cert, key, use_ssl = resolve_ssl_certs(self.auth_profile)
        if success:
            self.certfile = cert
            self.keyfile = key
            self.use_ssl = use_ssl
            return True
        return False

    async def async_step_certs(
        self: HisenseVidaaConfigFlow, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle certificate file configuration step."""
        errors: dict[str, str] = {}
        config_dir = self.hass.config.config_dir if hasattr(self.hass, "config") else "/config"
        (
            default_cert_path,
            default_key_path,
            default_cert_dir,
            default_cert_name,
            default_key_name,
        ) = get_profile_default_cert_paths(self.auth_profile, config_dir=config_dir)

        if user_input is not None:
            self.use_ssl = user_input.get(CONF_USE_SSL, DEFAULT_USE_SSL)
            self.certfile = user_input.get(CONF_CERTFILE) or default_cert_path
            self.keyfile = user_input.get(CONF_KEYFILE) or default_key_path

            if self.use_ssl and not check_certs_exist(self.certfile, self.keyfile):
                if not check_certs_exist(self.certfile, self.certfile):
                    errors[CONF_CERTFILE] = "certs_not_found"
                elif not check_certs_exist(self.keyfile, self.keyfile):
                    errors[CONF_KEYFILE] = "certs_not_found"
                else:
                    errors["base"] = "certs_not_found"

            if not errors:
                try:
                    return await self._async_init_client_and_auth()
                except AbortFlow:
                    # HA flow control (e.g. already_configured) must never be
                    # turned into cannot_connect.
                    raise
                except Exception as e:
                    _LOGGER.warning("[%s] Failed to connect or initiate auth: %s", self.ip_address, e)
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="certs",
            data_schema=vol.Schema({
                vol.Optional(CONF_USE_SSL, default=self.use_ssl): bool,
                vol.Optional(CONF_CERTFILE, default=self.certfile or default_cert_path): str,
                vol.Optional(CONF_KEYFILE, default=self.keyfile or default_key_path): str,
            }),
            description_placeholders={
                "cert_dir": str(default_cert_dir),
                "cert_file": default_cert_name,
                "key_file": default_key_name,
            },
            errors=errors,
        )
