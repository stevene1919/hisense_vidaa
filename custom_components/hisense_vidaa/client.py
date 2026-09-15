"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import logging
import os
import socket
import ssl
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

try:
    from .crypto import generate_initial_credentials, resolve_ca_certificate, resolve_certificates
    from .discovery import (
        get_device_fingerprint as discover_device_fingerprint,
        get_tv_timestamp,
        ping_tv,
        probe_tv_auth_methods,
        test_tv_ssl_connection,
    )
    from .navigation import get_next_cycled_source, match_app, resolve_command_key, resolve_source
    from .settings import (
        DEFAULT_MENU_ID_BACKLIGHT,
        DEFAULT_MENU_ID_BRIGHTNESS,
        DEFAULT_MENU_ID_CONTRAST,
        DEFAULT_MENU_ID_PICTURE_MODE,
        DEFAULT_MENU_ID_SOUND_MODE,
        SettingMenuItem,
        find_menu_item_by_name,
        parse_settings_payload,
    )
except ImportError:
    from crypto import generate_initial_credentials, resolve_ca_certificate, resolve_certificates
    from discovery import (
        get_device_fingerprint as discover_device_fingerprint,
        get_tv_timestamp,
        ping_tv,
        probe_tv_auth_methods,
        test_tv_ssl_connection,
    )
    from navigation import get_next_cycled_source, match_app, resolve_command_key, resolve_source
    from settings import (
        DEFAULT_MENU_ID_BACKLIGHT,
        DEFAULT_MENU_ID_BRIGHTNESS,
        DEFAULT_MENU_ID_CONTRAST,
        DEFAULT_MENU_ID_PICTURE_MODE,
        DEFAULT_MENU_ID_SOUND_MODE,
        SettingMenuItem,
        find_menu_item_by_name,
        parse_settings_payload,
    )

_LOGGER = logging.getLogger(__name__)


