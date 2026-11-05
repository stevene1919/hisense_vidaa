"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from .crypto import generate_initial_credentials, resolve_ca_certificate, resolve_certificates
from .discovery import (
    BRAND_MAP,
    get_device_fingerprint as discover_device_fingerprint,
    get_tv_timestamp,
)
from .protocol.auth import (
    async_perform_token_refresh,
    async_probe_tv_auth_methods,
    async_test_tv_ssl_connection,
    is_token_expired,
)
from .protocol.auth_lifecycle import TokenLifecycleManager
from .protocol.connection import ConnectionManagerMixin, MqttSessionAdapter
from .protocol.pairing import (
    _async_execute_pairing_attempt,
    async_start_pairing_handshake,
    async_submit_pin_code,
)
from .protocol.ping import async_ping_tv
from .protocol.topics import build_topic_paths
from .protocol.upnp import HisenseUpnpClient
from .protocol.wol import send_wake_on_lan
from .tv.actions import TvActionsMixin
from .tv.callbacks import CallbackRegistryMixin
from .tv.state import TvStateMixin

if TYPE_CHECKING:
    import aiohttp

_LOGGER = logging.getLogger(__name__)


def _run_sync(coro: Any) -> Any:
    """Runs a coroutine to completion from synchronous (CLI) code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise RuntimeError("Synchronous client API called from a running event loop; use the async_* variant")


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
        brand: str = "his",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the client."""
        self.ip = ip
        self.mac = mac
        self.brand = "his" if (not brand or brand == "auto") else brand
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

        # If client_id was provided with an embedded brand tag ($<brand>$), verify it matches self.brand
        if (
            self.mac
            and self.brand
            and self.client_id
            and "$" in self.client_id
            and self.auth_profile not in ("legacy", "static")
            and f"${self.brand}$" not in self.client_id
        ):
            _LOGGER.info(
                "[%s] Client ID embedded brand does not match configured brand '%s'; regenerating initial credentials",
                self.ip,
                self.brand,
            )
            self.client_id, self.username, self.password = generate_initial_credentials(
                mac=self.mac,
                auth_profile=self.auth_profile,
                brand=self.brand,
            )
            self.access_token = None
            self.refresh_token = None

        if not name:
            brand_display = BRAND_MAP.get(self.brand, "Hisense")
            self.name = f"{brand_display} TV ({self.ip})"
        else:
            self.name = name

        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl

        if not use_ssl or auth_profile in ("legacy", "static") or (
            certfile
            and keyfile
            and not (
                (isinstance(certfile, str) and certfile.lower().endswith((".p12", ".pfx")))
                or (isinstance(keyfile, str) and keyfile.lower().endswith((".p12", ".pfx")))
            )
        ):
            self.certfile = certfile
            self.keyfile = keyfile
            self.ca_cert = ca_cert
        else:
            self.certfile, self.keyfile = resolve_certificates(
                auth_profile=auth_profile, certfile=certfile, keyfile=keyfile
            )
            self.ca_cert = resolve_ca_certificate(ca_cert)

        # Runtime State
        self._init_runtime_state()

        self.mqtt_client: MqttSessionAdapter | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._mqtt_task: asyncio.Task | None = None
        self._query_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._pending_queries: dict[str, list[asyncio.Future]] = {}
        self._auth_future: asyncio.Future | None = None
        self._auth_code_future: asyncio.Future | None = None
        self._token_future: asyncio.Future | None = None
        self._init_callbacks()

        self._token_manager = TokenLifecycleManager(self)
        self._reconnect_lock = asyncio.Lock()
        self._last_reconnect_time: float = 0.0
        self._last_initial_query_time: float = 0.0

        # Topic paths
        self.topics = build_topic_paths(self.client_id)

        # UPnP Client for zero-cert fast reachability, volume, and playback state
        # (shares Home Assistant's aiohttp session when injected)
        self.upnp = HisenseUpnpClient(self.ip, session=session)

    # --------------------------------------------------------------------------
    # Backward compatibility properties for TokenLifecycleManager
    # --------------------------------------------------------------------------
    @property
    def _refresh_lock(self) -> asyncio.Lock:
        return self._token_manager.refresh_lock

    @property
    def _refreshing_token(self) -> bool:
        return self._token_manager.refreshing_token

    @_refreshing_token.setter
    def _refreshing_token(self, value: bool) -> None:
        self._token_manager.refreshing_token = value

    @property
    def _last_refresh_attempt(self) -> float:
        return self._token_manager.last_refresh_attempt

    @_last_refresh_attempt.setter
    def _last_refresh_attempt(self, value: float) -> None:
        self._token_manager.last_refresh_attempt = value

    @property
    def _last_awake_refresh_attempt(self) -> float:
        return self._token_manager.last_awake_refresh_attempt

    @_last_awake_refresh_attempt.setter
    def _last_awake_refresh_attempt(self, value: float) -> None:
        self._token_manager.last_awake_refresh_attempt = value

    @property
    def _rejected_refresh_failures(self) -> int:
        return self._token_manager.rejected_refresh_failures

    @_rejected_refresh_failures.setter
    def _rejected_refresh_failures(self, value: int) -> None:
        self._token_manager.rejected_refresh_failures = value

    @property
    def _broker_rejection_failures(self) -> int:
        return self._token_manager.broker_rejection_failures

    @_broker_rejection_failures.setter
    def _broker_rejection_failures(self, value: int) -> None:
        self._token_manager.broker_rejection_failures = value

    @property
    def _last_refresh_connect_rc(self) -> int | None:
        return self._token_manager.last_refresh_connect_rc

    @_last_refresh_connect_rc.setter
    def _last_refresh_connect_rc(self, value: int | None) -> None:
        self._token_manager.last_refresh_connect_rc = value

    @property
    def _token_watch(self) -> asyncio.Task | None:
        return self._token_manager.token_watch_task

    @property
    def _token_watch_closed(self) -> bool:
        return self._token_manager.token_watch_closed

    @_token_watch_closed.setter
    def _token_watch_closed(self, value: bool) -> None:
        self._token_manager.token_watch_closed = value

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

    @property
    def _query_timer(self) -> Any:
        return self._query_task

    @_query_timer.setter
    def _query_timer(self, value: Any) -> None:
        self._query_task = value

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        """Legacy callback compatibility shim for tests and external callers."""
        if hasattr(client, "loop_stop"):
            client.loop_stop()
        if hasattr(self, "_auth_future") and self._auth_future and not self._auth_future.done():
            self._auth_future.set_exception(Exception(f"MQTT connection rejected with code {rc}"))
            return
        if rc == 0:
            self._handle_connected(client, standard=True)
        else:
            self._token_manager.handle_auth_rejection(rc)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        """Legacy callback compatibility shim."""
        self._handle_disconnected()

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        """Legacy callback compatibility shim."""
        topic = getattr(message, "topic", "")
        payload = getattr(message, "payload", b"")
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="ignore")
        self._handle_message(str(topic), payload)

    def _handle_incoming_message(self, topic: str, payload: str) -> None:
        """Alias for _handle_message for backwards compatibility."""
        self._handle_message(topic, payload)

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

    async def async_test_ssl_connection(self, timeout: float = 5.0) -> dict[str, Any]:
        """Performs a raw TLS handshake to test SSL reachability and cipher negotiation."""
        return await async_test_tv_ssl_connection(
            self.ip,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            timeout=timeout,
        )

    def test_ssl_connection(self, timeout: float = 5.0) -> dict[str, Any]:
        """Synchronous (CLI) wrapper for async_test_ssl_connection."""
        return _run_sync(self.async_test_ssl_connection(timeout))

    async def async_get_device_fingerprint(self, timeout: float = 2.0) -> dict[str, Any]:
        """Fetches the UPnP renderer description via the shared aiohttp session."""
        return await self.upnp.async_get_device_fingerprint(timeout=timeout)

    def get_device_fingerprint(self, timeout: float = 2.0) -> dict[str, Any]:
        """Synchronous (CLI) fingerprint including mDNS/UPnP service probing."""

        return discover_device_fingerprint(self.ip, timeout=timeout)

    async def async_probe_auth_methods(self, timeout: float = 2.0) -> dict[str, Any]:
        """Probes which authentication handshake profiles are accepted by the TV broker."""
        return await async_probe_tv_auth_methods(
            self.ip,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            mac=self.mac,
            timeout=timeout,
            brand=self.brand,
            timestamp=int(time.time()) + self.clock_offset,
        )

    def probe_auth_methods(self, timeout: float = 2.0) -> dict[str, Any]:
        """Synchronous (CLI) wrapper for async_probe_auth_methods."""
        return _run_sync(self.async_probe_auth_methods(timeout))

    async def async_ping(self, timeout: float = 3.0) -> dict[str, Any]:
        """Quickly tests if TV broker is listening, accepting TLS, and responding to MQTT packets."""
        return await async_ping_tv(
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
            upnp=self.upnp,
            brand=self.brand,
        )

    def ping(self, timeout: float = 3.0) -> dict[str, Any]:
        """Synchronous (CLI) wrapper for async_ping."""
        return _run_sync(self.async_ping(timeout))

    # --------------------------------------------------------------------------
    # Topic Configuration & Credentials Generation
    # --------------------------------------------------------------------------
    def update_topic_paths(self) -> None:
        """Sets up topic paths for the specific client ID."""
        self.topics = build_topic_paths(self.client_id)

    def derive_pairing_credentials(
        self,
        use_new_auth: bool | None = None,
        auth_profile: str | None = None,
        timestamp: int | None = None,
    ) -> None:
        """Derives initial dynamic credentials for challenge-response pairing.

        ``timestamp`` must be supplied by callers that fetched the TV clock
        (off-loop); when omitted the local clock is used.
        """
        profile = auth_profile or self.auth_profile
        self.client_id, self.username, self.password = generate_initial_credentials(
            mac=self.mac,
            timestamp=timestamp,
            auth_profile=profile,
            use_new_auth=use_new_auth,
            brand=self.brand,
        )
        self.update_topic_paths()
        _LOGGER.debug(
            "Derived pairing credentials (profile=%s, use_new_auth=%s, ts=%s) - Client ID: %s, Username: %s",
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

    async def async_sync_clock(self, timeout: float = 2.0) -> int | None:
        """Queries TV UPnP Date header, updates clock_offset, and triggers callbacks."""
        sync_fn = self.__dict__.get("sync_clock")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn(timeout=timeout)
            if asyncio.iscoroutine(res):
                return await res
            return res

        tv_timestamp = await self.upnp.async_get_tv_timestamp(timeout=timeout)
        if tv_timestamp is None:
            try:
                tv_timestamp = get_tv_timestamp(self.ip, timeout=timeout)
            except Exception:
                tv_timestamp = None
        if tv_timestamp:
            self.tv_timestamp = tv_timestamp
            self.clock_offset = tv_timestamp - int(time.time())
            self.last_clock_sync = time.time()
            _LOGGER.debug(
                "[%s] Synchronized TV clock: %d (offset: %d s)",
                self.ip,
                tv_timestamp,
                self.clock_offset,
            )
            self._dispatch_clock_drift_update(self.clock_offset)
            return self.clock_offset
        return None

    def sync_clock(self, timeout: float = 2.0) -> int | None:
        """Synchronous (CLI) wrapper for async_sync_clock."""
        return _run_sync(self.async_sync_clock(timeout))

    async def async_check_and_refresh_token(
        self,
        force: bool = False,
        margin_seconds: int = 0,
        clock_offset: int | None = None,
    ) -> bool:
        """Checks access token expiration and triggers refresh via refresh token if necessary."""
        sync_fn = self.__dict__.get("check_and_refresh_token")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn(force=force, margin_seconds=margin_seconds, clock_offset=clock_offset)
            if asyncio.iscoroutine(res):
                return await res
            return bool(res)

        if not self.refresh_token:
            return False

        effective_offset = self.clock_offset if clock_offset is None else clock_offset

        if not force and self.access_token:
            if not is_token_expired(
                self.access_token_time,
                self.access_token_duration,
                margin_seconds=margin_seconds,
                clock_offset=effective_offset,
            ):
                return False
            _LOGGER.debug(
                "[%s] Access token expired or within margin (clock_offset=%d), initiating refresh",
                self.ip,
                effective_offset,
            )

        return await self.async_refresh_tokens()

    def check_and_refresh_token(
        self,
        force: bool = False,
        margin_seconds: int = 0,
        clock_offset: int | None = None,
    ) -> bool:
        """Synchronous (CLI) wrapper for async_check_and_refresh_token."""
        if not self.refresh_token:
            return False
        return _run_sync(self.async_check_and_refresh_token(force, margin_seconds, clock_offset))

    async def async_refresh_tokens(self) -> bool:
        """Connects with the refresh token to obtain a fresh access token."""
        sync_fn = self.__dict__.get("refresh_tokens")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn()
            if asyncio.iscoroutine(res):
                return await res
            return bool(res)

        # Query TV UPnP clock before refreshing to ensure credentials and expiration match TV epoch
        await self.async_sync_clock(timeout=2.0)

        had_session = self._mqtt_task is not None or self.mqtt_client is not None
        if had_session:
            # The TV only allows one session per client id: stop the main session
            # (and its reconnect loop) while the refresh session runs.
            await self._async_stop_session()

        refresh_status: dict[str, Any] = {}
        updated_data = await async_perform_token_refresh(
            ip=self.ip,
            client_id=self.client_id,
            username=self.username,
            refresh_token=self.refresh_token or "",
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            out_status=refresh_status,
            use_ssl=self.use_ssl,
        )
        self._last_refresh_connect_rc = refresh_status.get("connect_rc")

        if updated_data:
            self.access_token = updated_data["accesstoken"]
            self.access_token_time = int(
                updated_data.get("accesstoken_time", int(time.time()) + self.clock_offset)
            )
            self.access_token_duration = int(updated_data.get("accesstoken_duration_day", 2))
            self.refresh_token = updated_data.get("refreshtoken", self.refresh_token)
            self.refresh_token_time = int(
                updated_data.get("refreshtoken_time", int(time.time()) + self.clock_offset)
            )
            self.refresh_token_duration = int(
                updated_data.get("refreshtoken_duration_day")
                or updated_data.get("refresh_token_duration_day", 30)
            )
            self._dispatch_token_refreshed()
            if had_session:
                await self.async_connect_and_run()
            return True

        if had_session:
            _LOGGER.warning(
                "[%s] Token refresh failed (TV in standby or unreachable); restoring MQTT connection with the current access token",
                self.ip,
            )
            await self.async_connect_and_run()
        return False

    def refresh_tokens(self) -> bool:
        """Synchronous (CLI) wrapper for async_refresh_tokens."""
        return _run_sync(self.async_refresh_tokens())

    @staticmethod
    def send_wake_on_lan(
        mac: str | list[str] | tuple[str, ...],
        broadcast_ip: str | None = None,
        port: int = 9,
        ip: str | None = None,
    ) -> bool:
        """Sends standard Wake-on-LAN magic packet UDP broadcasts for one or multiple MACs."""
        return send_wake_on_lan(mac=mac, broadcast_ip=broadcast_ip, port=port, ip=ip)

    # --------------------------------------------------------------------------
    # UPnP / DLNA LAN Control Integration
    # --------------------------------------------------------------------------
    async def async_upnp_get_volume(self) -> int | None:
        """Retrieves master volume level (0-100) via UPnP RenderingControl."""
        return await self.upnp.async_get_volume()

    async def async_upnp_set_volume(self, volume: int) -> bool:
        """Sets master volume level (0-100) via UPnP RenderingControl."""
        return await self.upnp.async_set_volume(volume)

    async def async_upnp_get_mute(self) -> bool | None:
        """Retrieves master mute status via UPnP RenderingControl."""
        return await self.upnp.async_get_mute()

    async def async_upnp_set_mute(self, mute: bool) -> bool:
        """Sets master mute status (True/False) via UPnP RenderingControl."""
        return await self.upnp.async_set_mute(mute)

    async def async_upnp_get_transport_info(self) -> dict[str, str] | None:
        """Retrieves playback transport info (PLAYING, STOPPED, etc.) via UPnP AVTransport."""
        return await self.upnp.async_get_transport_info()

    async def async_upnp_probe(self) -> dict[str, Any] | None:
        """Probes UPnP endpoint for fast sub-second reachability and status."""
        return await self.upnp.async_probe()
