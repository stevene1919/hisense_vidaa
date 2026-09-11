import logging
import os
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .client import HisenseTvClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_CLIENT_ID,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_SW_VERSION,
    CONF_USE_SSL,
    CONF_USERNAME,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_CERT_DIR,
    DEFAULT_CERT_FILENAME,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_KEY_FILENAME,
    DEFAULT_USE_SSL,
    DOMAIN,
)
from .crypto import check_certs_exist, resolve_certificates
from .discovery import get_arp_mac
from .options_flow import HisenseVidaaOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

AUTH_PROFILE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value="auto", label="Auto Detect (Recommended)"),
            selector.SelectOptionDict(value="modern", label="VIDAA 2.0 / 2024+ (vidaa_2024)"),
            selector.SelectOptionDict(value="remotenow", label="RemoteNOW / 2018–2023 (standard)"),
            selector.SelectOptionDict(value="legacy", label="Legacy Unencrypted (No SSL / static)"),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="auth_profile",
    )
)


class HisenseVidaaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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

    def _resolve_ssl_certs(self) -> bool:
        """Attempts to resolve certificates from disk or profile. Returns True if certs exist or not needed."""
        if self.auth_profile == "legacy":
            self.use_ssl = False
            self.certfile, self.keyfile = None, None
            return True
        resolved_cert, resolved_key = resolve_certificates(self.auth_profile)
        if check_certs_exist(resolved_cert, resolved_key):
            self.certfile = resolved_cert
            self.keyfile = resolved_key
            self.use_ssl = True
            return True
        return False

    async def _async_discover_device_name(self) -> None:
        """Discovers friendly device name and model info from UPnP/DLNA."""
        self.discovered_title = f"Hisense TV ({self.ip_address})"
        if not self.client:
            return
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
            if fp.get("model_code") or fp.get("model_name"):
                self.model = fp.get("model_code") or fp.get("model_name")
            if fp.get("manufacturer") or fp.get("brand"):
                self.manufacturer = fp.get("manufacturer") or fp.get("brand")
            if fp.get("firmware_version"):
                self.sw_version = fp.get("firmware_version")
        except Exception:
            pass

    async def _async_init_client_and_auth(self) -> config_entries.ConfigFlowResult:
        """Helper to initialize client, perform static auth check, and route to PIN or options."""
        self.client = HisenseTvClient(
            self.ip_address,
            self.mac_address,
            auth_profile=self.auth_profile,
            certfile=self.certfile if self.use_ssl else None,
            keyfile=self.keyfile if self.use_ssl else None,
            use_ssl=self.use_ssl,
        )

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
            await self._async_discover_device_name()
            return await self.async_step_options()

        return await self.async_step_auth()

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

            if self.auth_profile == "auto" or self.auth_profile == "legacy":
                if self._resolve_ssl_certs():
                    try:
                        return await self._async_init_client_and_auth()
                    except Exception as e:
                        _LOGGER.exception("Failed to connect or initiate auth with TV at %s: %s", self.ip_address, e)
                        errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_certs()
            else:
                # Explicit profile selected (modern / remotenow) -> route to certs configuration step
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
            pin_code = str(user_input["pin_code"]).strip().replace(" ", "").replace("-", "")
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

                await self._async_discover_device_name()
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

            if self.auth_profile == "auto" or self.auth_profile == "legacy":
                if not self._resolve_ssl_certs():
                    return await self.async_step_certs()
            else:
                return await self.async_step_certs()

            self.client = HisenseTvClient(
                self.ip_address,
                self.mac_address,
                auth_profile=self.auth_profile,
                certfile=self.certfile if self.use_ssl else None,
                keyfile=self.keyfile if self.use_ssl else None,
                use_ssl=self.use_ssl,
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
                            CONF_USE_SSL: self.use_ssl,
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
                ): AUTH_PROFILE_SELECTOR,
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
            if self._resolve_ssl_certs():
                try:
                    return await self._async_init_client_and_auth()
                except Exception as e:
                    _LOGGER.exception(
                        "Failed to connect or initiate auth with TV at %s: %s",
                        self.ip_address,
                        e,
                    )
                    errors["base"] = "cannot_connect"
            else:
                # Certs not present on disk: route to certs configuration
                return await self.async_step_certs()

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "name": self.discovered_title or self.ip_address or "Hisense TV",
                "ip_address": self.ip_address or "",
            },
            errors=errors,
        )

    async def async_step_certs(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle certificate file configuration step."""
        errors: dict[str, str] = {}
        config_dir = self.hass.config.config_dir if hasattr(self.hass, "config") else "/config"
        default_cert_dir = os.path.join(config_dir, DEFAULT_CERT_DIR)

        # Determine profile-specific default filenames
        if self.auth_profile == "modern":
            default_cert_name = "vidaa_2024_cert.pem"
            default_key_name = "vidaa_2024_key.pem"
        elif self.auth_profile == "remotenow":
            default_cert_name = "remotenow_2018_cert.pem"
            default_key_name = "remotenow_2018_key.pem"
        else:
            default_cert_name = DEFAULT_CERT_FILENAME
            default_key_name = DEFAULT_KEY_FILENAME

        resolved_cert, resolved_key = resolve_certificates(self.auth_profile)
        if check_certs_exist(resolved_cert, resolved_key):
            default_cert_path = resolved_cert
            default_key_path = resolved_key
        else:
            default_cert_path = os.path.join(default_cert_dir, default_cert_name)
            default_key_path = os.path.join(default_cert_dir, default_key_name)

        if user_input is not None:
            self.use_ssl = user_input.get(CONF_USE_SSL, DEFAULT_USE_SSL)
            self.certfile = user_input.get(CONF_CERTFILE) or default_cert_path
            self.keyfile = user_input.get(CONF_KEYFILE) or default_key_path

            if self.use_ssl and not check_certs_exist(self.certfile, self.keyfile):
                errors["base"] = "certs_not_found"
            else:
                try:
                    return await self._async_init_client_and_auth()
                except Exception as e:
                    _LOGGER.exception("Failed to connect or initiate auth: %s", e)
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
                CONF_USE_SSL: self.use_ssl,
            }
            if self.certfile:
                entry_data[CONF_CERTFILE] = self.certfile
            if self.keyfile:
                entry_data[CONF_KEYFILE] = self.keyfile
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
                    CONF_ENABLE_MEDIA_CONTROLS: user_input.get(
                        CONF_ENABLE_MEDIA_CONTROLS,
                        DEFAULT_ENABLE_MEDIA_CONTROLS,
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
                vol.Optional(
                    CONF_ENABLE_MEDIA_CONTROLS,
                    default=DEFAULT_ENABLE_MEDIA_CONTROLS,
                ): bool,
            }),
        )
