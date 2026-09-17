"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
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
    )
    from .protocol.auth import (
        apply_mqtt_tls,
        is_token_expired,
        perform_token_refresh,
        probe_tv_auth_methods,
        test_tv_ssl_connection,
    )
    from .protocol.pairing import async_start_pairing_handshake, async_submit_pin_code
    from .protocol.topics import TOPIC_BROADCAST_BASEPATH, build_topic_paths
    from .protocol.wol import send_wake_on_lan
    from .tv.actions import (
        change_source as act_change_source,
        change_source_by_name_or_id as act_change_source_by_name_or_id,
        cycle_source as act_cycle_source,
        get_picture_settings as act_get_picture_settings,
        get_sound_settings as act_get_sound_settings,
        launch_app as act_launch_app,
        launch_app_by_name as act_launch_app_by_name,
        query_initial_state as act_query_initial_state,
        send_command as act_send_command,
        send_key as act_send_key,
        send_text_input as act_send_text_input,
        set_backlight as act_set_backlight,
        set_brightness as act_set_brightness,
        set_contrast as act_set_contrast,
        set_picture_mode as act_set_picture_mode,
        set_picture_setting as act_set_picture_setting,
        set_sound_mode as act_set_sound_mode,
        set_sound_setting as act_set_sound_setting,
        set_volume as act_set_volume,
        show_message as act_show_message,
    )
    from .tv.settings import SettingMenuItem
    from .tv.state import (
        apply_device_info_update,
        apply_picture_update,
        apply_sound_update,
        apply_state_update,
        apply_volume_update,
    )
except (ImportError, ValueError):
    from crypto import generate_initial_credentials, resolve_ca_certificate, resolve_certificates
    from discovery import (
        get_device_fingerprint as discover_device_fingerprint,
        get_tv_timestamp,
        ping_tv,
    )
    from protocol.auth import (
        apply_mqtt_tls,
        is_token_expired,
        perform_token_refresh,
        probe_tv_auth_methods,
        test_tv_ssl_connection,
    )
    from protocol.pairing import async_start_pairing_handshake, async_submit_pin_code
    from protocol.topics import TOPIC_BROADCAST_BASEPATH, build_topic_paths
    from protocol.wol import send_wake_on_lan
    from tv.actions import (
        change_source as act_change_source,
        change_source_by_name_or_id as act_change_source_by_name_or_id,
        cycle_source as act_cycle_source,
        get_picture_settings as act_get_picture_settings,
        get_sound_settings as act_get_sound_settings,
        launch_app as act_launch_app,
        launch_app_by_name as act_launch_app_by_name,
        query_initial_state as act_query_initial_state,
        send_command as act_send_command,
        send_key as act_send_key,
        send_text_input as act_send_text_input,
        set_backlight as act_set_backlight,
        set_brightness as act_set_brightness,
        set_contrast as act_set_contrast,
        set_picture_mode as act_set_picture_mode,
        set_picture_setting as act_set_picture_setting,
        set_sound_mode as act_set_sound_mode,
        set_sound_setting as act_set_sound_setting,
        set_volume as act_set_volume,
        show_message as act_show_message,
    )
    from tv.settings import SettingMenuItem
    from tv.state import (
        apply_device_info_update,
        apply_picture_update,
        apply_sound_update,
        apply_state_update,
        apply_volume_update,
    )

_LOGGER = logging.getLogger(__name__)


