import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_MAC_ADDRESS,
    CONF_CLIENT_ID,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_TIME,
    CONF_ACCESS_TOKEN_DURATION,
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_TIME,
    CONF_REFRESH_TOKEN_DURATION
)
from .client import HisenseTvClient

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
            self.mac_address = user_input.get(CONF_MAC_ADDRESS)
            
            # Start the client connection to TV
            self.client = HisenseTvClient(self.ip_address, self.mac_address)
            try:
                await self.client.async_start_auth()
                return await self.async_step_auth()
            except Exception as e:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Optional(CONF_MAC_ADDRESS): str,
            }),
            errors=errors
        )

    async def async_step_auth(self, user_input=None):
        errors = {}
        if user_input is not None:
            pin_code = user_input["pin_code"]
            try:
                token_data = await self.client.async_submit_pin(pin_code)
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
            except Exception as e:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({
                vol.Required("pin_code"): str,
            }),
            errors=errors
        )
