import logging
import json
from wakeonlan import send_magic_packet
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    BrowseMedia
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

        # Register client push callbacks
        self._client.on_state_update = self._handle_state_update
        self._client.on_volume_update = self._handle_volume_update
        self._client.on_sourcelist_update = self._handle_sourcelist_update
        self._client.on_applist_update = self._handle_applist_update
        self._client.on_disconnected_callback = self._handle_disconnected

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
        # Merge input sources and apps for the source dropdown
        sources = list(self._source_dict.keys())
        apps = [app["name"] for app in self._app_list]
        return sorted(sources + apps)

    @property
    def supported_features(self):
        return (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )

    def turn_on(self):
        if self._mac:
            send_magic_packet(self._mac)
            self._state = STATE_ON
            self.schedule_update_ha_state()
        else:
            _LOGGER.warning("Cannot turn on without MAC address")

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
            self._state = STATE_ON
            if statetype == "sourceswitch":
                self._source = data.get("sourcename") or data.get("displayname")
            elif statetype == "app":
                self._source = data.get("name")
            elif statetype == "livetv":
                self._source = "TV"

        self.schedule_update_ha_state()

    def _handle_volume_update(self, data):
        self._state = STATE_ON
        if data.get("volume_type") == 0:
            self._volume = data.get("volume_value", 0)
        elif data.get("volume_type") == 2:
            self._muted = (data.get("volume_value") == 1)

        self.schedule_update_ha_state()

    def _handle_sourcelist_update(self, data):
        if not data:
            return
        self._source_dict = {item.get("sourcename"): item for item in data if item.get("sourcename")}
        self.schedule_update_ha_state()

    def _handle_applist_update(self, data):
        if not data:
            return
        self._app_list = data
        self._app_dict = {item.get("name"): item for item in data if item.get("name")}
        self.schedule_update_ha_state()

    def _handle_disconnected(self):
        self._state = STATE_OFF
        self.schedule_update_ha_state()

    # Browser Media Support
    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        """Implement the websocket media browsing helper."""
        if media_content_id in [None, "library"]:
            return await self._build_library_node()
        if media_content_id == "app_list":
            return await self._build_app_list_node()
        return None

    async def _build_library_node(self):
        node = BrowseMedia(
            title="Media Library",
            media_class="directory",
            media_content_type="library",
            media_content_id="library",
            can_play=False,
            can_expand=True,
            children=[],
        )

        try:
            # Query channel list info dynamically using direct connection query
            pub = self._client.topicTVPSBasepath + "actions/getchannellistinfo"
            sub = self._client.topicMobiBasepath + "platform_service/data/getchannellistinfo"
            payload = await self._client.async_query(pub, sub)

            self._channel_infos = {item.get("list_para"): item for item in payload if item.get("list_para")}
            for key, item in self._channel_infos.items():
                node.children.append(
                    BrowseMedia(
                        title=item.get("list_name"),
                        media_class="directory",
                        media_content_type="channellistinfo",
                        media_content_id=key,
                        can_play=False,
                        can_expand=True,
                    )
                )
        except Exception as e:
            _LOGGER.debug(f"Failed to fetch channel list info: {e}")

        node.children.append(
            BrowseMedia(
                title="Applications",
                media_class="app",
                media_content_type="apps",
                media_content_id="app_list",
                can_play=False,
                can_expand=True,
            )
        )
        return node

    async def _build_app_list_node(self):
        node = BrowseMedia(
            title="Applications",
            media_class="app",
            media_content_type="apps",
            media_content_id="app_list",
            can_play=False,
            can_expand=True,
            children=[],
        )

        try:
            pub = self._client.topicTVUIBasepath + "actions/applist"
            sub = self._client.topicMobiBasepath + "ui_service/data/applist"
            payload = await self._client.async_query(pub, sub)

            self._app_list = payload
            self._app_dict = {item.get("name"): item for item in payload if item.get("name")}
            for item in payload:
                node.children.append(
                    BrowseMedia(
                        title=item.get("name"),
                        media_class="app",
                        media_content_type="app",
                        media_content_id=item.get("appId"),
                        can_play=True,
                        can_expand=False,
                    )
                )
        except Exception as e:
            _LOGGER.debug(f"Failed to fetch apps: {e}")

        return node

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        if media_type == "channel":
            payload = json.dumps({"channel_param": media_id})
            self._client.mqtt_client.publish(
                self._client.topicTVUIBasepath + "actions/changechannel", payload
            )
        elif media_type == "app":
            # Search in app list
            app = None
            for item in self._app_list:
                if item.get("appId") == media_id:
                    app = item
                    break
            if app:
                self._client.launch_app(app["appId"], app["name"], app["url"])

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
