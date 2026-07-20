import logging
import time
import threading
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature
)
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, CONF_MAC_ADDRESS

_LOGGER = logging.getLogger(__name__)

class HisenseVidaaMediaPlayer(MediaPlayerEntity):
    def __init__(self, client, mac, entry_id, name):
        self._client = client
        self._mac = mac
        self._entry_id = entry_id
        self._name = name

        self._state = STATE_OFF
        self._volume = 0
        self._muted = False
        self._source = None
        self._source_list = []
        self._source_dict = {}
        self._app_list = []
        self._app_dict = {}
        self._channel_infos = {}

    async def async_added_to_hass(self):
        """Register callbacks and query initial state when entity is added."""
        self._client.on_state_update = self._handle_state_update
        self._client.on_volume_update = self._handle_volume_update
        self._client.on_sourcelist_update = self._handle_sourcelist_update
        self._client.on_applist_update = self._handle_applist_update
        self._client.on_disconnected_callback = self._handle_disconnected

        # Query initial state now that callbacks are registered and active
        await self.hass.async_add_executor_job(self._client.query_initial_state)

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._entry_id}_media_player"

    @property
    def device_info(self):
        """Return device info."""
        info = {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._name,
            "manufacturer": "Hisense",
            "model": "VIDAA TV",
        }
        
        if self._mac:
            # HA explicitly requires lowercase MAC address formats separated by colons
            cleaned_mac = self._mac.replace("-", ":").lower()
            info["connections"] = {(CONNECTION_NETWORK_MAC, cleaned_mac)}
            
        return info

    @property
    def state(self):
        return self._state

    @property
    def volume_level(self):
        return self._volume / 100.0

    @property
    def is_volume_muted(self):
        return self._muted

    @property
    def source(self):
        return self._source

    @property
    def source_list(self):
        # Filter just the physical inputs (HDMI, TV, AV)
        sources = [
            s for s in self._source_dict.keys()
            if "hdmi" in s.lower() or s.lower() in ("tv", "av")
        ]
        return sorted(sources)

    @property
    def supported_features(self):
        return (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )

    def turn_on(self):
        # Send KEY_POWER via MQTT to wake/turn on the TV.
        # Since the TV's MQTT broker might be running in low power standby,
        # we always attempt to send the key.
        if self._client.connected:
            _LOGGER.debug("TV MQTT connected. Sending KEY_POWER to turn on")
            self._client.send_key("KEY_POWER")
        else:
            _LOGGER.debug("TV MQTT not connected. Attempting background token refresh and reconnect to send KEY_POWER")
            def reconnect_and_send():
                try:
                    # Try to refresh token and reconnect
                    self._client.check_and_refresh_token()
                    self._client.mqtt_client.username_pw_set(
                        username=self._client.username,
                        password=self._client.access_token
                    )
                    self._client.mqtt_client.reconnect()
                    # Wait up to 5 seconds for connection to succeed and then send the key
                    for _ in range(50):
                        if self._client.connected:
                            _LOGGER.debug("TV MQTT connected after reconnect. Sending KEY_POWER")
                            self._client.send_key("KEY_POWER")
                            break
                        time.sleep(0.1)
                except Exception as e:
                    _LOGGER.error(f"Failed to reconnect and send KEY_POWER: {e}")

            threading.Thread(target=reconnect_and_send, daemon=True).start()

        self._state = STATE_ON
        self.schedule_update_ha_state()

    def turn_off(self):
        self._client.send_key("KEY_POWER")
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    def set_volume_level(self, volume):
        self._client.set_volume(int(volume * 100))

    def volume_up(self):
        self._client.send_key("KEY_VOLUMEUP")

    def volume_down(self):
        self._client.send_key("KEY_VOLUMEDOWN")

    def mute_volume(self, mute):
        self._client.send_key("KEY_MUTE")

    def select_source(self, source):
        # Determine if it's an app
        app = self._app_dict.get(source)
        if app:
            self._client.launch_app(app["appId"], app["name"], app["url"])
            return

        # Input source
        src = self._source_dict.get(source)
        if src:
            self._client.change_source(src["sourceid"])

    def _handle_state_update(self, data):
        statetype = data.get("statetype")
        _LOGGER.debug(f"TV State updated: {statetype}")

        if statetype == "fake_sleep_0":
            self._state = STATE_OFF
        else:
            was_off = (self._state == STATE_OFF)
            self._state = STATE_ON
            if statetype == "sourceswitch":
                self._source = data.get("sourcename") or data.get("displayname")
            elif statetype == "app":
                self._source = data.get("name")
            elif statetype == "livetv":
                self._source = "TV"

            if was_off or not self._source_dict or not self._app_dict:
                self.hass.add_job(self._client.query_initial_state)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_volume_update(self, data):
        self._state = STATE_ON
        if data.get("volume_type") == 0:
            self._volume = data.get("volume_value", 0)
        elif data.get("volume_type") == 2:
            self._muted = (data.get("volume_value") == 1)

        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_sourcelist_update(self, data):
        if not data:
            return
        self._source_dict = {item.get("sourcename"): item for item in data if item.get("sourcename")}
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_applist_update(self, data):
        if not data:
            return
        self._app_list = data
        self._app_dict = {item.get("name"): item for item in data if item.get("name")}
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)

    def _handle_disconnected(self):
        self._state = STATE_OFF
        self.hass.loop.call_soon_threadsafe(self.schedule_update_ha_state)



async def async_setup_entry(hass, config_entry, async_add_entities):
    client = hass.data[DOMAIN][config_entry.entry_id]
    mac = config_entry.data.get(CONF_MAC_ADDRESS)

    entity = HisenseVidaaMediaPlayer(
        client=client,
        mac=mac,
        entry_id=config_entry.entry_id,
        name=config_entry.title
    )
    async_add_entities([entity])
