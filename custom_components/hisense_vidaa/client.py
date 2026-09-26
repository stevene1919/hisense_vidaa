"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

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
from .protocol.connection import (
    build_mqtt_client,
    clean_disconnect_mqtt_client,
    subscribe_standard_tv_topics,
)
from .protocol.dispatcher import dispatch_incoming_mqtt_message
from .protocol.pairing import (
    _async_execute_pairing_attempt,
    async_start_pairing_handshake,
    async_submit_pin_code,
)
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
    turn_off_tv as act_turn_off_tv,
    turn_on_tv as act_turn_on_tv,
)
from .tv.callbacks import CallbackRegistryMixin
from .tv.settings import SettingMenuItem

_LOGGER = logging.getLogger(__name__)


class HisenseTvClient(CallbackRegistryMixin):
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

        self.certfile, self.keyfile = resolve_certificates(auth_profile=auth_profile, certfile=certfile, keyfile=keyfile)
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
        self._init_callbacks()
        self._refresh_lock = threading.Lock()
        self._refreshing_token: bool = False
        self._last_refresh_attempt: float = 0.0
        self._reconnect_lock = threading.Lock()
        self._last_reconnect_time: float = 0.0
        # Token refresh retry while the TV is awake (the TV answers gettoken only when on)
        self._token_watch: threading.Timer | None = None
        self._token_watch_closed: bool = False
        self._awake_refresh_failures: int = 0
        self._last_awake_refresh_attempt: float = 0.0
        # Consecutive failed refreshes after the broker rejected the access token (rc 4/5);
        # drives the retry backoff (1 min .. 30 min) so a TV in standby is not hammered.
        self._rejected_refresh_failures: int = 0
        self._rejected_retry_timer: threading.Timer | None = None

        # Topic paths
        self.topicBrcsBasepath = TOPIC_BROADCAST_BASEPATH
        self.topicTVUIBasepath = ""
        self.topicTVPSBasepath = ""
        self.topicMobiBasepath = ""
        self.topicRemoBasepath = ""
        self.define_topic_paths()

    @property
    def is_on(self) -> bool:
        """Returns True if the TV is connected and active."""
        return self.state not in ("off", "")

    @is_on.setter
    def is_on(self, value: bool) -> None:
        """Sets the power state."""
        self.state = "on" if value else "off"

    # --------------------------------------------------------------------------
    # Discovery, Network Diagnostics & SSL Checks
    # --------------------------------------------------------------------------
    def validate_certificates(self) -> None:
        """Validates that local client certificates exist on disk."""
        self.certfile, self.keyfile = resolve_certificates(auth_profile=self.auth_profile, certfile=self.certfile, keyfile=self.keyfile)
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
        return build_mqtt_client(
            client_id=client_id,
            username=username,
            password=password,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            use_ssl=self.use_ssl,
            on_connect=self._on_connect,
            on_message=self._on_message,
            on_disconnect=self._on_disconnect,
        )

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
            subscribe_standard_tv_topics(
                client=client,
                broadcast_basepath=self.topicBrcsBasepath,
                mobile_basepath=self.topicMobiBasepath,
            )
            if self.refresh_token and not self._refreshing_token:
                threading.Thread(target=self._proactive_token_refresh, daemon=True).start()

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
                if self.refresh_token and not is_token_expired(self.refresh_token_time, self.refresh_token_duration):
                    current_time = time.time()
                    with self._refresh_lock:
                        retry_after = min(60 * (2 ** self._rejected_refresh_failures), 1800)
                        should_refresh = not self._refreshing_token and (current_time - self._last_refresh_attempt > retry_after)
                        if should_refresh:
                            self._refreshing_token = True
                            self._last_refresh_attempt = current_time
                    if should_refresh:
                        _LOGGER.info("[%s] Authentication failed on connect. Refreshing token in background...", self.ip)
                        threading.Thread(target=self._refresh_token_and_update_creds, daemon=True).start()
                    else:
                        # paho's loop is stopped on rc 4/5, so nothing would retry by itself:
                        # reconnect (and thereby retry the refresh) once the backoff has passed.
                        self._schedule_rejected_retry(max(5.0, retry_after - (current_time - self._last_refresh_attempt)))
                else:
                    _LOGGER.warning("[%s] MQTT authentication rejected and no valid refresh token available. Reauthentication required.", self.ip)
                    self._dispatch_auth_failed()

    def _schedule_rejected_retry(self, delay: float) -> None:
        with self._refresh_lock:
            if self._rejected_retry_timer is not None:
                return
            timer = threading.Timer(delay, self._rejected_retry_fire)
            timer.daemon = True
            self._rejected_retry_timer = timer
            timer.start()
        _LOGGER.debug("[%s] Next reconnect attempt in %.0f s", self.ip, delay)

    def _rejected_retry_fire(self) -> None:
        with self._refresh_lock:
            self._rejected_retry_timer = None
        try:
            self.connect_and_run()
        except Exception as e:
            _LOGGER.debug("[%s] Scheduled reconnect failed: %s", self.ip, e)

    def _cancel_rejected_retry(self) -> None:
        with self._refresh_lock:
            timer, self._rejected_retry_timer = self._rejected_retry_timer, None
        if timer:
            with contextlib.suppress(Exception):
                timer.cancel()

    def _refresh_token_and_update_creds(self) -> None:
        try:
            if self.check_and_refresh_token(force=True):
                _LOGGER.info("[%s] Token successfully refreshed on connection failure.", self.ip)
                self._rejected_refresh_failures = 0
            else:
                self._rejected_refresh_failures += 1
                _LOGGER.warning(
                    "[%s] Token refresh after rejected connection failed (attempt %d); next retry in %d min",
                    self.ip,
                    self._rejected_refresh_failures,
                    min(60 * (2 ** self._rejected_refresh_failures), 1800) // 60,
                )
                if not self.refresh_token or is_token_expired(self.refresh_token_time, self.refresh_token_duration):
                    _LOGGER.warning("[%s] Refresh token is missing or expired. Reauthentication required.", self.ip)
                    self._dispatch_auth_failed()
        except Exception as e:
            _LOGGER.warning("[%s] Background token refresh error: %s", self.ip, e)
            if not self.refresh_token or is_token_expired(self.refresh_token_time, self.refresh_token_duration):
                self._dispatch_auth_failed()
        finally:
            with self._refresh_lock:
                self._refreshing_token = False

    def _proactive_token_refresh(self) -> None:
        """Proactively refreshes the token if access token is within 12h of expiration."""
        try:
            if self.access_token and is_token_expired(self.access_token_time, self.access_token_duration, margin_seconds=43200):
                # Give the retained broadcast state (fake_sleep_0 in standby) time to arrive.
                # A TV in standby keeps its broker up but never answers gettoken, so the
                # refresh would only drop the working connection for nothing; the token
                # watch retries as soon as the TV is awake.
                time.sleep(self.PROACTIVE_REFRESH_SETTLE_SECONDS)
                if not self.is_on:
                    _LOGGER.info(
                        "[%s] Access token is near expiration, but the TV is in standby; deferring token refresh until it is awake",
                        self.ip,
                    )
                    return
                current_time = time.time()
                with self._refresh_lock:
                    should_refresh = not self._refreshing_token and (current_time - self._last_refresh_attempt > 60)
                    if should_refresh:
                        self._refreshing_token = True
                        self._last_refresh_attempt = current_time
                if should_refresh:
                    _LOGGER.info("[%s] Access token is near expiration (<12h remaining). Proactively renewing tokens...", self.ip)
                    self.refresh_tokens()
        except Exception as e:
            _LOGGER.debug("[%s] Proactive token refresh check error: %s", self.ip, e)
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
        payload = msg.payload.decode("utf-8", errors="ignore")
        dispatch_incoming_mqtt_message(self, topic=msg.topic, payload=payload)

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
        await _async_execute_pairing_attempt(self, profile=profile, use_new_auth=use_new_auth)

    async def async_submit_pin(self, pin_code: str) -> dict[str, Any]:
        """Submits the PIN code entered by the user and retrieves token pair."""
        return await async_submit_pin_code(self, pin_code)

    def check_and_refresh_token(self, force: bool = False, margin_seconds: int = 0) -> bool:
        """Checks access token expiration and triggers refresh via refresh token if necessary."""
        if not self.refresh_token:
            return False

        if not force and self.access_token:
            if not is_token_expired(self.access_token_time, self.access_token_duration, margin_seconds=margin_seconds):
                return False
            _LOGGER.debug("[%s] Access token expired or within margin, initiating refresh", self.ip)

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

        # Refresh failed: the TV answers ``gettoken`` only while it is awake, so a refresh
        # attempted in standby just times out. Do not leave the integration disconnected —
        # the current access token may still be valid — restore the main connection and
        # let the awake-retry logic try again later.
        if was_connected or main_client:
            _LOGGER.warning(
                "[%s] Token refresh failed (TV in standby or unreachable); restoring MQTT connection with the current access token",
                self.ip,
            )
            self.connect_and_run()
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
        self._token_watch_closed = False
        self._start_token_watch()

    # --------------------------------------------------------------------------
    # Token watch: periodic refresh retry while the TV is awake
    # --------------------------------------------------------------------------
    TOKEN_WATCH_INTERVAL = 300
    PROACTIVE_REFRESH_SETTLE_SECONDS = 3.0

    def _start_token_watch(self) -> None:
        with self._refresh_lock:
            if self._token_watch_closed or self._token_watch is not None:
                return
            timer = threading.Timer(self.TOKEN_WATCH_INTERVAL, self._token_watch_tick)
            timer.daemon = True
            self._token_watch = timer
            timer.start()

    def _stop_token_watch(self) -> None:
        with self._refresh_lock:
            self._token_watch_closed = True
            timer, self._token_watch = self._token_watch, None
        if timer:
            with contextlib.suppress(Exception):
                timer.cancel()

    def _token_watch_tick(self) -> None:
        with self._refresh_lock:
            self._token_watch = None
        try:
            self._maybe_refresh_while_awake()
        except Exception as e:
            _LOGGER.debug("[%s] Token watch error: %s", self.ip, e)
        self._start_token_watch()

    def _maybe_refresh_while_awake(self) -> None:
        """Renews a near-expiry access token once the TV is awake (with backoff on failure)."""
        if not (self.connected and self.is_on and self.access_token and self.refresh_token):
            return
        if not is_token_expired(self.access_token_time, self.access_token_duration, margin_seconds=43200):
            return
        backoff = min(600 * (2 ** self._awake_refresh_failures), 6 * 3600)
        now = time.time()
        with self._refresh_lock:
            if (
                self._refreshing_token
                or now - self._last_awake_refresh_attempt < backoff
                or now - self._last_refresh_attempt < 60
            ):
                return
            self._refreshing_token = True
            self._last_refresh_attempt = now
            self._last_awake_refresh_attempt = now
        ok = False
        try:
            _LOGGER.info("[%s] TV is awake and the access token is near expiration. Renewing tokens...", self.ip)
            ok = self.refresh_tokens()
        except Exception as e:
            _LOGGER.warning("[%s] Token refresh while awake failed: %s", self.ip, e)
        finally:
            with self._refresh_lock:
                self._refreshing_token = False
        if ok:
            self._awake_refresh_failures = 0
            _LOGGER.info("[%s] Tokens renewed successfully", self.ip)
        else:
            self._awake_refresh_failures += 1
            _LOGGER.warning(
                "[%s] Token refresh failed while the TV is awake (attempt %d); next retry in %d min",
                self.ip,
                self._awake_refresh_failures,
                min(600 * (2 ** self._awake_refresh_failures), 6 * 3600) // 60,
            )

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

    def turn_on(self, mac_targets: list[str] | None = None) -> None:
        """Powers on or wakes the TV safely and idempotently."""
        act_turn_on_tv(self, mac_targets=mac_targets)

    def turn_off(self) -> None:
        """Powers off the TV safely."""
        act_turn_off_tv(self)

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
        self._stop_token_watch()
        self._cancel_rejected_retry()
        if self.mqtt_client:
            clean_disconnect_mqtt_client(self.mqtt_client)
            self.mqtt_client = None
            self.connected = False

