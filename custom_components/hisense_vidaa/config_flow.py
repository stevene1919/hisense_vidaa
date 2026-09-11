import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_SW_VERSION,
    CONF_USERNAME,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DOMAIN,
)
from .discovery import get_arp_mac
from .options_flow import HisenseVidaaOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)


class HisenseVidaaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self.ip_address: str | None = None
        self.mac_address: str | None = None
        self.auth_profile: str = DEFAULT_AUTH_PROFILE
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors = {}
        if user_input is not None:
            self.ip_address = user_input[CONF_IP_ADDRESS]
            self.auth_profile = user_input.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)

            # Attempt automatic MAC address resolution from ARP cache
            raw_mac = await self.hass.async_add_executor_job(get_arp_mac, self.ip_address)
            if raw_mac:
                from homeassistant.helpers.device_registry import format_mac

                self.mac_address = format_mac(raw_mac)

            # Start the client connection to TV
            self.client = HisenseTvClient(
                self.ip_address, self.mac_address, auth_profile=self.auth_profile
            )
            try:
                # If auto-detect is selected, probe if TV uses legacy static credentials
                if self.auth_profile == "auto":
                    probe = await self.hass.async_add_executor_job(
                        self.client.probe_auth_methods, 1.5
                    )
                    if (
                        probe.get("legacy_static", {}).get("supported")
                        and not probe.get("modern_dynamic", {}).get("supported")
                        and not probe.get("standard_dynamic", {}).get("supported")
                    ):
                        self.auth_profile = "legacy"
                        self.client.auth_profile = "legacy"

                await self.client.async_start_auth()

                # If MAC was not in ARP before, try again now that TCP connection was established
                if not self.mac_address:
                    raw_mac = await self.hass.async_add_executor_job(
                        get_arp_mac, self.ip_address
                    )
                    if raw_mac:
                        from homeassistant.helpers.device_registry import format_mac

                        self.mac_address = format_mac(raw_mac)

                if self.mac_address:
                    await self.async_set_unique_id(self.mac_address)
                    self._abort_if_unique_id_configured()

                if self.auth_profile == "legacy":
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

        # If resumed from an existing session without an active client, initiate pairing connection
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
                    _LOGGER.exception("Failed to connect to TV to show PIN: %s", e)
                    errors["base"] = "cannot_connect"

        if user_input is not None and self.client:
            pin_code = user_input["pin_code"]
            try:
                await self.client.async_submit_pin(pin_code)

                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={
                            **self._reauth_entry.data,
                            CONF_IP_ADDRESS: self.ip_address,
                            CONF_MAC_ADDRESS: self.mac_address or self._reauth_entry.data.get(CONF_MAC_ADDRESS),
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
                    )
                    await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

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

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthorization initiated by Home Assistant."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self.ip_address = entry_data[CONF_IP_ADDRESS]
        self.mac_address = entry_data.get(CONF_MAC_ADDRESS)
        self.auth_profile = entry_data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Dialog to confirm reauth and trigger PIN."""
        errors = {}
        if user_input is not None:
            self.client = HisenseTvClient(
                self.ip_address, self.mac_address, auth_profile=self.auth_profile
            )
            try:
                await self.client.async_start_auth()

                if self.auth_profile == "legacy" and self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={
                            **self._reauth_entry.data,
                            CONF_IP_ADDRESS: self.ip_address,
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
                    )
                    await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                return await self.async_step_auth()
            except Exception as e:
                _LOGGER.exception("Failed to connect to TV for reauth: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"ip_address": self.ip_address or ""},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfigure initiated from 3-dots menu in HA UI."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        errors = {}
        current_data = self._reauth_entry.data if self._reauth_entry else {}
        default_ip = current_data.get(CONF_IP_ADDRESS, "")
        default_profile = current_data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)

        if user_input is not None:
            self.ip_address = user_input[CONF_IP_ADDRESS]
            self.auth_profile = user_input.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
            self.mac_address = current_data.get(CONF_MAC_ADDRESS)

            self.client = HisenseTvClient(
                self.ip_address, self.mac_address, auth_profile=self.auth_profile
            )
            try:
                if self.auth_profile == "auto":
                    probe = await self.hass.async_add_executor_job(
                        self.client.probe_auth_methods, 1.5
                    )
                    if (
                        probe.get("legacy_static", {}).get("supported")
                        and not probe.get("modern_dynamic", {}).get("supported")
                        and not probe.get("standard_dynamic", {}).get("supported")
                    ):
                        self.auth_profile = "legacy"
                        self.client.auth_profile = "legacy"

                await self.client.async_start_auth()

                if self.auth_profile == "legacy" and self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data={
                            **self._reauth_entry.data,
                            CONF_IP_ADDRESS: self.ip_address,
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
                    )
                    await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")

                return await self.async_step_auth()
            except Exception as e:
                _LOGGER.exception("Failed to initiate reconfigure pairing: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS, default=default_ip): str,
                vol.Optional(
                    CONF_AUTH_PROFILE, default=default_profile
                ): vol.In(AUTH_PROFILES),
            }),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle SSDP discovery."""
        upnp = discovery_info.upnp or {}
        model_desc = upnp.get("modelDescription") or ""
        friendly_name = upnp.get("friendlyName", "")
        manufacturer = upnp.get("manufacturer", "")

        # Filter non-VIDAA devices
        is_vidaa = (
            "vidaa_support" in model_desc
            or "transport_protocol" in model_desc
            or "hisense" in manufacturer.lower()
            or "vidaa" in friendly_name.lower()
            or "hisense" in friendly_name.lower()
        )
        if not is_vidaa:
            return self.async_abort(reason="not_vidaa_tv")

        host = discovery_info.ssdp_headers.get("_host") or discovery_info.ssdp_location
        if host and "://" in host:
            host = urlparse(host).hostname

        if not host:
            return self.async_abort(reason="cannot_connect")

        self.ip_address = host
        self.discovered_title = (
            friendly_name
            if friendly_name and friendly_name != "Renderer"
            else f"Hisense TV ({host})"
        )
        self.manufacturer = manufacturer or "Hisense"
        self.model = upnp.get("modelName") or upnp.get("modelNumber") or "VIDAA TV"

        for line in model_desc.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k in ("macWifi", "macEthernet") and v:
                    from homeassistant.helpers.device_registry import format_mac

                    self.mac_address = format_mac(v)
                    break

        if not self.mac_address:
            raw_mac = await self.hass.async_add_executor_job(get_arp_mac, host)
            if raw_mac:
                from homeassistant.helpers.device_registry import format_mac

                self.mac_address = format_mac(raw_mac)

        unique_id = self.mac_address or discovery_info.ssdp_udn
        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: self.ip_address}
            )

        return await self.async_step_discovery_confirm()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle Zeroconf / mDNS discovery."""
        host = discovery_info.host
        if not host:
            return self.async_abort(reason="cannot_connect")

        self.ip_address = host
        self.discovered_title = f"Hisense TV ({host})"
        raw_mac = await self.hass.async_add_executor_job(get_arp_mac, host)
        if raw_mac:
            from homeassistant.helpers.device_registry import format_mac

            self.mac_address = format_mac(raw_mac)
            await self.async_set_unique_id(self.mac_address)
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: self.ip_address}
            )

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm discovery setup with user."""
        errors = {}
        if user_input is not None:
            self.client = HisenseTvClient(
                self.ip_address, self.mac_address, auth_profile=self.auth_profile
            )
            try:
                if self.auth_profile == "auto":
                    probe = await self.hass.async_add_executor_job(
                        self.client.probe_auth_methods, 1.5
                    )
                    if (
                        probe.get("legacy_static", {}).get("supported")
                        and not probe.get("modern_dynamic", {}).get("supported")
                        and not probe.get("standard_dynamic", {}).get("supported")
                    ):
                        self.auth_profile = "legacy"
                        self.client.auth_profile = "legacy"

                await self.client.async_start_auth()

                if self.auth_profile == "legacy":
                    return await self.async_step_options()

                return await self.async_step_auth()
            except Exception as e:
                _LOGGER.exception(
                    "Failed to connect or initiate auth with TV at %s: %s",
                    self.ip_address,
                    e,
                )
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self.discovered_title or self.ip_address or "Hisense TV",
                "ip_address": self.ip_address or "",
            },
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow configuring initial options during setup."""
        if user_input is not None and self.client:
            entry_data = {
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
            }
            if self.model:
                entry_data[CONF_MODEL] = self.model
            if self.manufacturer:
                entry_data[CONF_MANUFACTURER] = self.manufacturer
            if self.sw_version:
                entry_data[CONF_SW_VERSION] = self.sw_version

            return self.async_create_entry(
                title=self.discovered_title or f"Hisense TV ({self.ip_address})",
                data=entry_data,
                options={
                    CONF_ENABLE_REMOTE: user_input.get(
                        CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE
                    ),
                    CONF_ENABLE_WOL: user_input.get(
                        CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL
                    ),
                    CONF_INCLUDE_APPS_IN_SOURCES: user_input.get(
                        CONF_INCLUDE_APPS_IN_SOURCES,
                        DEFAULT_INCLUDE_APPS_IN_SOURCES,
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
