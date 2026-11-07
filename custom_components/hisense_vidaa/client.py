"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from .const import BRAND_MAP
from .protocol import generate_initial_credentials, resolve_ca_certificate, resolve_certificates
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
from .tv.fingerprint import (
    get_device_fingerprint as discover_device_fingerprint,
    get_tv_timestamp,
)
from .tv.state import TvStateMixin
from .tv.tokens import TvTokenLifecycleMixin, _run_sync
from .tv.upnp_mixin import TvUpnpMixin

if TYPE_CHECKING:
    import aiohttp

__all__ = [
    "HisenseTvClient",
    "async_perform_token_refresh",
    "get_tv_timestamp",
    "is_token_expired",
]

_LOGGER = logging.getLogger(__name__)


class HisenseTvClient(
    CallbackRegistryMixin,
    TvStateMixin,
    ConnectionManagerMixin,
    TvActionsMixin,
    TvTokenLifecycleMixin,
    TvUpnpMixin,
):
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
        self._disconnect_debounce_handle: asyncio.TimerHandle | None = None
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

    @staticmethod
    def send_wake_on_lan(
        mac: str | list[str] | tuple[str, ...],
        broadcast_ip: str | None = None,
        port: int = 9,
        ip: str | None = None,
    ) -> bool:
        """Sends standard Wake-on-LAN magic packet UDP broadcasts for one or multiple MACs."""
        return send_wake_on_lan(mac=mac, broadcast_ip=broadcast_ip, port=port, ip=ip)
