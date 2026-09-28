"""Config flow for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .client import HisenseTvClient
from .const import (
    AUTH_PROFILE_SELECTOR,
    CONF_AUTH_PROFILE,
    CONF_IP_ADDRESS,
    CONF_MAC_ADDRESS,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_SOUND_CONTROLS,
    DEFAULT_USE_SSL,
    DOMAIN,
)
from .flow_certs import CertsFlowMixin
from .flow_discovery import DiscoveryFlowMixin
from .flow_helpers import (
    async_disconnect_existing_client,
    async_discover_device_details,
    async_probe_device_capabilities,
    async_resolve_mac,
    build_entry_options,
    build_options_schema,
    collect_client_auth_data,
)
from .flow_reauth import ReauthFlowMixin
from .options_flow import HisenseVidaaOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaConfigFlow(
    config_entries.ConfigFlow,
    DiscoveryFlowMixin,
    ReauthFlowMixin,
    CertsFlowMixin,
    domain=DOMAIN,
):
    """Handle a config flow for Hisense VIDAA TV."""

    VERSION = 1

    def __init__(self) -> None:
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
        self.sw_version: str | None = None
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HisenseVidaaOptionsFlowHandler()

    async def _async_discover_device_name(self) -> None:
        """Discovers friendly device name and model info from UPnP/DLNA."""
        details = await async_discover_device_details(self.hass, self.client, self.ip_address)
        self.discovered_title = details["title"]
        if details["model"]:
            self.model = details["model"]
        if details["manufacturer"]:
            self.manufacturer = details["manufacturer"]
        if details["sw_version"]:
            self.sw_version = details["sw_version"]

    async def _async_probe_device_capabilities(self) -> None:
        """Probe TV capabilities (picture/sound menus) to set intelligent default options."""
        await async_probe_device_capabilities(self.hass, self.client, self.ip_address)

    async def _async_disconnect_existing_client(self) -> None:
        """Disconnect any running client for this IP/MAC to avoid MQTT session collision during pairing."""
        await async_disconnect_existing_client(self.hass, self.ip_address, self.mac_address)

    def _get_client_auth_data(self) -> dict[str, Any]:
        """Collect authentication credentials and device attributes dictionary."""
        return collect_client_auth_data(
            ip_address=self.ip_address,
            auth_profile=self.auth_profile,
            use_ssl=self.use_ssl,
            mac_address=self.mac_address,
            client=self.client,
            certfile=self.certfile,
            keyfile=self.keyfile,
            model=self.model,
            manufacturer=self.manufacturer,
            sw_version=self.sw_version,
        )

    async def _async_init_client_and_auth(
        self, is_reauth: bool = False, reauth_reason: str = "reauth_successful"
    ) -> config_entries.ConfigFlowResult:
        """Helper to initialize client, perform static auth check, and route to PIN or options."""
        await self._async_disconnect_existing_client()
        self.client = HisenseTvClient(
            self.ip_address,
            self.mac_address,
            auth_profile=self.auth_profile,
            certfile=self.certfile if self.use_ssl else None,
            keyfile=self.keyfile if self.use_ssl else None,
            use_ssl=self.use_ssl,
        )
        self.client._loop = self.hass.loop

        if self.auth_profile == "auto":
            probe = await self.hass.async_add_executor_job(
                self.client.probe_auth_methods, 1.5
            )
            if (
                probe.get("legacy_static", {}).get("supported")
                and not probe.get("modern_dynamic", {}).get("supported")
                and not probe.get("middle_dynamic", {}).get("supported")
                and not probe.get("standard_dynamic", {}).get("supported")
            ):
                self.auth_profile = "legacy"
                self.client.auth_profile = "legacy"

        await self.client.async_start_auth()

        if not self.mac_address:
            self.mac_address = await async_resolve_mac(self.hass, self.ip_address)

        if self.mac_address:
            await self.async_set_unique_id(self.mac_address)
            self._abort_if_unique_id_configured()

        if self.auth_profile == "legacy":
            if is_reauth and self._reauth_entry:
                return await self._async_finish_reauth(reason=reauth_reason)
            await self._async_discover_device_name()
            await self._async_probe_device_capabilities()
            return await self.async_step_options()

        return await self.async_step_auth()

    # --------------------------------------------------------------------------
    # Flow Steps
    # --------------------------------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle manual user IP configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.ip_address = user_input[CONF_IP_ADDRESS]
            self.auth_profile = user_input.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
            self.mac_address = await async_resolve_mac(self.hass, self.ip_address)

            if self.auth_profile in ("auto", "legacy"):
                if self._resolve_ssl_certs():
                    try:
                        return await self._async_init_client_and_auth()
                    except Exception as e:
                        _LOGGER.warning("[%s] Failed to connect or initiate auth with TV: %s", self.ip_address, e)
                        errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_certs()
            else:
                return await self.async_step_certs()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Optional(
                    CONF_AUTH_PROFILE, default=DEFAULT_AUTH_PROFILE
                ): AUTH_PROFILE_SELECTOR,
            }),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle PIN code entry step."""
        errors: dict[str, str] = {}

        if not self.client:
            if not self.ip_address and self._reauth_entry:
                self.ip_address = self._reauth_entry.data.get(CONF_IP_ADDRESS)
                self.mac_address = self._reauth_entry.data.get(CONF_MAC_ADDRESS)
                self.auth_profile = self._reauth_entry.data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)

            if self.ip_address:
                self.client = HisenseTvClient(
                    self.ip_address, self.mac_address, auth_profile=self.auth_profile
                )
                try:
                    await self.client.async_start_auth()
                except Exception as e:
                    _LOGGER.warning("[%s] Failed to connect to TV to show PIN: %s", self.ip_address, e)
                    errors["base"] = "cannot_connect"

        if user_input is not None and self.client:
            pin_code = str(user_input["pin_code"]).strip().replace(" ", "").replace("-", "")
            try:
                await self.client.async_submit_pin(pin_code)

                if self._reauth_entry:
                    return await self._async_finish_reauth(reason="reauth_successful")

                await self._async_discover_device_name()
                await self._async_probe_device_capabilities()
                return await self.async_step_options()
            except Exception as e:
                _LOGGER.warning("[%s] Failed to validate PIN or retrieve tokens from TV: %s", self.ip_address, e)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({
                vol.Required("pin_code"): str,
            }),
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow configuring initial options during setup."""
        pic_supported = bool(getattr(self.client, "picture_settings", None)) if self.client else DEFAULT_ENABLE_PICTURE_CONTROLS
        sound_supported = bool(getattr(self.client, "sound_settings", None)) if self.client else DEFAULT_ENABLE_SOUND_CONTROLS

        if user_input is not None and self.client:
            entry_data = self._get_client_auth_data()

            await self.hass.async_add_executor_job(self.client.disconnect)
            self.client = None

            return self.async_create_entry(
                title=self.discovered_title or f"Hisense TV ({self.ip_address})",
                data=entry_data,
                options=build_entry_options(user_input, pic_supported, sound_supported),
            )

        return self.async_show_form(
            step_id="options",
            data_schema=build_options_schema(pic_supported, sound_supported),
        )

    @callback
    def async_remove(self) -> None:
        """Clean up running flow client when config flow is aborted or closed."""
        if self.client:
            client = self.client
            self.client = None
            if hasattr(self, "hass") and self.hass:
                self.hass.async_create_task(self.hass.async_add_executor_job(client.disconnect))
            else:
                client.disconnect()