class HisenseTvClient:
    """Client for connecting, authenticating, and controlling Hisense VIDAA TVs."""

    def __init__(
        self,
        ip: str,
        mac: str | None = None,
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        access_token_time: int = 0,
        access_token_duration: int = 0,
        refresh_token: str | None = None,
        refresh_token_time: int = 0,
        refresh_token_duration: int = 0,
        certfile: str | None = None,
        keyfile: str | None = None,
        ca_cert: str | None = None,
        auth_profile: str = "auto",
        use_ssl: bool = True,
        verify_ssl: bool = False,
    ) -> None:
        self.ip = ip
        self.mac = mac
        self.client_id = client_id
        self.username = username
        self.password = password
        self.access_token = access_token
        self.access_token_time = access_token_time
        self.access_token_duration = access_token_duration
        self.refresh_token = refresh_token
        self.refresh_token_time = refresh_token_time
        self.refresh_token_duration = refresh_token_duration
        self.auth_profile = (auth_profile or "auto").lower()
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl

        if self.use_ssl:
            self.certfile, self.keyfile = resolve_certificates(
                auth_profile=self.auth_profile,
                certfile=certfile,
                keyfile=keyfile,
            )
            self.ca_cert = resolve_ca_certificate(ca_cert)
        else:
            self.certfile, self.keyfile, self.ca_cert = None, None, None

        self.mqtt_client: mqtt.Client | None = None
        self.connected = False
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

        self._auth_future: asyncio.Future | None = None
        self._auth_code_future: asyncio.Future | None = None
        self._token_future: asyncio.Future | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._refreshing_token = False
        self._last_refresh_attempt = 0.0
        self._refresh_lock = threading.Lock()

        self.topicTVUIBasepath = ""
        self.topicTVPSBasepath = ""
        self.topicMobiBasepath = ""
        self.topicBrcsBasepath = "/remoteapp/mobile/broadcast/"
        self.topicRemoBasepath = ""

        self.sources: list[dict[str, Any]] = []
        self.apps: list[dict[str, Any]] = []
        self.current_source: str | None = None
        self.has_notifications: bool = False

        # Picture and Sound Settings state
        self.picture_settings: dict[int, SettingMenuItem] = {}
        self.sound_settings: dict[int, SettingMenuItem] = {}
        self.picture_mode: str | None = None
        self.backlight: int | None = None
        self.brightness: int | None = None
        self.contrast: int | None = None
        self.sound_mode: str | None = None

        if self.client_id:
            self.define_topic_paths()

    # --------------------------------------------------------------------------
    # Callback Registry & Dispatch
    # --------------------------------------------------------------------------
    def _register_callback(self, event: str, cb: Callable) -> None:
        if cb and cb not in self._callbacks[event]:
            self._callbacks[event].append(cb)

    def _unregister_callback(self, event: str, cb: Callable) -> None:
        if cb in self._callbacks[event]:
            self._callbacks[event].remove(cb)

    def _dispatch(self, event: str, *args: Any) -> None:
        for cb in list(self._callbacks[event]):
            try:
                cb(*args)
            except Exception as e:
                _LOGGER.error("Error in %s callback: %s", event, e)

    @property
    def on_state_update(self) -> Callable | None:
        cbs = self._callbacks["state"]
        return cbs[0] if cbs else None

    @on_state_update.setter
    def on_state_update(self, cb: Callable) -> None:
        self._register_callback("state", cb)

    @property
    def on_volume_update(self) -> Callable | None:
        cbs = self._callbacks["volume"]
        return cbs[0] if cbs else None

    @on_volume_update.setter
    def on_volume_update(self, cb: Callable) -> None:
        self._register_callback("volume", cb)

    @property
    def on_sourcelist_update(self) -> Callable | None:
        cbs = self._callbacks["sourcelist"]
        return cbs[0] if cbs else None

    @on_sourcelist_update.setter
    def on_sourcelist_update(self, cb: Callable) -> None:
        self._register_callback("sourcelist", cb)

    @property
    def on_applist_update(self) -> Callable | None:
        cbs = self._callbacks["applist"]
        return cbs[0] if cbs else None

    @on_applist_update.setter
    def on_applist_update(self, cb: Callable) -> None:
        self._register_callback("applist", cb)

    @property
    def on_disconnected_callback(self) -> Callable | None:
        cbs = self._callbacks["disconnected"]
        return cbs[0] if cbs else None

    @on_disconnected_callback.setter
    def on_disconnected_callback(self, cb: Callable) -> None:
        self._register_callback("disconnected", cb)

    @property
    def on_token_refreshed(self) -> Callable | None:
        cbs = self._callbacks["token_refreshed"]
        return cbs[0] if cbs else None

    @on_token_refreshed.setter
    def on_token_refreshed(self, cb: Callable) -> None:
        self._register_callback("token_refreshed", cb)

    def register_state_callback(self, cb: Callable) -> None:
        self._register_callback("state", cb)

    def unregister_state_callback(self, cb: Callable) -> None:
        self._unregister_callback("state", cb)

    def register_volume_callback(self, cb: Callable) -> None:
        self._register_callback("volume", cb)

    def unregister_volume_callback(self, cb: Callable) -> None:
        self._unregister_callback("volume", cb)

    def register_sourcelist_callback(self, cb: Callable) -> None:
        self._register_callback("sourcelist", cb)

    def unregister_sourcelist_callback(self, cb: Callable) -> None:
        self._unregister_callback("sourcelist", cb)

    def register_applist_callback(self, cb: Callable) -> None:
        self._register_callback("applist", cb)

    def unregister_applist_callback(self, cb: Callable) -> None:
        self._unregister_callback("applist", cb)

    def register_connected_callback(self, cb: Callable) -> None:
        self._register_callback("connected", cb)

    def unregister_connected_callback(self, cb: Callable) -> None:
        self._unregister_callback("connected", cb)

    def register_disconnected_callback(self, cb: Callable) -> None:
        self._register_callback("disconnected", cb)

    def unregister_disconnected_callback(self, cb: Callable) -> None:
        self._unregister_callback("disconnected", cb)

    def register_token_refreshed_callback(self, cb: Callable) -> None:
        self._register_callback("token_refreshed", cb)

    def unregister_token_refreshed_callback(self, cb: Callable) -> None:
        self._unregister_callback("token_refreshed", cb)

    def register_auth_failed_callback(self, cb: Callable) -> None:
        self._register_callback("auth_failed", cb)

    def unregister_auth_failed_callback(self, cb: Callable) -> None:
        self._unregister_callback("auth_failed", cb)

    def register_picture_callback(self, cb: Callable) -> None:
        self._register_callback("picture", cb)

    def unregister_picture_callback(self, cb: Callable) -> None:
        self._unregister_callback("picture", cb)

    def register_sound_callback(self, cb: Callable) -> None:
        self._register_callback("sound", cb)

    def unregister_sound_callback(self, cb: Callable) -> None:
        self._unregister_callback("sound", cb)

    def _dispatch_auth_failed(self) -> None:
        self._dispatch("auth_failed", self)

    def _dispatch_connected(self) -> None:
        self._dispatch("connected")

    def _dispatch_state_update(self, data: Any) -> None:
        if isinstance(data, dict):
            statetype = data.get("statetype")
            if statetype == "sourceswitch":
                self.current_source = data.get("sourcename") or data.get("displayname") or data.get("sourceid")
            elif statetype in ("livetv", "tv"):
                self.current_source = "TV"
            elif statetype == "app":
                self.current_source = data.get("name") or data.get("appId")
        self._dispatch("state", data)

    def _dispatch_volume_update(self, data: Any) -> None:
        self._dispatch("volume", data)

    def _dispatch_sourcelist_update(self, data: Any) -> None:
        if isinstance(data, list):
            self.sources = data
        self._dispatch("sourcelist", data)

    def _dispatch_applist_update(self, data: Any) -> None:
        if isinstance(data, list):
            self.apps = data
        self._dispatch("applist", data)

    def _dispatch_picture_update(self, data: Any) -> None:
        if isinstance(data, dict):
            if "menu_info" in data or "menu_list" in data or "items" in data:
                self.picture_settings = parse_settings_payload(data)
                pm_item = find_menu_item_by_name(self.picture_settings, "Picture Mode", DEFAULT_MENU_ID_PICTURE_MODE)
                if pm_item and pm_item.value:
                    self.picture_mode = str(pm_item.value)
                bl_item = find_menu_item_by_name(self.picture_settings, "Backlight", DEFAULT_MENU_ID_BACKLIGHT)
                if bl_item and bl_item.value is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        self.backlight = int(bl_item.value)
                br_item = find_menu_item_by_name(self.picture_settings, "Brightness", DEFAULT_MENU_ID_BRIGHTNESS)
                if br_item and br_item.value is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        self.brightness = int(br_item.value)
                ct_item = find_menu_item_by_name(self.picture_settings, "Contrast", DEFAULT_MENU_ID_CONTRAST)
                if ct_item and ct_item.value is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        self.contrast = int(ct_item.value)
            elif data.get("action") == "notify_value_changed":
                try:
                    menu_id = int(data.get("menu_id", 0))
                    menu_val = data.get("menu_value")
                    if menu_id in self.picture_settings:
                        self.picture_settings[menu_id].value = menu_val
                    if menu_id == DEFAULT_MENU_ID_PICTURE_MODE or "picture" in str(self.picture_settings.get(menu_id, "")).lower():
                        self.picture_mode = str(menu_val)
                    elif menu_id == DEFAULT_MENU_ID_BACKLIGHT or "backlight" in str(self.picture_settings.get(menu_id, "")).lower():
                        with contextlib.suppress(ValueError, TypeError):
                            self.backlight = int(menu_val)
                except Exception as e:
                    _LOGGER.debug("Error updating notify_value_changed for picture: %s", e)
        self._dispatch("picture", data)

    def _dispatch_sound_update(self, data: Any) -> None:
        if isinstance(data, dict):
            if "menu_info" in data or "menu_list" in data or "items" in data:
                self.sound_settings = parse_settings_payload(data)
                sm_item = find_menu_item_by_name(self.sound_settings, "Sound Mode", DEFAULT_MENU_ID_SOUND_MODE)
                if sm_item and sm_item.value:
                    self.sound_mode = str(sm_item.value)
            elif data.get("action") == "notify_value_changed":
                try:
                    menu_id = int(data.get("menu_id", 0))
                    menu_val = data.get("menu_value")
                    if menu_id in self.sound_settings:
                        self.sound_settings[menu_id].value = menu_val
                    if menu_id == DEFAULT_MENU_ID_SOUND_MODE or "sound" in str(self.sound_settings.get(menu_id, "")).lower():
                        self.sound_mode = str(menu_val)
                except Exception as e:
                    _LOGGER.debug("Error updating notify_value_changed for sound: %s", e)
        self._dispatch("sound", data)

    def _dispatch_disconnected(self) -> None:
        self.connected = False
        self._dispatch("disconnected")

    def _dispatch_token_refreshed(self) -> None:
        self._dispatch("token_refreshed", self)

    # --------------------------------------------------------------------------
    # Discovery, Fingerprinting & Network Wrappers
    # --------------------------------------------------------------------------
    def validate_certificates(self) -> None:
        """Verifies that the SSL certificate and private key files exist and are readable."""
        if not self.certfile or not os.path.isfile(self.certfile):
            raise FileNotFoundError(
                f"SSL Certificate file not found: '{self.certfile}'. "
                "Please place certificate files in '/config/ssl' or specify --cert."
            )
        if not self.keyfile or not os.path.isfile(self.keyfile):
            raise FileNotFoundError(
                f"SSL Private Key file not found: '{self.keyfile}'. "
                "Please place key files in '/config/ssl' or specify --key."
            )

    def test_ssl_connection(self, timeout: float = 5.0) -> dict[str, Any]:
        """Tests the raw TLS handshake with the TV on port 36669 without authenticating."""
        self.validate_certificates()
        return test_tv_ssl_connection(
            self.ip,
            self.certfile,
            self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            timeout=timeout,
        )

    def get_device_fingerprint(self, timeout: float = 2.0) -> dict[str, Any]:
        """Fetches UPnP, DLNA, and mDNS device metadata for model and capability identification."""
        return discover_device_fingerprint(self.ip, timeout=timeout)

    def probe_auth_methods(self, timeout: float = 2.0) -> dict[str, Any]:
        """Probes TV MQTT broker with various auth algorithms to diagnose compatibility."""
        return probe_tv_auth_methods(
            self.ip,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            mac=self.mac,
            timeout=timeout,
        )

    def ping(self, timeout: float = 3.0) -> dict[str, Any]:
        """Quickly tests if TV broker is listening, accepting TLS, and responding to MQTT packets."""
        return ping_tv(
            ip=self.ip,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            client_id=self.client_id,
            username=self.username,
            password=self.access_token,
            mac=self.mac,
            timeout=timeout,
        )

    # --------------------------------------------------------------------------
    # Topic Configuration & Credentials Generation
    # --------------------------------------------------------------------------
    def define_topic_paths(self) -> None:
        """Sets up topic paths for the specific client ID."""
        self.topicTVUIBasepath = f"/remoteapp/tv/ui_service/{self.client_id}/"
        self.topicTVPSBasepath = f"/remoteapp/tv/platform_service/{self.client_id}/"
        self.topicMobiBasepath = f"/remoteapp/mobile/{self.client_id}/"
        self.topicRemoBasepath = f"/remoteapp/tv/remote_service/{self.client_id}/"

    def generate_initial_creds(
        self, use_new_auth: bool | None = None, timestamp: int | None = None
    ) -> None:
        """Generates initial dynamic credentials for challenge-response pairing."""
        if timestamp is None and self.ip:
            timestamp = get_tv_timestamp(self.ip, timeout=1.5)
        self.client_id, self.username, self.password = generate_initial_credentials(
            mac=self.mac,
            timestamp=timestamp,
            auth_profile=self.auth_profile,
            use_new_auth=use_new_auth,
        )
        self.define_topic_paths()
        _LOGGER.debug(
            "Generated initial creds (profile=%s, use_new_auth=%s, ts=%s) - Client ID: %s, Username: %s",
            self.auth_profile,
            use_new_auth,
            timestamp,
            self.client_id,
            self.username,
        )

    # --------------------------------------------------------------------------
    # MQTT Setup & Message Handlers
    # --------------------------------------------------------------------------
    def _apply_tls(self, client: mqtt.Client) -> None:
        """Applies TLS certificate configuration to an MQTT client instance."""
        if not self.use_ssl or not self.certfile or not self.keyfile:
            return

        if self.verify_ssl and self.ca_cert and os.path.isfile(self.ca_cert):
            client.tls_set(
                ca_certs=self.ca_cert,
                certfile=self.certfile,
                keyfile=self.keyfile,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS,
            )
            client.tls_insecure_set(True)
        else:
            client.tls_set(
                ca_certs=None,
                certfile=self.certfile,
                keyfile=self.keyfile,
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLS,
            )
            client.tls_insecure_set(True)

    def create_mqtt_client(self, client_id: str, username: str, password: str) -> mqtt.Client:
        """Creates and configures an authenticated MQTT client."""
        client = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        client.reconnect_delay_set(min_delay=2, max_delay=30)
        self._apply_tls(client)
        client.username_pw_set(username=username, password=password)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _safe_set_future_result(self, future: asyncio.Future | None, result: Any) -> None:
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_result, result)
            else:
                future.set_result(result)

    def _safe_set_future_exception(self, future: asyncio.Future | None, exc: Exception) -> None:
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_exception, exc)
            else:
                future.set_exception(exc)

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to TV MQTT Broker")
            self._dispatch_connected()
            if hasattr(self, "topicBrcsBasepath"):
                client.subscribe([
                    (self.topicBrcsBasepath + "ui_service/state", 0),
                    (self.topicBrcsBasepath + "platform_service/actions/volumechange", 0),
                    (self.topicBrcsBasepath + "ui_service/volume", 0),
                    (self.topicBrcsBasepath + "platform_service/actions/tvsleep", 0),
                    (self.topicBrcsBasepath + "ui_service/data/hotelmodechange", 0),
                    (self.topicMobiBasepath + "ui_service/data/sourcelist", 0),
                    (self.topicMobiBasepath + "ui_service/data/applist", 0),
                    (self.topicMobiBasepath + "ui_service/data/gettvstate", 0),
                    (self.topicMobiBasepath + "ui_service/data/state", 0),
                    (self.topicMobiBasepath + "platform_service/data/getvolume", 0),
                    (self.topicMobiBasepath + "platform_service/data/gettvinfo", 0),
                    (self.topicMobiBasepath + "platform_service/data/getdeviceinfo", 0),
                    (self.topicMobiBasepath + "ui_service/data/capability", 0),
                    (self.topicMobiBasepath + "platform_service/data/picturesetting", 0),
                    (self.topicBrcsBasepath + "platform_service/data/picturesetting", 0),
                    (self.topicMobiBasepath + "platform_service/data/soundsetting", 0),
                    (self.topicBrcsBasepath + "platform_service/data/soundsetting", 0),
                ])
                threading.Timer(0.5, self.query_initial_state).start()
        else:
            self.connected = False
            _LOGGER.error("Failed to connect to TV MQTT Broker, rc: %d", rc)
            if self._auth_future and not self._auth_future.done():
                self._safe_set_future_exception(
                    self._auth_future,
                    Exception(f"MQTT connection rejected with code {rc} (Not authorized / invalid credentials)"),
                )
                return

            if rc in (4, 5):
                # Immediately halt paho-mqtt auto-reconnect loop to avoid flapping/broker storm
                with contextlib.suppress(Exception):
                    client.loop_stop()

                if self.refresh_token:
                    current_time = time.time()
                    with self._refresh_lock:
                        should_refresh = not self._refreshing_token and (current_time - self._last_refresh_attempt > 15)
                    if should_refresh:
                        _LOGGER.info("Authentication failed on connect. Refreshing token in background...")
                        threading.Thread(target=self._refresh_token_and_update_creds, daemon=True).start()
                    else:
                        self._dispatch_auth_failed()
                else:
                    self._dispatch_auth_failed()

    def _refresh_token_and_update_creds(self) -> None:
        with self._refresh_lock:
            if self._refreshing_token or not self.refresh_token:
                return
            self._refreshing_token = True
            self._last_refresh_attempt = time.time()

        try:
            if self.check_and_refresh_token(force=True):
                _LOGGER.info("Token successfully refreshed on connection failure. Updating client credentials.")
                if self.mqtt_client:
                    self.mqtt_client.username_pw_set(username=self.username, password=self.access_token)
                    self.mqtt_client.reconnect()
                    with contextlib.suppress(Exception):
                        self.mqtt_client.loop_start()
            else:
                _LOGGER.warning("Token refresh failed (token expired on TV). Stopping auto-reconnect.")
                self._dispatch_auth_failed()
        except Exception as e:
            _LOGGER.error("Error during background token refresh: %s", e)
            self._dispatch_auth_failed()
        finally:
            with self._refresh_lock:
                self._refreshing_token = False

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self.connected = False
        _LOGGER.info("Disconnected from TV MQTT Broker, rc: %d", rc)
        self._dispatch_disconnected()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="ignore")
        _LOGGER.debug("Message received: %s on topic %s", payload, topic)

        # Check authentication futures
        if self._auth_future and topic in (
            self.topicMobiBasepath + "ui_service/data/authentication",
            self.topicMobiBasepath + "ui_service/data/vidaa_app_connect",
        ):
            self._safe_set_future_result(self._auth_future, payload)
        elif self._auth_code_future and topic == self.topicMobiBasepath + "ui_service/data/authenticationcode":
            self._safe_set_future_result(self._auth_code_future, payload)
        elif self._token_future and topic in (
            self.topicMobiBasepath + "platform_service/data/tokenissuance",
            self.topicMobiBasepath + "platform_service/data/gettoken",
        ):
            self._safe_set_future_result(self._token_future, payload)

        # Handle state push callbacks
        if topic in (
            self.topicBrcsBasepath + "ui_service/state",
            self.topicMobiBasepath + "ui_service/data/gettvstate",
            self.topicMobiBasepath + "ui_service/data/state",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_state_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing state: %s", e)
        elif topic in (
            self.topicBrcsBasepath + "platform_service/actions/volumechange",
            self.topicBrcsBasepath + "ui_service/volume",
            self.topicMobiBasepath + "platform_service/data/getvolume",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_volume_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing volume: %s", e)
        elif topic == self.topicBrcsBasepath + "platform_service/actions/tvsleep":
            self._dispatch_state_update({"statetype": "fake_sleep_0"})
        elif topic == self.topicMobiBasepath + "ui_service/data/sourcelist":
            try:
                data = json.loads(payload)
                self._dispatch_sourcelist_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing sourcelist: %s", e)
        elif topic == self.topicMobiBasepath + "ui_service/data/applist":
            try:
                data = json.loads(payload)
                self._dispatch_applist_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing applist: %s", e)
        elif topic in (
            self.topicMobiBasepath + "platform_service/data/picturesetting",
            self.topicBrcsBasepath + "platform_service/data/picturesetting",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_picture_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing picturesetting: %s", e)
        elif topic in (
            self.topicMobiBasepath + "platform_service/data/soundsetting",
            self.topicBrcsBasepath + "platform_service/data/soundsetting",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_sound_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing soundsetting: %s", e)
        elif topic == self.topicMobiBasepath + "ui_service/data/capability":
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    caps = str(data).lower()
                    if "notify" in caps or "toast" in caps or "showmessage" in caps or "message" in caps:
                        self.has_notifications = True
                        _LOGGER.info("TV reported support for on-screen notifications: %s", data)
            except Exception as e:
                _LOGGER.debug("Error parsing capability descriptor: %s", e)

    # --------------------------------------------------------------------------
    # Authentication & Pairing Handshake
    # --------------------------------------------------------------------------
    async def async_start_auth(self) -> None:
        """Starts the authentication handshake and triggers the TV to show PIN."""
        if self.auth_profile == "legacy":
            self.client_id = "hisenseservice"
            self.username = "hisenseservice"
            self.password = "multimqttservice"
            self.access_token = "multimqttservice"
            self.define_topic_paths()
            return

        if self.auth_profile in ("modern", "vidaa_2024", "vidaa"):
            await self._async_start_auth_internal(use_new_auth=True)
        elif self.auth_profile in ("remotenow", "remotenow_2018", "standard"):
            await self._async_start_auth_internal(use_new_auth=False)
        else:  # auto
            try:
                await self._async_start_auth_internal(use_new_auth=False)
            except Exception as e:
                err_msg = str(e)
                if "code 5" in err_msg or "code 4" in err_msg or "Not authorized" in err_msg:
                    _LOGGER.info("Standard auth failed (%s), auto-falling back to modern VIDAA auth...", err_msg)
                    await self._async_start_auth_internal(use_new_auth=True)
                else:
                    raise

    async def _async_start_auth_internal(self, use_new_auth: bool = False) -> None:
        loop = asyncio.get_running_loop()
        self._loop = loop
        self.disconnect()
        await asyncio.sleep(0.2)
        tv_ts = await loop.run_in_executor(None, get_tv_timestamp, self.ip, 1.5)
        self.generate_initial_creds(use_new_auth=use_new_auth, timestamp=tv_ts)
        self.mqtt_client = await loop.run_in_executor(
            None, self.create_mqtt_client, self.client_id, self.username, self.password
        )

        self._auth_future = loop.create_future()
        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

        # Wait up to 10 seconds for connection
        for _ in range(50):
            if self.connected:
                break
            if self._auth_future.done() and self._auth_future.exception():
                self.disconnect()
                raise self._auth_future.exception()
            await asyncio.sleep(0.2)

        if not self.connected:
            self.disconnect()
            raise Exception("Cannot connect to TV MQTT Broker (connection timeout)")

        self.mqtt_client.subscribe([
            (self.topicTVUIBasepath + "actions/vidaa_app_connect", 0),
            (self.topicMobiBasepath + "ui_service/data/authentication", 0),
            (self.topicMobiBasepath + "ui_service/data/authenticationcode", 0),
            (self.topicMobiBasepath + "ui_service/data/vidaa_app_connect", 0),
            (self.topicMobiBasepath + "platform_service/data/tokenissuance", 0),
        ])

        # Allow broker time to register subscriptions before publishing
        await asyncio.sleep(0.5)

        for attempt in range(3):
            self.mqtt_client.publish(
                self.topicTVUIBasepath + "actions/vidaa_app_connect",
                '{"app_version":2,"connect_result":0,"device_type":"Mobile App"}',
            )
            try:
                await asyncio.wait_for(asyncio.shield(self._auth_future), timeout=4.0)
                break
            except TimeoutError:
                if attempt < 2 and not self._auth_future.done():
                    _LOGGER.debug("No response to vidaa_app_connect on attempt %d, retrying...", attempt + 1)
                    await asyncio.sleep(0.5)
                else:
                    self.disconnect()
                    raise Exception("TV authentication request timed out (TV did not show PIN)")
        self._auth_future = None

    async def async_submit_pin(self, pin_code: str) -> dict[str, Any]:
        """Submits the PIN code entered by the user and retrieves token pair."""
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._auth_code_future = loop.create_future()

        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")

        self.mqtt_client.publish(
            self.topicTVUIBasepath + "actions/authenticationcode",
            json.dumps({"authNum": int(pin_code)}),
        )

        try:
            payload_str = await asyncio.wait_for(self._auth_code_future, timeout=15)
            _LOGGER.debug("Received PIN response payload: %s", payload_str)
            payload = json.loads(payload_str)
            if payload.get("result") != 1:
                _LOGGER.error("PIN validation rejected with payload: %s", payload_str)
                raise Exception(f"Incorrect PIN code (TV response: {payload_str})")
        except TimeoutError:
            raise Exception("Timeout waiting for PIN validation")
        finally:
            self._auth_code_future = None

        self._token_future = loop.create_future()
        self.mqtt_client.publish(self.topicTVPSBasepath + "data/gettoken", '{"refreshtoken": ""}')
        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/authenticationcodeclose")

        try:
            token_payload_str = await asyncio.wait_for(self._token_future, timeout=15)
            token_data = json.loads(token_payload_str)

            self.access_token = token_data["accesstoken"]
            self.access_token_time = int(token_data["accesstoken_time"])
            self.access_token_duration = int(token_data["accesstoken_duration_day"])
            self.refresh_token = token_data["refreshtoken"]
            self.refresh_token_time = int(token_data["refreshtoken_time"])
            self.refresh_token_duration = int(token_data["refreshtoken_duration_day"])

            _LOGGER.info(
                "Pairing successful! Received access_token (valid %d days) and refresh_token (valid %d days)",
                self.access_token_duration,
                self.refresh_token_duration,
            )
            return token_data
        except TimeoutError:
            raise Exception("Timeout waiting for token issuance from TV")
        finally:
            self._token_future = None

    def check_and_refresh_token(self, force: bool = False) -> bool:
        """Checks access token expiration and triggers refresh via refresh token if necessary."""
        if not self.refresh_token:
            return False

        now = int(time.time())
        token_expiration = self.access_token_time + (self.access_token_duration * 86400)
        time_remaining = token_expiration - now

        if force or (self.access_token and time_remaining < 43200) or not self.access_token:
            _LOGGER.info("Access token expired or expiring soon (remaining: %ds). Refreshing...", time_remaining)
            return self.refresh_tokens()

        return False

    def refresh_tokens(self) -> bool:
        """Connects with the refresh token to obtain a fresh access token."""
        if not self.refresh_token or not self.client_id or not self.username:
            _LOGGER.warning("Cannot refresh token: missing refresh_token, client_id, or username")
            return False

        was_connected = self.connected
        main_client = self.mqtt_client
        if main_client:
            try:
                main_client.loop_stop()
                main_client.disconnect()
            except Exception:
                pass
            self.mqtt_client = None
            self.connected = False

        client = mqtt.Client(client_id=self.client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        self._apply_tls(client)
        client.username_pw_set(username=self.username, password=self.refresh_token)

        lock = threading.Event()
        updated_data: dict[str, Any] = {}
        connect_rc = [None]

        def on_refresh_connect(cl, userdata, flags, rc):
            connect_rc[0] = rc
            if rc == 0:
                _LOGGER.info("Refresh client connected successfully. Subscribing to token topics...")
                cl.subscribe(self.topicMobiBasepath + "#")
                payload = json.dumps({"refreshtoken": self.refresh_token or ""})
                cl.publish(self.topicTVPSBasepath + "data/gettoken", payload)
            else:
                _LOGGER.error("Refresh client connection failed, rc: %d", rc)
                lock.set()

        def on_refresh_subscribe(cl, userdata, mid, granted_qos):
            payload = json.dumps({"refreshtoken": self.refresh_token or ""})
            cl.publish(self.topicTVPSBasepath + "data/gettoken", payload)

        def on_token_msg(cl, userdata, msg):
            nonlocal updated_data
            try:
                payload_str = msg.payload.decode("utf-8", errors="ignore")
                _LOGGER.debug("Refresh client received message on %s: %s", msg.topic, payload_str)
                data = json.loads(payload_str)
                if isinstance(data, dict) and "accesstoken" in data:
                    updated_data = data
                    lock.set()
            except Exception as e:
                _LOGGER.error("Error parsing refreshed token: %s", e)

        client.on_connect = on_refresh_connect
        client.on_subscribe = on_refresh_subscribe
        client.on_message = on_token_msg
        client.on_disconnect = lambda cl, userdata, rc: _LOGGER.debug("Refresh client disconnected: %d", rc)

        try:
            client.connect(self.ip, 36669, 60)
            client.loop_start()

            start = time.time()
            while not lock.is_set() and time.time() - start < 10:
                time.sleep(0.1)
        except (OSError, TimeoutError) as e:
            _LOGGER.debug("TV is offline or unreachable during token refresh: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error during refresh client connection: %s", e)
        finally:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass

        if updated_data:
            self.access_token = updated_data["accesstoken"]
            self.access_token_time = int(updated_data.get("accesstoken_time", int(time.time())))
            self.access_token_duration = int(updated_data.get("accesstoken_duration_day", 2))
            self.refresh_token = updated_data.get("refreshtoken", self.refresh_token)
            self.refresh_token_time = int(updated_data.get("refreshtoken_time", int(time.time())))
            self.refresh_token_duration = int(updated_data.get("refreshtoken_duration_day") or updated_data.get("refresh_token_duration_day", 30))
            self._dispatch_token_refreshed()
            if was_connected or main_client:
                self.connect_and_run()
            return True

        if connect_rc[0] is not None:
            _LOGGER.error("Failed to refresh token. Connect RC: %d", connect_rc[0])

        if was_connected or main_client:
            self.connect_and_run()
        return False

    # --------------------------------------------------------------------------
    # Main Runtime Connection Loop
    # --------------------------------------------------------------------------
    def connect_and_run(self) -> None:
        """Main client connection loop using the access token as password."""
        if not self.access_token or not self.client_id or not self.username:
            _LOGGER.error("Cannot connect to TV: missing credentials (client_id, username, or access_token)")
            return

        self.mqtt_client = self.create_mqtt_client(self.client_id, self.username, self.access_token)
        _LOGGER.info("Starting background MQTT connection loop to TV at %s", self.ip)
        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

    def query_initial_state(self) -> None:
        """Queries initial state, volume, source list, app list, and settings from TV."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/gettvstate", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/getvolume", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/sourcelist", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/applist", "")
            time.sleep(0.1)
            self.get_picture_settings()
            time.sleep(0.1)
            self.get_sound_settings()

    # --------------------------------------------------------------------------
    # TV Commands, Navigation, Settings & Controls
    # --------------------------------------------------------------------------
    @staticmethod
    def send_wake_on_lan(
        mac: str | list[str] | tuple[str, ...],
        broadcast_ip: str | None = None,
        port: int = 9,
        ip: str | None = None,
    ) -> bool:
        """Sends standard Wake-on-LAN magic packet UDP broadcasts for one or multiple MACs."""
        if not mac:
            return False

        mac_list = [mac] if isinstance(mac, str) else list(mac)
        success = False

        for single_mac in mac_list:
            if not single_mac or not isinstance(single_mac, str):
                continue
            cleaned_mac = single_mac.replace(":", "").replace("-", "").replace(".", "").strip()
            if len(cleaned_mac) != 12:
                continue
            try:
                mac_bytes = bytes.fromhex(cleaned_mac)
                magic_packet = b"\xff" * 6 + mac_bytes * 16

                broadcast_targets = set()
                if broadcast_ip:
                    broadcast_targets.add(broadcast_ip)
                else:
                    broadcast_targets.add("255.255.255.255")
                    if ip:
                        try:
                            ip_obj = ipaddress.ip_address(ip)
                            if isinstance(ip_obj, ipaddress.IPv4Address):
                                subnet_broadcast = f"{ip.rsplit('.', 1)[0]}.255"
                                broadcast_targets.add(subnet_broadcast)
                        except ValueError:
                            pass

                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    for target in broadcast_targets:
                        for p in (port, 7 if port == 9 else port):
                            try:
                                sock.sendto(magic_packet, (target, p))
                            except Exception as target_err:
                                _LOGGER.debug("WoL target %s:%s send error: %s", target, p, target_err)

                _LOGGER.debug("Sent Wake-on-LAN magic packet to %s (targets: %s)", single_mac, broadcast_targets)
                success = True
            except Exception as e:
                _LOGGER.warning("Failed to send Wake-on-LAN packet to %s: %s", single_mac, e)

        return success

    def show_message(self, message: str, title: str | None = None, duration: int = 5) -> bool:
        """Displays an on-screen toast popup notification on the TV."""
        if not self.connected or not self.mqtt_client:
            _LOGGER.debug("Cannot show toast message: TV MQTT client not connected")
            return False

        payload_dict = {
            "message": message,
            "title": title or "",
            "duration": duration,
            "type": "notify",
        }
        payload = json.dumps(payload_dict)
        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/showmessage", payload)
        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/toast", payload)
        return True

    def send_key(self, key: str) -> None:
        """Publishes a raw keypress event to the TV."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(self.topicRemoBasepath + "actions/sendkey", key)

    def send_command(self, command: str) -> bool:
        """Sends a key command to the TV, automatically resolving known key aliases."""
        if not command:
            return False
        cmd_clean = command.strip().lower()
        if cmd_clean.startswith("app:"):
            app_target = command.split(":", 1)[1].strip()
            return self._launch_app_by_name(app_target)
        if cmd_clean.startswith("source:"):
            src_target = command.split(":", 1)[1].strip()
            return self._change_source_by_name_or_id(src_target)
        if cmd_clean in (
            "input",
            "source",
            "cycle_source",
            "input_cycle",
            "source_cycle",
            "key_input",
            "key_source",
        ):
            return self.cycle_source()
        if cmd_clean in ("input_menu", "source_menu", "key_input_menu", "key_source_menu"):
            self.send_key("KEY_MENU")
            return True

        key_to_send = resolve_command_key(command)
        self.send_key(key_to_send)
        return True

    def cycle_source(self) -> bool:
        """Cycles to the next available input source."""
        next_source = get_next_cycled_source(self.sources, self.current_source)
        if not next_source:
            self.send_key("KEY_MENU")
            return True

        sid, sname = next_source
        self.change_source(sid, sname)
        return True

    def _launch_app_by_name(self, name_or_id: str) -> bool:
        """Launches an app by name or app ID from cached applist."""
        matched = match_app(self.apps, name_or_id)
        if matched:
            self.launch_app(matched["appId"], matched["name"], matched["url"])
            return True

        target_clean = name_or_id.strip().lower()
        if target_clean in ("netflix", "app_netflix"):
            self.send_key("KEY_NETFLIX")
            return True
        if target_clean in ("youtube", "app_youtube"):
            self.send_key("KEY_YOUTUBE")
            return True
        if target_clean in ("prime", "prime video", "app_prime"):
            self.send_key("KEY_PRIME")
            return True

        return False

    def _change_source_by_name_or_id(self, target: str) -> bool:
        """Switches to source by name (e.g. HDMI1, TV) or numeric sourceid."""
        sid, sname = resolve_source(self.sources, target)
        self.change_source(sid or target.strip(), sname)
        return True

    def set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100)."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/changevolume", str(volume))

    def change_source(self, source_id: str, source_name: str | None = None) -> None:
        """Switches the active input source on the TV."""
        if not self.connected or not self.mqtt_client:
            return

        sid = str(source_id)
        sname = source_name

        payload_dict: dict[str, Any] = {}
        if sid:
            payload_dict["sourceid"] = sid
        if sname:
            payload_dict["sourcename"] = sname
        if not payload_dict:
            payload_dict = {"sourceid": source_id}

        payload = json.dumps(payload_dict)
        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/changesource", payload)

        # Dual publish for newer VIDAA firmware expecting source name
        if sname and sid != sname and str(sid).isdigit():
            payload_modern = json.dumps({"sourceid": sname, "sourcename": sname})
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/changesource", payload_modern)

        if str(sid).upper() == "TV" or (sname and str(sname).upper() == "TV") or str(source_id).lower() == "tv":
            self.send_key("KEY_LIVETV")

    def launch_app(self, app_id: str, app_name: str, url: str) -> None:
        """Launches an installed Smart TV application."""
        if self.connected and self.mqtt_client:
            payload = json.dumps({"appId": app_id, "name": app_name, "url": url})
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/launchapp", payload)

    # --------------------------------------------------------------------------
    # Picture & Sound Settings Controls (Issue #20 & Beyond)
    # --------------------------------------------------------------------------
    def get_picture_settings(self) -> None:
        """Requests current picture settings menu information from the TV."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(
                self.topicTVPSBasepath + "actions/picturesetting",
                json.dumps({"action": "get_menu_info"}),
            )

    def set_picture_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific picture setting value."""
        if self.connected and self.mqtt_client:
            payload = json.dumps({
                "action": "notify_value_changed",
                "menu_id": int(menu_id),
                "menu_value": str(menu_value),
            })
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/picturesetting", payload)
            if int(menu_id) in self.picture_settings:
                self.picture_settings[int(menu_id)].value = menu_value

    def set_picture_mode(self, mode: str) -> None:
        """Sets the TV picture mode preset."""
        pm_item = find_menu_item_by_name(self.picture_settings, "Picture Mode", DEFAULT_MENU_ID_PICTURE_MODE)
        menu_id = pm_item.menu_id if pm_item else DEFAULT_MENU_ID_PICTURE_MODE
        self.set_picture_setting(menu_id, mode)
        self.picture_mode = mode

    def set_backlight(self, level: int) -> None:
        """Sets the TV backlight level (0–100)."""
        bl_item = find_menu_item_by_name(self.picture_settings, "Backlight", DEFAULT_MENU_ID_BACKLIGHT)
        menu_id = bl_item.menu_id if bl_item else DEFAULT_MENU_ID_BACKLIGHT
        clamped = max(0, min(100, int(level)))
        self.set_picture_setting(menu_id, clamped)
        self.backlight = clamped

    def set_brightness(self, level: int) -> None:
        """Sets the TV brightness level (0–100)."""
        br_item = find_menu_item_by_name(self.picture_settings, "Brightness", DEFAULT_MENU_ID_BRIGHTNESS)
        menu_id = br_item.menu_id if br_item else DEFAULT_MENU_ID_BRIGHTNESS
        clamped = max(0, min(100, int(level)))
        self.set_picture_setting(menu_id, clamped)
        self.brightness = clamped

    def set_contrast(self, level: int) -> None:
        """Sets the TV contrast level (0–100)."""
        ct_item = find_menu_item_by_name(self.picture_settings, "Contrast", DEFAULT_MENU_ID_CONTRAST)
        menu_id = ct_item.menu_id if ct_item else DEFAULT_MENU_ID_CONTRAST
        clamped = max(0, min(100, int(level)))
        self.set_picture_setting(menu_id, clamped)
        self.contrast = clamped

    def get_sound_settings(self) -> None:
        """Requests current sound settings menu information from the TV."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(
                self.topicTVPSBasepath + "actions/soundsetting",
                json.dumps({"action": "get_menu_info"}),
            )

    def set_sound_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific sound setting value."""
        if self.connected and self.mqtt_client:
            payload = json.dumps({
                "action": "notify_value_changed",
                "menu_id": int(menu_id),
                "menu_value": str(menu_value),
            })
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/soundsetting", payload)
            if int(menu_id) in self.sound_settings:
                self.sound_settings[int(menu_id)].value = menu_value

    def set_sound_mode(self, mode: str) -> None:
        """Sets the TV sound mode preset."""
        sm_item = find_menu_item_by_name(self.sound_settings, "Sound Mode", DEFAULT_MENU_ID_SOUND_MODE)
        menu_id = sm_item.menu_id if sm_item else DEFAULT_MENU_ID_SOUND_MODE
        self.set_sound_setting(menu_id, mode)
        self.sound_mode = mode

    def send_text_input(self, text: str, action: str = "insert") -> None:
        """Sends virtual keyboard string input to active on-screen input/search field."""
        if self.connected and self.mqtt_client:
            payload = json.dumps({"text": text, "action": action})
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/txtinputdata", payload)
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/bwsinputdata", payload)

    # --------------------------------------------------------------------------
    # Async Queries & Disconnect
    # --------------------------------------------------------------------------
    async def async_query(self, pub_topic: str, sub_topic: str, payload: str | None = None) -> Any:
        """Publishes a query to the TV and asynchronously awaits the response topic."""
        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def on_msg(client, userdata, msg):
            loop.call_soon_threadsafe(future.set_result, msg.payload.decode("utf-8"))

        self.mqtt_client.message_callback_add(sub_topic, on_msg)
        self.mqtt_client.subscribe(sub_topic)
        self.mqtt_client.publish(pub_topic, payload)

        try:
            result = await asyncio.wait_for(future, timeout=10)
            return json.loads(result)
        except Exception as e:
            _LOGGER.error("Error querying %s: %s", pub_topic, e)
            raise e
        finally:
            self.mqtt_client.unsubscribe(sub_topic)
            self.mqtt_client.message_callback_remove(sub_topic)

    def disconnect(self) -> None:
        """Cleanly disconnects the MQTT client and stops the background network thread."""
        if self.mqtt_client:
            try:
                self.mqtt_client.on_connect = None
                self.mqtt_client.on_disconnect = None
                self.mqtt_client.on_message = None
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                _LOGGER.debug("Error during client disconnect: %s", e)
            finally:
                self.mqtt_client = None
                self.connected = False
