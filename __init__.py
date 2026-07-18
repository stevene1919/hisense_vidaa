import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

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

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hisense VIDAA TV from a config entry."""
    data = entry.data
    client = HisenseTvClient(
        ip=data[CONF_IP_ADDRESS],
        mac=data.get(CONF_MAC_ADDRESS),
        client_id=data[CONF_CLIENT_ID],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        access_token=data[CONF_ACCESS_TOKEN],
        access_token_time=data[CONF_ACCESS_TOKEN_TIME],
        access_token_duration=data[CONF_ACCESS_TOKEN_DURATION],
        refresh_token=data[CONF_REFRESH_TOKEN],
        refresh_token_time=data[CONF_REFRESH_TOKEN_TIME],
        refresh_token_duration=data[CONF_REFRESH_TOKEN_DURATION]
    )

    # Check and refresh tokens, run client loop in executor
    updated = await hass.async_add_executor_job(client.check_and_refresh_token)
    if updated:
        hass.config_entries.async_update_entry(entry, data={
            **entry.data,
            CONF_ACCESS_TOKEN: client.access_token,
            CONF_ACCESS_TOKEN_TIME: client.access_token_time,
            CONF_ACCESS_TOKEN_DURATION: client.access_token_duration,
            CONF_REFRESH_TOKEN: client.refresh_token,
            CONF_REFRESH_TOKEN_TIME: client.refresh_token_time,
            CONF_REFRESH_TOKEN_DURATION: client.refresh_token_duration,
        })

    # Start running background thread loop for MQTT client in executor
    await hass.async_add_executor_job(client.connect_and_run)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["media_player"])
    if unload_ok:
        client = hass.data[DOMAIN].pop(entry.entry_id)
        client.disconnect()
    return unload_ok
