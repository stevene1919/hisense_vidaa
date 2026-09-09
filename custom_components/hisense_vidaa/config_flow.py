import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .client import HisenseTvClient
from .const import (
    AUTH_PROFILES,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_CLIENT_ID,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_IP_ADDRESS,
    CONF_MAC_ADDRESS,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_USERNAME,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self.ip_address: str | None = None
        self.mac_address: str | None = None
        self.auth_profile: str = DEFAULT_AUTH_PROFILE
        self.client: HisenseTvClient | None = None
        self.discovered_title: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HisenseVidaaOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        if user_input is not None:
            self.ip_address = user_input[CONF_IP_ADDRESS]
            self.auth_profile = user_input.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)

            # Attempt automatic MAC address resolution from ARP cache
            try:
                from functools import partial

                from getmac import get_mac_address
                from homeassistant.helpers.device_registry import format_mac

                raw_mac = await self.hass.async_add_executor_job(
                    partial(get_mac_address, ip=self.ip_address)
                )
                if raw_mac:
                    self.mac_address = format_mac(raw_mac)
            except Exception:
                self.mac_address = None

            # Start the client connection to TV
            self.client = HisenseTvClient(
                self.ip_address, self.mac_address, auth_profile=self.auth_profile
            )
            try:
                probe = await self.hass.async_add_executor_job(self.client.probe_auth_methods, 1.5)
                if self.auth_profile == "auto" and probe.get("auth_model") == "legacy_static":
                    self.auth_profile = "legacy"
                    self.client.auth_profile = "legacy"

                await self.client.async_start_auth()

                # If MAC was not in ARP before, try again now that TCP connection was established
                if not self.mac_address:
                    try:
                        raw_mac = await self.hass.async_add_executor_job(
                            partial(get_mac_address, ip=self.ip_address)
                        )
                        if raw_mac:
                            self.mac_address = format_mac(raw_mac)
                    except Exception:
                        pass

                if self.mac_address:
                    await self.async_set_unique_id(self.mac_address)
                    self._abort_if_unique_id_configured()

                if self.auth_profile == "legacy":
                    self.discovered_title = f"Hisense TV ({self.ip_address})"
                    try:
                        fp = await self.hass.async_add_executor_job(
                            self.client.get_device_fingerprint, 1.5
                        )
                        discovered_name = fp.get("friendly_name") or fp.get("model_code")
                        if (
                            discovered_name
                            and discovered_name.strip()
                            and discovered_name.strip() != "Renderer"
                        ):
                            self.discovered_title = discovered_name.strip()
                    except Exception:
                        pass
                    return self.async_create_entry(
                        title=self.discovered_title or f"Hisense TV ({self.ip_address})",
                        data={
                            CONF_IP_ADDRESS: self.ip_address,
                            CONF_MAC_ADDRESS: self.mac_address,
                            CONF_AUTH_PROFILE: self.auth_profile,
                            CONF_CLIENT_ID: self.client.client_id,
                            CONF_USERNAME: self.client.username,
                            CONF_PASSWORD: self.client.password,
                            CONF_ACCESS_TOKEN: self.client.access_token,
                            CONF_ACCESS_TOKEN_TIME: self.client.access_token_time,
                            CONF_ACCESS_TOKEN_DURATION: self.client.access_token_duration,
                            CONF_REFRESH_TOKEN: self.client.refresh_token,
                            CONF_REFRESH_TOKEN_TIME: self.client.refresh_token_time,
                            CONF_REFRESH_TOKEN_DURATION: self.client.refresh_token_duration,
                        },
                        options={
                            CONF_ENABLE_REMOTE: DEFAULT_ENABLE_REMOTE,
                            CONF_ENABLE_WOL: DEFAULT_ENABLE_WOL,
                            CONF_INCLUDE_APPS_IN_SOURCES: DEFAULT_INCLUDE_APPS_IN_SOURCES,
                        },
                    )

                return await self.async_step_auth()
            except Exception as e:
                _LOGGER.exception("Failed to connect or initiate auth with TV at %s: %s", self.ip_address, e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Optional(
                    CONF_AUTH_PROFILE, default=DEFAULT_AUTH_PROFILE
                ): vol.In(AUTH_PROFILES),
            }),
            errors=errors,
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        if user_input is not None and self.client:
            pin_code = user_input["pin_code"]
            try:
                await self.client.async_submit_pin(pin_code)

                # Discover actual device friendly name from UPnP/mDNS
                self.discovered_title = f"Hisense TV ({self.ip_address})"
                try:
                    fp = await self.hass.async_add_executor_job(
                        self.client.get_device_fingerprint, 1.5
                    )
                    discovered_name = fp.get("friendly_name") or fp.get("model_code")
                    if (
                        discovered_name
                        and discovered_name.strip()
                        and discovered_name.strip() != "Renderer"
                    ):
                        self.discovered_title = discovered_name.strip()
                except Exception:
                    pass

                return await self.async_step_options()
            except Exception as e:
                _LOGGER.exception("Failed to validate PIN or retrieve tokens from TV: %s", e)
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
        if user_input is not None and self.client:
            return self.async_create_entry(
                title=self.discovered_title or f"Hisense TV ({self.ip_address})",
                data={
                    CONF_IP_ADDRESS: self.ip_address,
                    CONF_MAC_ADDRESS: self.mac_address,
                    CONF_AUTH_PROFILE: self.auth_profile,
                    CONF_CLIENT_ID: self.client.client_id,
                    CONF_USERNAME: self.client.username,
                    CONF_PASSWORD: self.client.password,
                    CONF_ACCESS_TOKEN: self.client.access_token,
                    CONF_ACCESS_TOKEN_TIME: self.client.access_token_time,
                    CONF_ACCESS_TOKEN_DURATION: self.client.access_token_duration,
                    CONF_REFRESH_TOKEN: self.client.refresh_token,
                    CONF_REFRESH_TOKEN_TIME: self.client.refresh_token_time,
                    CONF_REFRESH_TOKEN_DURATION: self.client.refresh_token_duration,
                },
                options={
                    CONF_ENABLE_REMOTE: user_input.get(
                        CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE
                    ),
                    CONF_ENABLE_WOL: user_input.get(
                        CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL
                    ),
                    CONF_INCLUDE_APPS_IN_SOURCES: user_input.get(
                        CONF_INCLUDE_APPS_IN_SOURCES, DEFAULT_INCLUDE_APPS_IN_SOURCES
                    ),
                },
            )

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_ENABLE_REMOTE, default=DEFAULT_ENABLE_REMOTE
                ): bool,
                vol.Optional(CONF_ENABLE_WOL, default=DEFAULT_ENABLE_WOL): bool,
                vol.Optional(
                    CONF_INCLUDE_APPS_IN_SOURCES,
                    default=DEFAULT_INCLUDE_APPS_IN_SOURCES,
                ): bool,
            }),
        )


class HisenseVidaaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Hisense VIDAA options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_ENABLE_REMOTE,
                    default=options.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_WOL,
                    default=options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_APPS_IN_SOURCES,
                    default=options.get(
                        CONF_INCLUDE_APPS_IN_SOURCES,
                        DEFAULT_INCLUDE_APPS_IN_SOURCES,
                    ),
                ): bool,
            }),
        )
