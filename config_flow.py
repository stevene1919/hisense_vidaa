import voluptuous as vol
from homeassistant import config_entries

from .client import HisenseTvClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_ACCESS_TOKEN_TIME,
    CONF_CLIENT_ID,
    CONF_IP_ADDRESS,
    CONF_MAC_ADDRESS,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_DURATION,
    CONF_REFRESH_TOKEN_TIME,
    CONF_USERNAME,
    DOMAIN,
)


class HisenseVidaaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.ip_address = None
        self.mac_address = None
        self.client = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self.ip_address = user_input[CONF_IP_ADDRESS]

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
            self.client = HisenseTvClient(self.ip_address, self.mac_address)
            try:
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

                return await self.async_step_auth()
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
            }),
            errors=errors
        )

    async def async_step_auth(self, user_input=None):
        errors = {}
        if user_input is not None:
            pin_code = user_input["pin_code"]
            try:
                await self.client.async_submit_pin(pin_code)
                return self.async_create_entry(
                    title=f"Hisense TV ({self.ip_address})",
                    data={
                        CONF_IP_ADDRESS: self.ip_address,
                        CONF_MAC_ADDRESS: self.mac_address,
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
                )
            except Exception:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({
                vol.Required("pin_code"): str,
            }),
            errors=errors
        )
