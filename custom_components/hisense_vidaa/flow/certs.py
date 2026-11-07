"""Certificate handling mixin for Hisense VIDAA config flow."""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import AbortFlow

from ..const import (
    BRAND_MAP,
    CONF_CERTFILE,
    CONF_KEYFILE,
    CONF_USE_SSL,
    DEFAULT_BRAND,
    DEFAULT_USE_SSL,
)
from ..protocol import (
    check_certs_exist,
    detect_brand_from_cert_paths,
    extract_pkcs12_to_pem,
    get_profile_default_cert_paths,
    validate_ssl_certs,
)
from .helpers import resolve_ssl_certs

if TYPE_CHECKING:
    from ..config_flow import HisenseVidaaConfigFlow

_LOGGER = logging.getLogger(__name__)


class CertsFlowMixin:
    """Mixin for SSL certificate selection and validation in config flows."""

    async def _async_resolve_ssl_certs(self: HisenseVidaaConfigFlow) -> bool:
        """Attempts to resolve certificates from disk or profile off the event loop."""
        if hasattr(self, "hass") and self.hass:
            success, cert, key, use_ssl = await self.hass.async_add_executor_job(
                resolve_ssl_certs, self.auth_profile
            )
        else:
            loop = asyncio.get_running_loop()
            success, cert, key, use_ssl = await loop.run_in_executor(
                None, resolve_ssl_certs, self.auth_profile
            )
        if success:
            self.certfile = cert
            self.keyfile = key
            self.use_ssl = use_ssl
            brand_hint = detect_brand_from_cert_paths(cert, key)
            if brand_hint and getattr(self, "brand", DEFAULT_BRAND) == DEFAULT_BRAND:
                self.brand = brand_hint
                if brand_hint in BRAND_MAP:
                    self.manufacturer = BRAND_MAP[brand_hint]
            return True
        return False

    def _resolve_ssl_certs(self: HisenseVidaaConfigFlow) -> bool:
        """Synchronous fallback to resolve certificates from disk or profile."""
        success, cert, key, use_ssl = resolve_ssl_certs(self.auth_profile)
        if success:
            self.certfile = cert
            self.keyfile = key
            self.use_ssl = use_ssl
            brand_hint = detect_brand_from_cert_paths(cert, key)
            if brand_hint and getattr(self, "brand", DEFAULT_BRAND) == DEFAULT_BRAND:
                self.brand = brand_hint
                if brand_hint in BRAND_MAP:
                    self.manufacturer = BRAND_MAP[brand_hint]
            return True
        return False

    async def async_step_certs(
        self: HisenseVidaaConfigFlow, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle certificate file configuration step."""
        errors: dict[str, str] = {}
        config_dir = self.hass.config.config_dir if hasattr(self.hass, "config") else "/config"
        if hasattr(self, "hass") and self.hass:
            (
                default_cert_path,
                default_key_path,
                default_cert_dir,
                default_cert_name,
                default_key_name,
            ) = await self.hass.async_add_executor_job(
                get_profile_default_cert_paths, self.auth_profile, config_dir
            )
        else:
            loop = asyncio.get_running_loop()
            (
                default_cert_path,
                default_key_path,
                default_cert_dir,
                default_cert_name,
                default_key_name,
            ) = await loop.run_in_executor(
                None, get_profile_default_cert_paths, self.auth_profile, config_dir
            )

        if user_input is not None:
            self.use_ssl = user_input.get(CONF_USE_SSL, DEFAULT_USE_SSL)
            self.certfile = user_input.get(CONF_CERTFILE) or default_cert_path
            self.keyfile = user_input.get(CONF_KEYFILE) or default_key_path

            if self.use_ssl:
                if self.certfile and (self.certfile.lower().endswith(".p12") or self.certfile.lower().endswith(".pfx")):
                    if hasattr(self, "hass") and self.hass:
                        extracted = await self.hass.async_add_executor_job(extract_pkcs12_to_pem, self.certfile)
                    else:
                        loop = asyncio.get_running_loop()
                        extracted = await loop.run_in_executor(None, extract_pkcs12_to_pem, self.certfile)
                    if extracted:
                        self.certfile, self.keyfile = extracted

                async def _check_exist(c: str | None, k: str | None) -> bool:
                    if hasattr(self, "hass") and self.hass:
                        return await self.hass.async_add_executor_job(check_certs_exist, c, k)
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, check_certs_exist, c, k)

                certs_exist = await _check_exist(self.certfile, self.keyfile)
                if not certs_exist:
                    cert_exists = await _check_exist(self.certfile, self.certfile)
                    key_exists = await _check_exist(self.keyfile, self.keyfile)
                    if not cert_exists:
                        errors[CONF_CERTFILE] = "certs_not_found"
                    elif not key_exists:
                        errors[CONF_KEYFILE] = "certs_not_found"
                    else:
                        errors["base"] = "certs_not_found"
                else:
                    async def _validate(c: str | None, k: str | None) -> tuple[bool, str | None]:
                        if hasattr(self, "hass") and self.hass:
                            return await self.hass.async_add_executor_job(validate_ssl_certs, c, k)
                        loop = asyncio.get_running_loop()
                        return await loop.run_in_executor(None, validate_ssl_certs, c, k)

                    valid, err_reason = await _validate(self.certfile, self.keyfile)
                    if not valid:
                        _LOGGER.warning("[%s] SSL certificate validation failed: %s", self.ip_address, err_reason)
                        errors["base"] = "invalid_ssl_cert"

            if not errors:
                brand_hint = detect_brand_from_cert_paths(self.certfile, self.keyfile)
                if brand_hint and getattr(self, "brand", DEFAULT_BRAND) == DEFAULT_BRAND:
                    self.brand = brand_hint
                    if brand_hint in BRAND_MAP:
                        self.manufacturer = BRAND_MAP[brand_hint]
                try:
                    return await self._async_init_client_and_auth()
                except AbortFlow:
                    # HA flow control (e.g. already_configured) must never be
                    # turned into cannot_connect.
                    raise
                except ssl.SSLError as e:
                    _LOGGER.warning("[%s] SSL handshake failed: %s", self.ip_address, e)
                    errors["base"] = "invalid_ssl_cert"
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
