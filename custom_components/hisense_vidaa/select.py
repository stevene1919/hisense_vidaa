import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

AUDIO_OUTPUT_TV_SPEAKERS = "TV Speakers"
AUDIO_OUTPUT_ARC = "ARC / eARC"
AUDIO_OUTPUT_HEADPHONE = "Headphone / Bluetooth"

AUDIO_OUTPUT_OPTIONS = [
    AUDIO_OUTPUT_TV_SPEAKERS,
    AUDIO_OUTPUT_ARC,
    AUDIO_OUTPUT_HEADPHONE,
]

VOLUME_TYPE_MAP = {
    0: AUDIO_OUTPUT_TV_SPEAKERS,
    1: AUDIO_OUTPUT_ARC,
    2: AUDIO_OUTPUT_HEADPHONE,
}


class HisenseVidaaAudioOutputSelect(SelectEntity):
    """Hisense VIDAA Audio Output Mode selector."""

    _attr_has_entity_name = True
    _attr_name = "Audio Output Mode"
    _attr_icon = "mdi:speaker-multiple"
    _attr_options = AUDIO_OUTPUT_OPTIONS

    def __init__(
        self,
        client,
        mac: str | None,
        entry_id: str,
        name: str,
        model: str | None = None,
        manufacturer: str | None = None,
        sw_version: str | None = None,
    ) -> None:
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name
        self._model = model or "VIDAA TV"
        self._manufacturer = manufacturer or "Hisense"
        self._sw_version = sw_version
        self._volume_type = 0

    async def async_added_to_hass(self) -> None:
        self._client.register_volume_callback(self._handle_volume_update)

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_audio_output_select"

    @property
    def device_info(self) -> DeviceInfo:
        info = DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._name,
            manufacturer=self._manufacturer,
            model=self._model,
            sw_version=self._sw_version,
        )
        if self._mac:
            cleaned_mac = self._mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}
        return info

    @property
    def available(self) -> bool:
        return bool(self._client and self._client.connected)

    @property
    def current_option(self) -> str:
        return VOLUME_TYPE_MAP.get(self._volume_type, AUDIO_OUTPUT_TV_SPEAKERS)

    def _handle_volume_update(self, data: dict[str, Any]) -> None:
        vol_type = data.get("volume_type")
        if vol_type is not None:
            self._volume_type = int(vol_type)
            if self.hass and hasattr(self.hass, "loop") and self.hass.loop:
                self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)
            else:
                self.schedule_update_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the audio output option."""
        if option == AUDIO_OUTPUT_TV_SPEAKERS:
            self._volume_type = 0
            await self.hass.async_add_executor_job(self._client.send_key, "KEY_AUDIO_ONLY")
        elif option == AUDIO_OUTPUT_ARC:
            self._volume_type = 1
            await self.hass.async_add_executor_job(self._client.send_key, "KEY_SOUND")
        elif option == AUDIO_OUTPUT_HEADPHONE:
            self._volume_type = 2
            await self.hass.async_add_executor_job(self._client.send_key, "KEY_HEADPHONE")
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA select platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client = data.get("client", data) if isinstance(data, dict) else data
    mac = config_entry.data.get(CONF_MAC_ADDRESS)

    entity = HisenseVidaaAudioOutputSelect(
        client=client,
        mac=mac,
        entry_id=config_entry.entry_id,
        name=config_entry.title,
        model=config_entry.data.get(CONF_MODEL, "VIDAA TV"),
        manufacturer=config_entry.data.get(CONF_MANUFACTURER, "Hisense"),
        sw_version=config_entry.data.get(CONF_SW_VERSION),
    )
    async_add_entities([entity])
