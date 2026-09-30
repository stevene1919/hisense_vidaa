"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

from .crypto import generate_initial_credentials, resolve_ca_certificate, resolve_certificates
from .discovery import (
    get_device_fingerprint as discover_device_fingerprint,
    ping_tv,
)
from .protocol.auth import (
    is_token_expired,
    perform_token_refresh,
    probe_tv_auth_methods,
    test_tv_ssl_connection,
)
from .protocol.auth_lifecycle import TokenLifecycleManager
from .protocol.connection import ConnectionManagerMixin
from .protocol.pairing import (
    _async_execute_pairing_attempt,
    async_start_pairing_handshake,
    async_submit_pin_code,
)
from .protocol.topics import TOPIC_BROADCAST_BASEPATH, build_topic_paths
from .protocol.wol import send_wake_on_lan
from .tv.actions import TvActionsMixin
from .tv.callbacks import CallbackRegistryMixin
from .tv.state import TvStateMixin

_LOGGER = logging.getLogger(__name__)


class HisenseTvClient(CallbackRegistryMixin, TvStateMixin, ConnectionManagerMixin, TvActionsMixin):
    """Client communicating with Hisense VIDAA TV over local TLS/MQTT broker."""

    TOKEN_WATCH_INTERVAL = TokenLifecycleManager.TOKEN_WATCH_INTERVAL
    PROACTIVE_REFRESH_SETTLE_SECONDS = TokenLifecycleManager.PROACTIVE_REFRESH_SETTLE_SECONDS
    MAX_BROKER_REJECTION_ATTEMPTS = TokenLifecycleManager.MAX_BROKER_REJECTION_ATTEMPTS

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
        refresh_in_standby: bool = False,
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
        # Renew tokens while the TV is in standby (for TVs that keep their MQTT broker up when switched off).
        self.refresh_in_standby = refresh_in_standby
        self.name = name or f"Hisense TV ({self.ip})"

        self.certfile, self.keyfile = resolve_certificates(auth_profile=auth_profile, certfile=certfile, keyfile=keyfile)
        self.ca_cert = resolve_ca_certificate(ca_cert)
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl

        # Runtime State
        self._init_runtime_state()

        self.mqtt_client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._auth_future: asyncio.Future | None = None
        self._auth_code_future: asyncio.Future | None = None
        self._token_future: asyncio.Future | None = None
        self._init_callbacks()

        self._token_manager = TokenLifecycleManager(self)
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
    # Backward compatibility properties for TokenLifecycleManager
    # --------------------------------------------------------------------------
    @property
    def _refresh_lock(self) -> threading.Lock:
        return self._token_manager.refresh_lock

    @property
    def _refreshing_token(self) -> bool:
        return self._token_manager.refreshing_token

    @_refreshing_token.setter
    def _refreshing_token(self, val: bool) -> None:
        self._token_manager.refreshing_token = val

    @property
    def _last_refresh_attempt(self) -> float:
        return self._token_manager.last_refresh_attempt

    @_last_refresh_attempt.setter
    def _last_refresh_attempt(self, val: float) -> None:
        self._token_manager.last_refresh_attempt = val

    @property
    def _last_awake_refresh_attempt(self) -> float:
        return self._token_manager.last_awake_refresh_attempt

    @_last_awake_refresh_attempt.setter
    def _last_awake_refresh_attempt(self, val: float) -> None:
        self._token_manager.last_awake_refresh_attempt = val

    @property
    def _rejected_refresh_failures(self) -> int:
        return self._token_manager.rejected_refresh_failures

    @_rejected_refresh_failures.setter
    def _rejected_refresh_failures(self, val: int) -> None:
        self._token_manager.rejected_refresh_failures = val

    @property
    def _broker_rejection_failures(self) -> int:
        return self._token_manager.broker_rejection_failures

    @_broker_rejection_failures.setter
    def _broker_rejection_failures(self, val: int) -> None:
        self._token_manager.broker_rejection_failures = val

    @property
    def _last_refresh_connect_rc(self) -> int | None:
        return self._token_manager.last_refresh_connect_rc

    @_last_refresh_connect_rc.setter
    def _last_refresh_connect_rc(self, val: int | None) -> None:
        self._token_manager.last_refresh_connect_rc = val

    @property
    def _token_watch(self) -> threading.Timer | None:
        return self._token_manager.token_watch

    @_token_watch.setter
    def _token_watch(self, val: threading.Timer | None) -> None:
        self._token_manager.token_watch = val

    @property
    def _token_watch_closed(self) -> bool:
        return self._token_manager.token_watch_closed

    @_token_watch_closed.setter
    def _token_watch_closed(self, val: bool) -> None:
        self._token_manager.token_watch_closed = val

    def _start_token_watch(self) -> None:
        self._token_manager.start_token_watch()

    def _stop_token_watch(self) -> None:
        self._token_manager.stop_token_watch()

    def _token_watch_tick(self) -> None:
        self._token_manager._token_watch_tick()

    def _maybe_refresh_while_awake(self) -> None:
        self._token_manager.maybe_refresh_while_awake()

    def _proactive_token_refresh(self) -> None:
        self._token_manager.proactive_token_refresh()

    def _schedule_rejected_retry(self, delay: float) -> None:
        self._token_manager.schedule_rejected_retry(delay)

    def _rejected_retry_fire(self) -> None:
        self._token_manager._rejected_retry_fire()

    def _cancel_rejected_retry(self) -> None:
        self._token_manager.cancel_rejected_retry()

    def _refresh_token_and_update_creds(self) -> None:
        self._token_manager.refresh_token_and_update_creds()

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
        """Generates initial dynamic credentials for challenge-response pairing.

        ``timestamp`` must be supplied by callers that fetched the TV clock
        (off-loop); when omitted the local clock is used.
        """
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
            try:
                main_client.loop_stop()
                main_client.disconnect()
            except Exception:
                pass
            self.mqtt_client = None
            self.connected = False

        refresh_status: dict[str, Any] = {}
        updated_data = perform_token_refresh(
            ip=self.ip,
            client_id=self.client_id,
            username=self.username,
            refresh_token=self.refresh_token or "",
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            out_status=refresh_status,
        )
        self._last_refresh_connect_rc = refresh_status.get("connect_rc")

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

        if was_connected or main_client:
            _LOGGER.warning(
                "[%s] Token refresh failed (TV in standby or unreachable); restoring MQTT connection with the current access token",
                self.ip,
            )
            self.connect_and_run()
        return False

    @staticmethod
    def send_wake_on_lan(
        mac: str | list[str] | tuple[str, ...],
        broadcast_ip: str | None = None,
        port: int = 9,
        ip: str | None = None,
    ) -> bool:
        """Sends standard Wake-on-LAN magic packet UDP broadcasts for one or multiple MACs."""
        return send_wake_on_lan(mac=mac, broadcast_ip=broadcast_ip, port=port, ip=ip)
