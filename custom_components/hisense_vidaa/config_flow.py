"""Config flow for Hisense VIDAA TV integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

if TYPE_CHECKING:
    from . import HisenseVidaaConfigEntry

from .client import HisenseTvClient
from .const import (
    AUTH_PROFILE_SELECTOR,
    BRAND_SELECTOR,
    CONF_AUTH_PROFILE,
    CONF_BRAND,
    CONF_CERTFILE,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_USE_SSL,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_BRAND,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_SOUND_CONTROLS,
    DEFAULT_USE_SSL,
    DOMAIN,
)
from .discovery import BRAND_MAP, GENERIC_MANUFACTURERS, normalize_brand_code
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
from .protocol.pairing import PairingStatusError, async_probe_pairing_challenge

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
        self.brand: str = DEFAULT_BRAND
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

    async def _async_discover_device_name(self) -> None:
        """Discovers friendly device name and model info from UPnP/DLNA."""
        details = await async_discover_device_details(self.hass, self.client, self.ip_address)
        self.discovered_title = details["title"]
        if details.get("model"):
            self.model = details["model"]
        if details.get("manufacturer"):
            self.manufacturer = details["manufacturer"]
        discovered_brand = details.get("brand")
        if discovered_brand:
            if self.brand == DEFAULT_BRAND or discovered_brand != DEFAULT_BRAND:
                self.brand = discovered_brand
        elif self.client and self.client.brand and self.client.brand != DEFAULT_BRAND:
            self.brand = self.client.brand
        if details.get("sw_version"):
            self.sw_version = details["sw_version"]

    async def _async_probe_device_capabilities(self) -> None:
        """Probe TV capabilities (picture/sound menus) to set intelligent default options."""
        await async_probe_device_capabilities(self.hass, self.client, self.ip_address)

    async def _async_disconnect_existing_client(self) -> None:
        """Disconnect any running client for this IP/MAC to avoid MQTT session collision during pairing."""
        # Only ever disconnect the entry being re-paired: a sibling entry that
        # happens to share the IP/MAC must keep its client connected.
        entry_id = self._reauth_entry.entry_id if self._reauth_entry else None
        await async_disconnect_existing_client(
            self.hass, self.ip_address, self.mac_address, entry_id=entry_id
        )

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
            brand=self.brand,
        )

    async def _async_init_client_and_auth(
        self, is_reauth: bool = False, reauth_reason: str = "reauth_successful"
    ) -> config_entries.ConfigFlowResult:
        """Helper to initialize client, perform static auth check, and route to PIN or options."""
        if not self.mac_address:
            self.mac_address = await async_resolve_mac(self.hass, self.ip_address)

        # Duplicate/unique-id guard MUST run before touching the running client:
        # its AbortFlow must not leave an existing (working) entry disconnected.
        if self.mac_address and self._reauth_entry is None:
            await self.async_set_unique_id(self.mac_address)
            self._abort_if_unique_id_configured()

        if (
            self.brand == DEFAULT_BRAND
            and self.manufacturer is None
            and self.ip_address
            and self.hass
        ):
            try:
                from .tv.fingerprint import query_upnp_descriptor

                upnp_desc = await self.hass.async_add_executor_job(
                    query_upnp_descriptor, self.ip_address, 1.5
                )
                detected = upnp_desc.get("brand") or upnp_desc.get("manufacturer")
                if detected:
                    self.brand = normalize_brand_code(detected)
                    raw_mfg = upnp_desc.get("manufacturer")
                    if raw_mfg and raw_mfg.strip().lower() not in GENERIC_MANUFACTURERS:
                        self.manufacturer = BRAND_MAP.get(raw_mfg.strip().lower(), raw_mfg.strip())
                    elif self.brand in BRAND_MAP:
                        self.manufacturer = BRAND_MAP[self.brand]
            except Exception:
                pass

        await self._async_disconnect_existing_client()
        if self.use_ssl and not (self.certfile and self.keyfile):
            await self._async_resolve_ssl_certs()
        session = async_get_clientsession(self.hass) if self.hass else None
        self.client = HisenseTvClient(
            self.ip_address,
            self.mac_address,
            auth_profile=self.auth_profile,
            certfile=self.certfile if self.use_ssl else None,
            keyfile=self.keyfile if self.use_ssl else None,
            use_ssl=self.use_ssl,
            brand=self.brand,
            session=session,
        )
        self.client._loop = self.hass.loop

        if self.auth_profile == "auto":
            probe = await self.client.async_probe_auth_methods(1.5)
            if (
                probe.get("legacy_static", {}).get("supported")
                and not probe.get("modern_dynamic", {}).get("supported")
                and not probe.get("middle_dynamic", {}).get("supported")
                and not probe.get("standard_dynamic", {}).get("supported")
            ):
                self.auth_profile = "legacy"
                self.client.auth_profile = "legacy"

        await self.client.async_start_auth()
        if self.client.brand and self.client.brand != self.brand:
            self.brand = self.client.brand
            if self.brand in BRAND_MAP:
                self.manufacturer = BRAND_MAP[self.brand]

        if self.auth_profile in ("legacy", "static"):
            return await self._async_static_pairing_step(is_reauth, reauth_reason)

        return await self.async_step_auth()

    async def _async_static_pairing_step(
        self, is_reauth: bool, reauth_reason: str
    ) -> config_entries.ConfigFlowResult:
        """Probe a static session for a PIN challenge before continuing as before.

        The TV shows a 4-digit code (and pushes it to .../data/authentication)
        only when it does not yet know this client. Already-paired TVs and
        pre-dynamic firmware answer normally, so nothing changes for them - no
        form is shown and the flow continues exactly as it did before.
        """
        try:
            challenged = await async_probe_pairing_challenge(self.client)
        except PairingStatusError as e:
            _LOGGER.warning("[%s] TV pairing dialog %s during challenge probe", self.ip_address, e.status)
            self._pairing_error = "invalid_auth"
            return await self.async_step_auth()

        if challenged:
            return await self.async_step_auth()

        # No challenge: behave exactly as today. Drop the probe connection so
        # the remaining steps see the same (unconnected) client as before.
        await self.client.async_disconnect()
        if is_reauth and self._reauth_entry:
            return await self._async_finish_reauth(reason=reauth_reason)
        await self._async_discover_device_name()
        await self._async_probe_device_capabilities()
        return await self.async_step_options()

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
            if CONF_BRAND in user_input:
                self.brand = user_input[CONF_BRAND]
                if self.brand in BRAND_MAP:
                    self.manufacturer = BRAND_MAP[self.brand]
            self.mac_address = await async_resolve_mac(self.hass, self.ip_address)

            if self.auth_profile in ("auto", "legacy"):
                if await self._async_resolve_ssl_certs():
                    try:
                        return await self._async_init_client_and_auth()
                    except AbortFlow:
                        # HA flow control (e.g. duplicate unique_id) must not be
                        # reported as cannot_connect.
                        raise
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
                    CONF_BRAND, default=DEFAULT_BRAND
                ): BRAND_SELECTOR,
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
        if self._pairing_error:
            # Surfaced by the static-session challenge probe (TV busy / dialog closed).
            errors["base"] = self._pairing_error
            self._pairing_error = None

        if not self.client:
            if not self.ip_address and self._reauth_entry:
                opts = (
                    dict(self._reauth_entry.options)
                    if isinstance(getattr(self._reauth_entry, "options", None), dict)
                    else {}
                )
                data = (
                    dict(self._reauth_entry.data)
                    if isinstance(getattr(self._reauth_entry, "data", None), dict)
                    else {}
                )
                self.ip_address = data.get(CONF_IP_ADDRESS)
                self.mac_address = data.get(CONF_MAC_ADDRESS)
                self.auth_profile = opts.get(CONF_AUTH_PROFILE, data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE))
                self.brand = opts.get(CONF_BRAND, data.get(CONF_BRAND, DEFAULT_BRAND))
                self.use_ssl = opts.get(CONF_USE_SSL, data.get(CONF_USE_SSL, DEFAULT_USE_SSL))
                self.certfile = opts.get(CONF_CERTFILE, data.get(CONF_CERTFILE))
                self.keyfile = opts.get(CONF_KEYFILE, data.get(CONF_KEYFILE))

            if self.ip_address:
                session = async_get_clientsession(self.hass) if self.hass else None
                self.client = HisenseTvClient(
                    self.ip_address,
                    self.mac_address,
                    auth_profile=self.auth_profile,
                    brand=self.brand,
                    session=session,
                    certfile=self.certfile,
                    keyfile=self.keyfile,
                    use_ssl=self.use_ssl,
                )
                self.client._loop = self.hass.loop
                try:
                    await self.client.async_start_auth()
                    if self.client.brand and self.client.brand != self.brand:
                        self.brand = self.client.brand
                        if self.brand in BRAND_MAP:
                            self.manufacturer = BRAND_MAP[self.brand]
                except Exception as e:
                    _LOGGER.warning("[%s] Failed to connect to TV to show PIN: %s", self.ip_address, e)
                    errors["base"] = "cannot_connect"

        if user_input is not None and self.client:
            pin_code = str(user_input["pin_code"]).strip().replace(" ", "").replace("-", "")
            # F9-leg6: guard ONLY the submit call - a failure afterwards (name
            # discovery, capability probe) must not be reported as a bad PIN.
            try:
                await self.client.async_submit_pin(pin_code)
            except PairingStatusError as e:
                # TV closed the dialog or another remote occupies the slot; the
                # form is re-shown so the pairing can be retried.
                _LOGGER.warning("[%s] TV pairing dialog %s while submitting PIN", self.ip_address, e.status)
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.warning("[%s] Failed to validate PIN or retrieve tokens from TV: %s", self.ip_address, e)
                errors["base"] = "invalid_auth"
            else:
                if self._reauth_entry:
                    return await self._async_finish_reauth(reason="reauth_successful")

                await self._async_discover_device_name()
                await self._async_probe_device_capabilities()
                if self.client and self.client.brand and self.client.brand != DEFAULT_BRAND and self.brand == DEFAULT_BRAND:
                    self.brand = self.client.brand
                return await self.async_step_options()

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
        picture_supported = (
            bool(getattr(self.client, "picture_settings", None))
            if self.client
            else DEFAULT_ENABLE_PICTURE_CONTROLS
        )
        sound_supported = (
            bool(getattr(self.client, "sound_settings", None))
            if self.client
            else DEFAULT_ENABLE_SOUND_CONTROLS
        )

        if user_input is not None and self.client:
            entry_data = self._get_client_auth_data()

            await self.client.async_disconnect()
            self.client = None

            default_title = f"{BRAND_MAP.get(self.brand, 'Hisense')} TV ({self.ip_address})"
            return self.async_create_entry(
                title=self.discovered_title or default_title,
                data=entry_data,
                options=build_entry_options(user_input, picture_supported, sound_supported),
            )

        return self.async_show_form(
            step_id="options",
            data_schema=build_options_schema(picture_supported, sound_supported),
        )

    @callback
    def async_remove(self) -> None:
        """Clean up running flow client when config flow is aborted or closed."""
        if self.client:
            client = self.client
            self.client = None
            if hasattr(self, "hass") and self.hass:
                task = self.hass.async_create_background_task(
                    client.async_disconnect(),
                    "hisense_vidaa_config_flow_remove",
                )
                def _done_callback(fut: Any) -> None:
                    if not fut.cancelled() and fut.exception():
                        _LOGGER.debug("Error disconnecting client on flow remove: %s", fut.exception())
                task.add_done_callback(_done_callback)
            else:
                try:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    self._remove_task = loop.create_task(client.async_disconnect())
                except RuntimeError:
                    # Fallback if no running loop: close sync or ignore
                    if hasattr(client, "disconnect"):
                        client.disconnect()