class HisenseTvClient:
    """Client communicating with Hisense VIDAA TV over local TLS/MQTT broker."""

    def __init__(
        self,
        ip: str,
        mac: str | None = None,
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        access_token_time: int = 0,
        access_token_duration: int = 2,
        refresh_token: str | None = None,
        refresh_token_time: int = 0,
        refresh_token_duration: int = 30,
        certfile: str | None = None,
        keyfile: str | None = None,
        ca_cert: str | None = None,
        use_ssl: bool = True,
        verify_ssl: bool = False,
        auth_profile: str = "auto",
        name: str | None = None,
    ) -> None:
        """Initialize the client."""
        self.ip = ip
        self.mac = mac
        self.client_id = client_id or ""
        self.username = username or ""
        self.password = password or ""
        self.access_token = access_token
        self.access_token_time = int(access_token_time)
        self.access_token_duration = int(access_token_duration)
        self.refresh_token = refresh_token
        self.refresh_token_time = int(refresh_token_time)
        self.refresh_token_duration = int(refresh_token_duration)
        self.auth_profile = auth_profile
        self.name = name or f"Hisense TV ({self.ip})"

        self.certfile, self.keyfile = resolve_certificates(certfile, keyfile)
        self.ca_cert = resolve_ca_certificate(ca_cert)
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl

        # Runtime State
        self.connected: bool = False
        self.state: str = "off"
        self.volume: int = 0
        self.muted: bool = False
        self.sources: list[dict[str, Any]] = []
        self.current_source: str | None = None
        self.current_source_id: str | None = None
        self.apps: list[dict[str, Any]] = []
        self.current_app: str | None = None
        self.current_app_id: str | None = None
        self.current_channel: str | None = None
        self.current_program: str | None = None
        self.channel_number: str | None = None
        self.picture_mode: str | None = None
        self.sound_mode: str | None = None
        self.backlight: int | None = None
        self.brightness: int | None = None
        self.contrast: int | None = None
        self.picture_settings: dict[int, SettingMenuItem] = {}
        self.sound_settings: dict[int, SettingMenuItem] = {}
        self.audio_output_mode: str | None = None
        self.hdr_mode: str | None = None
        self.audio_format: str | None = None
        self.sleep_timer: int | None = None
        self.has_notifications: bool = False
        self.device_name: str | None = None
        self.model_name: str | None = None
        self.manufacturer: str | None = None
        self.firmware_version: str | None = None

        self.mqtt_client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._auth_future: asyncio.Future | None = None
        self._auth_code_future: asyncio.Future | None = None
        self._token_future: asyncio.Future | None = None
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._refresh_lock = threading.Lock()
        self._refreshing_token: bool = False
        self._last_refresh_attempt: float = 0.0
        self._reconnect_lock = threading.Lock()
        self._last_reconnect_time: float = 0.0

        # Topic paths
        self.topicBrcsBasepath = TOPIC_BROADCAST_BASEPATH
        self.topicTVUIBasepath = ""
        self.topicTVPSBasepath = ""
        self.topicMobiBasepath = ""
        self.topicRemoBasepath = ""
        self.define_topic_paths()

    # --------------------------------------------------------------------------
    # Callbacks & Event Dispatch
    # --------------------------------------------------------------------------
    def _register_callback(self, event: str, cb: Callable) -> None:
        if cb not in self._callbacks[event]:
            self._callbacks[event].append(cb)

    def _unregister_callback(self, event: str, cb: Callable) -> None:
        if cb in self._callbacks[event]:
            self._callbacks[event].remove(cb)

    def _dispatch(self, event: str, *args: Any) -> None:
        for cb in list(self._callbacks[event]):
            try:
                cb(*args)
            except Exception as e:
                _LOGGER.error("Error in callback for %s: %s", event, e)


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

    def register_device_info_callback(self, cb: Callable) -> None:
        self._register_callback("device_info", cb)

    def unregister_device_info_callback(self, cb: Callable) -> None:
        self._unregister_callback("device_info", cb)

    def _dispatch_auth_failed(self) -> None:
        self._dispatch("auth_failed")

    def _dispatch_connected(self) -> None:
        self._dispatch("connected")

    def _dispatch_disconnected(self) -> None:
        self._dispatch("disconnected")

    def _dispatch_state_update(self, data: Any) -> None:
        apply_state_update(self, data)
        self._dispatch("state", data)

    def _dispatch_device_info_update(self, data: Any) -> None:
        apply_device_info_update(self, data)
        self._dispatch("device_info", data)

    def _dispatch_volume_update(self, data: Any) -> None:
        apply_volume_update(self, data)
        self._dispatch("volume", data)

    def _dispatch_sourcelist_update(self, data: Any) -> None:
        if isinstance(data, list):
            self.sources = data
        elif isinstance(data, dict) and "sourcelist" in data:
            self.sources = data["sourcelist"]
        self._dispatch("sourcelist", self.sources)

    def _dispatch_applist_update(self, data: Any) -> None:
        if isinstance(data, list):
            self.apps = data
        elif isinstance(data, dict) and "applist" in data:
            self.apps = data["applist"]
        self._dispatch("applist", self.apps)

    def _dispatch_picture_update(self, data: Any) -> None:
        apply_picture_update(self, data)
        self._dispatch("picture", data)

    def _dispatch_sound_update(self, data: Any) -> None:
        apply_sound_update(self, data)
        self._dispatch("sound", data)

    def _dispatch_token_refreshed(self) -> None:
        self._dispatch(
            "token_refreshed",
            {
                "access_token": self.access_token,
                "access_token_time": self.access_token_time,
                "access_token_duration": self.access_token_duration,
                "refresh_token": self.refresh_token,
                "refresh_token_time": self.refresh_token_time,
                "refresh_token_duration": self.refresh_token_duration,
            },
        )

    # --------------------------------------------------------------------------
    # Discovery, Network Diagnostics & SSL Checks
    # --------------------------------------------------------------------------
    def validate_certificates(self) -> None:
        """Validates that local client certificates exist on disk."""
        self.certfile, self.keyfile = resolve_certificates(self.certfile, self.keyfile)
        self.ca_cert = resolve_ca_certificate(self.ca_cert)
        if not self.certfile or not self.keyfile:
            raise FileNotFoundError(
                f"Client certificate ({self.certfile}) or private key ({self.keyfile}) could not be resolved."
            )

    def test_ssl_connection(self, timeout: float = 5.0) -> dict[str, Any]:
        """Performs a raw TLS handshake to test SSL reachability and cipher negotiation."""
        return test_tv_ssl_connection(
            self.ip,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            timeout=timeout,
        )

    def get_device_fingerprint(self, timeout: float = 2.0) -> dict[str, Any]:
        """Fetches UPnP/SSDP device description XML from the TV."""
        return discover_device_fingerprint(self.ip, timeout=timeout)

    def probe_auth_methods(self, timeout: float = 2.0) -> dict[str, Any]:
        """Probes which authentication handshake profiles are accepted by the TV broker."""
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
        paths = build_topic_paths(self.client_id)
        self.topicTVUIBasepath = paths.ui
        self.topicTVPSBasepath = paths.platform
        self.topicMobiBasepath = paths.mobile
        self.topicRemoBasepath = paths.remote
        self.topicBrcsBasepath = paths.broadcast

    def generate_initial_creds(
        self,
        use_new_auth: bool | None = None,
        auth_profile: str | None = None,
        timestamp: int | None = None,
    ) -> None:
        """Generates initial dynamic credentials for challenge-response pairing."""
        if timestamp is None and self.ip:
            timestamp = get_tv_timestamp(self.ip, timeout=1.5)
        profile = auth_profile or self.auth_profile
        self.client_id, self.username, self.password = generate_initial_credentials(
            mac=self.mac,
            timestamp=timestamp,
            auth_profile=profile,
            use_new_auth=use_new_auth,
        )
        self.define_topic_paths()
        _LOGGER.debug(
            "Generated initial creds (profile=%s, use_new_auth=%s, ts=%s) - Client ID: %s, Username: %s",
            profile,
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
        apply_mqtt_tls(
            client=client,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            use_ssl=self.use_ssl,
        )

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
            _LOGGER.info("[%s] Connected to TV MQTT broker", self.ip)
            self._dispatch_connected()
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
            _LOGGER.warning("[%s] Failed to connect to TV MQTT broker (rc: %d)", self.ip, rc)

            if rc in (4, 5):
                with contextlib.suppress(Exception):
                    client.loop_stop()

            if self._auth_future and not self._auth_future.done():
                self._safe_set_future_exception(
                    self._auth_future,
                    Exception(f"MQTT connection rejected with code {rc} (Not authorized / invalid credentials)"),
                )
                return

            if rc in (4, 5):
                if self.refresh_token:
                    current_time = time.time()
                    with self._refresh_lock:
                        should_refresh = not self._refreshing_token and (current_time - self._last_refresh_attempt > 15)
                    if should_refresh:
                        _LOGGER.info("[%s] Authentication failed on connect. Refreshing token in background...", self.ip)
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
                _LOGGER.info("[%s] Token successfully refreshed on connection failure.", self.ip)
            else:
                _LOGGER.warning("[%s] Token refresh failed (token expired on TV). Stopping auto-reconnect.", self.ip)
                self._dispatch_auth_failed()
        except Exception as e:
            _LOGGER.error("[%s] Error during background token refresh: %s", self.ip, e)
            self._dispatch_auth_failed()
        finally:
            with self._refresh_lock:
                self._refreshing_token = False

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self.connected = False
        _LOGGER.debug("[%s] Disconnected from TV MQTT broker (rc: %d)", self.ip, rc)
        if (self._auth_future and not self._auth_future.done()) or (self._auth_code_future and not self._auth_code_future.done()):
            with contextlib.suppress(Exception):
                client.loop_stop()
        self._dispatch_disconnected()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="ignore")
        _LOGGER.debug("[%s] Message received: %s on topic %s", self.ip, payload, topic)

        # Check authentication futures
        if self._auth_future and (
            topic in (
                self.topicMobiBasepath + "ui_service/data/authentication",
                self.topicMobiBasepath + "ui_service/data/vidaa_app_connect",
            )
            or topic.endswith("ui_service/data/authentication")
            or topic.endswith("ui_service/data/vidaa_app_connect")
        ):
            self._safe_set_future_result(self._auth_future, payload)
        elif self._auth_code_future and (
            topic == self.topicMobiBasepath + "ui_service/data/authenticationcode"
            or topic.endswith("ui_service/data/authenticationcode")
        ):
            self._safe_set_future_result(self._auth_code_future, payload)
        elif self._token_future and (
            topic in (
                self.topicMobiBasepath + "platform_service/data/tokenissuance",
                self.topicMobiBasepath + "platform_service/data/gettoken",
            )
            or topic.endswith("platform_service/data/tokenissuance")
            or topic.endswith("platform_service/data/gettoken")
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
                _LOGGER.debug("[%s] Error parsing state: %s", self.ip, e)
        elif topic in (
            self.topicBrcsBasepath + "platform_service/actions/volumechange",
            self.topicBrcsBasepath + "ui_service/volume",
            self.topicMobiBasepath + "platform_service/data/getvolume",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_volume_update(data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing volume: %s", self.ip, e)
        elif topic == self.topicBrcsBasepath + "platform_service/actions/tvsleep":
            self._dispatch_state_update({"statetype": "fake_sleep_0"})
        elif topic == self.topicMobiBasepath + "ui_service/data/sourcelist":
            try:
                data = json.loads(payload)
                self._dispatch_sourcelist_update(data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing sourcelist: %s", self.ip, e)
        elif topic == self.topicMobiBasepath + "ui_service/data/applist":
            try:
                data = json.loads(payload)
                self._dispatch_applist_update(data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing applist: %s", self.ip, e)
        elif topic in (
            self.topicMobiBasepath + "platform_service/data/picturesetting",
            self.topicBrcsBasepath + "platform_service/data/picturesetting",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_picture_update(data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing picturesetting: %s", self.ip, e)
        elif topic in (
            self.topicMobiBasepath + "platform_service/data/soundsetting",
            self.topicBrcsBasepath + "platform_service/data/soundsetting",
        ):
            try:
                data = json.loads(payload)
                self._dispatch_sound_update(data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing soundsetting: %s", self.ip, e)
        elif topic == self.topicMobiBasepath + "ui_service/data/capability":
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    caps = str(data).lower()
                    if "notify" in caps or "toast" in caps or "showmessage" in caps or "message" in caps:
                        self.has_notifications = True
                        _LOGGER.info("[%s] TV reported support for on-screen notifications: %s", self.ip, data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing capability descriptor: %s", self.ip, e)
        elif topic in (
            self.topicMobiBasepath + "platform_service/data/getdeviceinfo",
            self.topicMobiBasepath + "platform_service/data/gettvinfo",
        ) or topic.endswith("platform_service/data/getdeviceinfo") or topic.endswith("platform_service/data/gettvinfo"):
            try:
                data = json.loads(payload)
                self._dispatch_device_info_update(data)
            except Exception as e:
                _LOGGER.debug("[%s] Error parsing device info: %s", self.ip, e)

    # --------------------------------------------------------------------------
    # Authentication & Pairing Handshake
    # --------------------------------------------------------------------------
    async def async_start_auth(self) -> None:
        """Starts the authentication handshake and triggers the TV to show PIN."""
        await async_start_pairing_handshake(self)

    async def _async_start_auth_internal(
        self, profile: str = "modern", use_new_auth: bool | None = None
    ) -> None:
        """Internal helper attempting a single auth handshake attempt."""
        try:
            from .protocol.pairing import _async_execute_pairing_attempt
        except (ImportError, ValueError):
            from protocol.pairing import _async_execute_pairing_attempt
        await _async_execute_pairing_attempt(self, profile=profile, use_new_auth=use_new_auth)

    async def async_submit_pin(self, pin_code: str) -> dict[str, Any]:
        """Submits the PIN code entered by the user and retrieves token pair."""
        return await async_submit_pin_code(self, pin_code)

    def check_and_refresh_token(self, force: bool = False) -> bool:
        """Checks access token expiration and triggers refresh via refresh token if necessary."""
        if not self.refresh_token:
            return False

        if not force and self.access_token:
            if not is_token_expired(self.access_token_time, self.access_token_duration):
                return False
            _LOGGER.debug("[%s] Access token expired, initiating refresh", self.ip)

        return self.refresh_tokens()

    def refresh_tokens(self) -> bool:
        """Connects with the refresh token to obtain a fresh access token."""
        was_connected = self.connected
        main_client = self.mqtt_client
        if main_client:
            with contextlib.suppress(Exception):
                main_client.loop_stop()
                main_client.disconnect()
            self.mqtt_client = None
            self.connected = False

        updated_data = perform_token_refresh(
            ip=self.ip,
            client_id=self.client_id,
            username=self.username,
            refresh_token=self.refresh_token or "",
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
        )

        if updated_data:
            self.access_token = updated_data["accesstoken"]
            self.access_token_time = int(updated_data.get("accesstoken_time", int(time.time())))
            self.access_token_duration = int(updated_data.get("accesstoken_duration_day", 2))
            self.refresh_token = updated_data.get("refreshtoken", self.refresh_token)
            self.refresh_token_time = int(updated_data.get("refreshtoken_time", int(time.time())))
            self.refresh_token_duration = int(
                updated_data.get("refreshtoken_duration_day")
                or updated_data.get("refresh_token_duration_day", 30)
            )
            self._dispatch_token_refreshed()
            if was_connected or main_client:
                self.connect_and_run()
            return True

        return False

    # --------------------------------------------------------------------------
    # Main Runtime Connection Loop
    # --------------------------------------------------------------------------
    def connect_and_run(self) -> None:
        """Main client connection loop using the access token as password."""
        if not self.access_token or not self.client_id or not self.username:
            _LOGGER.error("[%s] Cannot connect to TV: missing credentials (client_id, username, or access_token)", self.ip)
            return

        if self.mqtt_client:
            _LOGGER.debug("[%s] Cleaning up existing MQTT client before reconnecting", self.ip)
            try:
                self.mqtt_client.on_connect = None
                self.mqtt_client.on_disconnect = None
                self.mqtt_client.on_message = None
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                _LOGGER.debug("[%s] Error disconnecting existing MQTT client: %s", self.ip, e)
            finally:
                self.mqtt_client = None
                self.connected = False

        self.mqtt_client = self.create_mqtt_client(self.client_id, self.username, self.access_token)
        _LOGGER.debug("[%s] Starting background MQTT connection loop", self.ip)
        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

    def ensure_connected(self, min_interval: float = 5.0) -> bool:
        """Ensures the MQTT client is connected, rate-limiting reconnect attempts."""
        if self.connected and self.mqtt_client:
            return True

        now = time.time()
        with self._reconnect_lock:
            if now - self._last_reconnect_time < min_interval:
                _LOGGER.debug(
                    "[%s] Skipping reconnection attempt: last attempt was %.1fs ago (min interval: %.1fs)",
                    self.ip,
                    now - self._last_reconnect_time,
                    min_interval,
                )
                return False
            self._last_reconnect_time = now

        _LOGGER.debug("[%s] Ensuring MQTT connection to TV...", self.ip)
        try:
            self.check_and_refresh_token()
            self.connect_and_run()
            return True
        except Exception as e:
            _LOGGER.error("[%s] Error during ensure_connected: %s", self.ip, e)
            return False

    def query_initial_state(self) -> None:
        """Queries initial state, volume, source list, app list, and settings from TV."""
        act_query_initial_state(self)

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
        return send_wake_on_lan(mac=mac, broadcast_ip=broadcast_ip, port=port, ip=ip)

    def show_message(self, message: str, title: str | None = None, duration: int = 5) -> bool:
        """Displays an on-screen toast popup notification on the TV."""
        return act_show_message(self, message=message, title=title, duration=duration)

    def send_key(self, key: str) -> None:
        """Publishes a raw keypress event to the TV."""
        act_send_key(self, key=key)

    def send_command(self, command: str) -> bool:
        """Sends a key command to the TV, automatically resolving known key aliases."""
        return act_send_command(self, command=command)

    def cycle_source(self) -> bool:
        """Cycles to the next available input source."""
        return act_cycle_source(self)

    def _launch_app_by_name(self, name_or_id: str) -> bool:
        """Launches an app by name or app ID from cached applist."""
        return act_launch_app_by_name(self, name_or_id=name_or_id)

    def _change_source_by_name_or_id(self, target: str) -> bool:
        """Switches to source by name (e.g. HDMI1, TV) or numeric sourceid."""
        return act_change_source_by_name_or_id(self, target=target)

    def set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100)."""
        act_set_volume(self, volume=volume)

    def change_source(self, source_id: str, source_name: str | None = None) -> None:
        """Switches the active input source on the TV."""
        act_change_source(self, source_id=source_id, source_name=source_name)

    def launch_app(self, app_id: str, app_name: str, url: str) -> None:
        """Launches an installed Smart TV application."""
        act_launch_app(self, app_id=app_id, app_name=app_name, url=url)

    # --------------------------------------------------------------------------
    # Picture & Sound Settings Controls
    # --------------------------------------------------------------------------
    def get_picture_settings(self) -> None:
        """Requests current picture settings menu information from the TV."""
        act_get_picture_settings(self)

    def set_picture_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific picture setting value."""
        act_set_picture_setting(self, menu_id=menu_id, menu_value=menu_value)

    def set_picture_mode(self, mode: str) -> None:
        """Sets the TV picture mode preset."""
        act_set_picture_mode(self, mode=mode)

    def set_backlight(self, level: int) -> None:
        """Sets the TV backlight level (0–100)."""
        act_set_backlight(self, level=level)

    def set_brightness(self, level: int) -> None:
        """Sets the TV brightness level (0–100)."""
        act_set_brightness(self, level=level)

    def set_contrast(self, level: int) -> None:
        """Sets the TV contrast level (0–100)."""
        act_set_contrast(self, level=level)

    def get_sound_settings(self) -> None:
        """Requests current sound settings menu information from the TV."""
        act_get_sound_settings(self)

    def set_sound_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific sound setting value."""
        act_set_sound_setting(self, menu_id=menu_id, menu_value=menu_value)

    def set_sound_mode(self, mode: str) -> None:
        """Sets the TV sound mode preset."""
        act_set_sound_mode(self, mode=mode)

    def send_text_input(self, text: str, action: str = "insert") -> None:
        """Sends virtual keyboard string input to active on-screen input/search field."""
        act_send_text_input(self, text=text, action=action)

    # --------------------------------------------------------------------------
    # Async Queries & Disconnect
    # --------------------------------------------------------------------------
    async def async_query(self, pub_topic: str, sub_topic: str, payload: str | None = None) -> Any:
        """Publishes a query to the TV and asynchronously awaits the response topic."""
        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def on_msg(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
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
