import logging

from homeassistant.components.notify import NotifyEntity
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


class HisenseVidaaNotifyEntity(NotifyEntity):
    """Hisense VIDAA Toast Notification entity."""

    _attr_has_entity_name = True
    _attr_name = "Notifications"
    _attr_icon = "mdi:television-guide"

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

    @property
    def unique_id(self) -> str:
        return f"{self._entry_id}_notify"

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

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification message to the TV."""
        await self.hass.async_add_executor_job(
            self._client.show_message, message, title
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense VIDAA notify platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client = data.get("client", data) if isinstance(data, dict) else data
    mac = config_entry.data.get(CONF_MAC_ADDRESS)

    entity = HisenseVidaaNotifyEntity(
        client=client,
        mac=mac,
        entry_id=config_entry.entry_id,
        name=config_entry.title,
        model=config_entry.data.get(CONF_MODEL, "VIDAA TV"),
        manufacturer=config_entry.data.get(CONF_MANUFACTURER, "Hisense"),
        sw_version=config_entry.data.get(CONF_SW_VERSION),
    )
    async_add_entities([entity])
