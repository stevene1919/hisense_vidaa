import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .client import HisenseTvClient
from .const import (
    AUTH_PROFILE_SELECTOR,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_CLIENT_ID,
    CONF_ENABLE_AUDIO_ONLY,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_SOUND_CONTROLS,
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
    DEFAULT_ENABLE_AUDIO_ONLY,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_SOUND_CONTROLS,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_USE_SSL,
    DOMAIN,
)
from .crypto import check_certs_exist, get_profile_default_cert_paths, resolve_certificates
from .discovery import get_arp_mac, parse_ssdp_discovery, parse_zeroconf_discovery
from .options_flow import HisenseVidaaOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)


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

    async def _async_probe_device_capabilities(self) -> None:
        """Probe TV capabilities (picture/sound menus) to set intelligent default options."""
        if not self.client or not self.client.connected:
            return
        try:
            await self.hass.async_add_executor_job(self.client.get_picture_settings)
            await self.hass.async_add_executor_job(self.client.get_sound_settings)
            await asyncio.sleep(1.0)
        except Exception as e:
            _LOGGER.debug("[%s] Error during capability probe: %s", self.ip_address, e)

    async def _async_disconnect_existing_client(self) -> None:
        """Disconnect any running client for this IP/MAC to avoid MQTT session collision during pairing."""
        if not hasattr(self.hass, "data") or not isinstance(self.hass.data, dict):
            return
        for entry_id, entry_data in list(self.hass.data.get(DOMAIN, {}).items()):
            client = entry_data.get("client") if isinstance(entry_data, dict) else entry_data
            if client and (getattr(client, "ip", None) == self.ip_address or (self.mac_address and getattr(client, "mac", None) == self.mac_address)):
                _LOGGER.debug("Disconnecting existing running client for %s during pairing flow", self.ip_address)
                await self.hass.async_add_executor_job(client.disconnect)

    async def _async_init_client_and_auth(self) -> config_entries.ConfigFlowResult:
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

        # If auto-detect is selected, probe if TV uses legacy static credentials
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

        # If MAC was not in ARP before, try again now that TCP connection was established
        if not self.mac_address:
            raw_mac = await self.hass.async_add_executor_job(
                get_arp_mac, self.ip_address
            )
            if raw_mac:
                self.mac_address = format_mac(raw_mac)

        if self.mac_address:
            await self.async_set_unique_id(self.mac_address)
            self._abort_if_unique_id_configured()

        if self.auth_profile == "legacy":
            await self._async_discover_device_name()
            await self._async_probe_device_capabilities()
            return await self.async_step_options()

        return await self.async_step_auth()

    def _get_client_auth_data(self) -> dict[str, Any]:
        """Collect authentication credentials and device attributes dictionary."""
        data: dict[str, Any] = {
            CONF_IP_ADDRESS: self.ip_address,
            CONF_AUTH_PROFILE: self.auth_profile,
            CONF_USE_SSL: self.use_ssl,
        }
        if self.mac_address:
            data[CONF_MAC_ADDRESS] = self.mac_address
        if self.client:
            data.update({
                CONF_CLIENT_ID: self.client.client_id,
                CONF_USERNAME: self.client.username,
                CONF_PASSWORD: self.client.password,
                CONF_ACCESS_TOKEN: self.client.access_token,
                CONF_ACCESS_TOKEN_TIME: self.client.access_token_time,
                CONF_ACCESS_TOKEN_DURATION: self.client.access_token_duration,
                CONF_REFRESH_TOKEN: self.client.refresh_token,
                CONF_REFRESH_TOKEN_TIME: self.client.refresh_token_time,
                CONF_REFRESH_TOKEN_DURATION: self.client.refresh_token_duration,
            })
        if self.certfile:
            data[CONF_CERTFILE] = self.certfile
        if self.keyfile:
            data[CONF_KEYFILE] = self.keyfile
        if self.model:
            data[CONF_MODEL] = self.model
        if self.manufacturer:
            data[CONF_MANUFACTURER] = self.manufacturer
        if self.sw_version:
            data[CONF_SW_VERSION] = self.sw_version
        return data

    async def _async_finish_reauth(
        self, reason: str = "reauth_successful"
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
                self.mac_address = format_mac(raw_mac)

            if self.auth_profile == "auto" or self.auth_profile == "legacy":
                if self._resolve_ssl_certs():
                    try:
                        return await self._async_init_client_and_auth()
                    except Exception as e:
                        _LOGGER.warning("[%s] Failed to connect or initiate auth with TV: %s", self.ip_address, e)
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

            # Disconnect existing running client to avoid MQTT session collision during re-pairing
            await self._async_disconnect_existing_client()

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
                    return await self._async_finish_reauth(reason="reconfigure_successful")

                return await self.async_step_auth()
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

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle SSDP discovery."""
        parsed = await self.hass.async_add_executor_job(
            parse_ssdp_discovery, discovery_info
        )
        if not parsed:
            return self.async_abort(reason="not_vidaa_tv")

        self.ip_address = parsed.host
        self.discovered_title = parsed.title
        self.manufacturer = parsed.manufacturer
        self.model = parsed.model
        self.mac_address = parsed.mac_address

        if parsed.unique_id:
            await self.async_set_unique_id(parsed.unique_id)
            self._abort_if_unique_id_configured(
                updates={CONF_IP_ADDRESS: self.ip_address}
            )

        return await self.async_step_discovery_confirm()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle Zeroconf / mDNS discovery."""
        parsed = await self.hass.async_add_executor_job(
            parse_zeroconf_discovery, discovery_info
        )
        if not parsed or not parsed.host:
            return self.async_abort(reason="cannot_connect")

        self.ip_address = parsed.host
        self.discovered_title = parsed.title
        self.mac_address = parsed.mac_address
        if not self.mac_address and parsed.host:
            raw_mac = await self.hass.async_add_executor_job(get_arp_mac, parsed.host)
            if raw_mac:
                self.mac_address = format_mac(raw_mac)

        unique_id = self.mac_address or parsed.unique_id
        if unique_id:
            await self.async_set_unique_id(unique_id)
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
                    _LOGGER.warning(
                        "[%s] Failed to connect or initiate auth with TV: %s",
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

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Allow configuring initial options during setup."""
        pic_supported = bool(getattr(self.client, "picture_settings", None)) if self.client else DEFAULT_ENABLE_PICTURE_CONTROLS
        sound_supported = bool(getattr(self.client, "sound_settings", None)) if self.client else DEFAULT_ENABLE_SOUND_CONTROLS

        if user_input is not None and self.client:
            entry_data = self._get_client_auth_data()

            # Disconnect the flow client before creating entry to avoid MQTT session collision
            await self.hass.async_add_executor_job(self.client.disconnect)
            self.client = None

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
                    CONF_ENABLE_PICTURE_CONTROLS: user_input.get(
                        CONF_ENABLE_PICTURE_CONTROLS,
                        pic_supported,
                    ),
                    CONF_ENABLE_SOUND_CONTROLS: user_input.get(
                        CONF_ENABLE_SOUND_CONTROLS,
                        sound_supported,
                    ),
                    CONF_ENABLE_AUDIO_ONLY: user_input.get(
                        CONF_ENABLE_AUDIO_ONLY,
                        DEFAULT_ENABLE_AUDIO_ONLY,
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
                vol.Optional(
                    CONF_ENABLE_PICTURE_CONTROLS,
                    default=pic_supported,
                ): bool,
                vol.Optional(
                    CONF_ENABLE_SOUND_CONTROLS,
                    default=sound_supported,
                ): bool,
                vol.Optional(
                    CONF_ENABLE_AUDIO_ONLY,
                    default=DEFAULT_ENABLE_AUDIO_ONLY,
                ): bool,
            }),
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


