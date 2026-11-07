"""Native asyncio MQTT connection, lifecycle, and topic subscription management (aiomqtt)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from aiomqtt import Client, MqttError, ProtocolVersion
from aiomqtt.exceptions import MqttConnectError

from .auth import build_mqtt_ssl_context, extract_connect_rc
from .dispatcher import dispatch_incoming_mqtt_message

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)

MQTT_PORT = 36669
AUTH_REJECTION_CODES = (4, 5, 134, 135)
RECONNECT_MIN_DELAY = 2.0
RECONNECT_MAX_DELAY = 30.0
DISCONNECT_DEBOUNCE = 2.0

__all__ = [
    "AUTH_REJECTION_CODES",
    "DISCONNECT_DEBOUNCE",
    "ConnectionManagerMixin",
    "MqttSessionAdapter",
    "standard_tv_topics",
]


def standard_tv_topics(broadcast_basepath: str, mobile_basepath: str) -> list[tuple[str, int]]:
    """Returns the standard VIDAA broadcast and mobile unicast telemetry topics."""
    return [
        (broadcast_basepath + "ui_service/state", 0),
        (broadcast_basepath + "platform_service/actions/volumechange", 0),
        (broadcast_basepath + "ui_service/volume", 0),
        (broadcast_basepath + "platform_service/actions/tvsleep", 0),
        (broadcast_basepath + "ui_service/data/hotelmodechange", 0),
        # The client's own mobile push tree: mirrors the pairing session so mid-session
        # pushes (authentication challenges, token issuance, code close/toast) are
        # received instead of dropped.
        (mobile_basepath + "#", 0),
        (mobile_basepath + "ui_service/data/sourcelist", 0),
        (mobile_basepath + "ui_service/data/applist", 0),
        (mobile_basepath + "ui_service/data/gettvstate", 0),
        (mobile_basepath + "ui_service/data/state", 0),
        (mobile_basepath + "platform_service/data/getvolume", 0),
        (mobile_basepath + "platform_service/data/gettvinfo", 0),
        (mobile_basepath + "platform_service/data/getdeviceinfo", 0),
        (mobile_basepath + "ui_service/data/capability", 0),
        (mobile_basepath + "platform_service/data/picturesetting", 0),
        (broadcast_basepath + "platform_service/data/picturesetting", 0),
        (mobile_basepath + "platform_service/data/soundsetting", 0),
        (broadcast_basepath + "platform_service/data/soundsetting", 0),
    ]


class MqttSessionAdapter:
    """Ordered outbound command queue bound to one live ``aiomqtt.Client`` session.

    ``publish``/``subscribe`` are non-blocking and safe to call from synchronous
    helpers (they only enqueue); ``async_publish``/``async_subscribe`` await the
    broker hand-off. A single writer task preserves command ordering (e.g. digit
    sequences, dual ``changesource`` publishes).
    """

    def __init__(self, session: Client, loop: asyncio.AbstractEventLoop) -> None:
        self.session = session
        self._loop = loop
        self._queue: asyncio.Queue[tuple[str, Any, Any, asyncio.Future | None]] = asyncio.Queue()
        self._writer = loop.create_task(self._run_writer())
        self.closed = False

    async def _run_writer(self) -> None:
        while True:
            kind, target, payload, fut = await self._queue.get()
            try:
                if kind == "pub":
                    await self.session.publish(target, payload)
                else:
                    await self.session.subscribe(target)
                if fut is not None and not fut.done():
                    fut.set_result(True)
            except asyncio.CancelledError:
                if fut is not None and not fut.done():
                    fut.cancel()
                raise
            except Exception as err:  # MqttError, ValueError
                _LOGGER.debug("MQTT %s on %s failed: %s", kind, target, err)
                if fut is not None and not fut.done():
                    fut.set_exception(err)

    def _enqueue(self, item: tuple[str, Any, Any, asyncio.Future | None]) -> None:
        if self.closed:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            self._queue.put_nowait(item)
        else:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)

    def publish(self, topic: str, payload: Any = None, *_args: Any, **_kwargs: Any) -> None:
        """Enqueues a publish without blocking."""
        self._enqueue(("pub", topic, payload, None))

    def subscribe(self, topics: Any, *_args: Any, **_kwargs: Any) -> None:
        """Enqueues a subscription without blocking."""
        self._enqueue(("sub", topics, None, None))

    async def async_publish(self, topic: str, payload: Any = None) -> None:
        """Publishes in queue order and awaits the broker hand-off."""
        fut = self._loop.create_future()
        self._enqueue(("pub", topic, payload, fut))
        await fut

    async def async_subscribe(self, topics: Any) -> None:
        """Subscribes in queue order and awaits the SUBACK."""
        fut = self._loop.create_future()
        self._enqueue(("sub", topics, None, fut))
        await fut

    def close(self) -> None:
        """Stops the writer task."""
        self.closed = True
        self._writer.cancel()


def _decode_payload(payload: Any) -> str:
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode("utf-8", errors="ignore")
    if payload is None:
        return ""
    return str(payload)


class ConnectionManagerMixin:
    """Mixin providing aiomqtt connection supervision and async query dispatching."""

    # ------------------------------------------------------------------
    # Future helpers (all callers run on the event loop)
    # ------------------------------------------------------------------
    def _safe_set_future_result(self: HisenseTvClient, future: asyncio.Future | None, result: Any) -> None:
        if future and not future.done():
            future.set_result(result)

    def _safe_set_future_exception(self: HisenseTvClient, future: asyncio.Future | None, exception: Exception) -> None:
        if future and not future.done():
            future.set_exception(exception)

    # ------------------------------------------------------------------
    # TLS
    # ------------------------------------------------------------------
    async def _async_build_ssl_context(self: HisenseTvClient) -> Any:
        """Builds and loads the client TLS context off the event loop (disk I/O)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            build_mqtt_ssl_context,
            self.certfile if self.use_ssl else None,
            self.keyfile if self.use_ssl else None,
            self.ca_cert,
            self.verify_ssl,
            self.use_ssl,
        )

    # ------------------------------------------------------------------
    # Connection lifecycle callbacks
    # ------------------------------------------------------------------
    def _handle_connected(
        self: HisenseTvClient, adapter: Any = None, standard: bool = True
    ) -> None:
        debounce_handle = getattr(self, "_disconnect_debounce_handle", None)
        if debounce_handle is not None:
            debounce_handle.cancel()
            self._disconnect_debounce_handle = None
            _LOGGER.debug("[%s] Reconnected within debounce window; cancelled pending disconnect dispatch", self.ip)

        self.connected = True
        _LOGGER.info("[%s] Connected to TV MQTT broker", self.ip)
        self._dispatch_connected()
        if not standard:
            return
        if adapter is not None and hasattr(adapter, "subscribe"):
            with contextlib.suppress(Exception):
                adapter.subscribe(standard_tv_topics(self.topics.broadcast, self.topics.mobile))
        self._spawn(self.async_sync_clock(2.0))
        if self.refresh_token and not self._token_manager.refreshing_token:
            self._spawn(self._token_manager.async_proactive_token_refresh())
        self._query_task = self._spawn(self._async_delayed_initial_query())

    async def _async_delayed_initial_query(self: HisenseTvClient) -> None:
        await asyncio.sleep(0.5)
        await self.async_query_initial_state()

    def _handle_disconnected(self: HisenseTvClient, *, debounce: bool = True) -> None:
        was_connected = self.connected
        self.connected = False
        self._last_initial_query_time = 0.0

        debounce_handle = getattr(self, "_disconnect_debounce_handle", None)
        if debounce_handle is not None:
            debounce_handle.cancel()
            self._disconnect_debounce_handle = None

        if not was_connected:
            return

        def _fire_disconnect() -> None:
            self._disconnect_debounce_handle = None
            _LOGGER.debug("[%s] Disconnected from TV MQTT broker (debounce elapsed)", self.ip)
            self._dispatch_disconnected()

        loop = getattr(self, "_loop", None)
        if not loop:
            with contextlib.suppress(RuntimeError):
                loop = asyncio.get_running_loop()

        if debounce and loop and loop.is_running() and DISCONNECT_DEBOUNCE > 0:
            self._disconnect_debounce_handle = loop.call_later(DISCONNECT_DEBOUNCE, _fire_disconnect)
        else:
            _LOGGER.debug("[%s] Disconnected from TV MQTT broker", self.ip)
            self._dispatch_disconnected()

    def _handle_message(self: HisenseTvClient, topic: str, payload: str) -> None:
        waiters = self._pending_queries.pop(topic, None)
        if waiters:
            for fut in waiters:
                self._safe_set_future_result(fut, payload)
        dispatch_incoming_mqtt_message(self, topic=topic, payload=payload)

    def _spawn(self: HisenseTvClient, coro: Any) -> asyncio.Task | None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if asyncio.iscoroutine(coro):
                coro.close()
            return None
        task = loop.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    # ------------------------------------------------------------------
    # Supervisor
    # ------------------------------------------------------------------
    async def _mqtt_session_loop(
        self: HisenseTvClient,
        client_id: str,
        username: str,
        password: str,
        ssl_ctx: Any,
        *,
        reconnect: bool,
        standard: bool,
        ready: asyncio.Future | None = None,
    ) -> None:
        """Runs one or more aiomqtt sessions, routing messages until cancelled."""
        loop = asyncio.get_running_loop()
        delay = RECONNECT_MIN_DELAY
        while True:
            adapter: MqttSessionAdapter | None = None
            try:
                async with Client(
                    hostname=self.ip,
                    port=MQTT_PORT,
                    username=username,
                    password=password,
                    identifier=client_id,
                    tls_context=ssl_ctx,
                    protocol=ProtocolVersion.V311,
                    clean_session=True,
                    keepalive=60,
                    timeout=10,
                ) as session:
                    adapter = MqttSessionAdapter(session, loop)
                    self.mqtt_client = adapter
                    delay = RECONNECT_MIN_DELAY
                    self._handle_connected(adapter, standard)
                    if ready is not None and not ready.done():
                        ready.set_result(True)
                    async for message in session.messages:
                        self._handle_message(str(message.topic), _decode_payload(message.payload))
            except asyncio.CancelledError:
                raise
            except MqttConnectError as err:
                rc = extract_connect_rc(err)
                self.connected = False
                _LOGGER.warning("[%s] Failed to connect to TV MQTT broker (return code: %d)", self.ip, rc)
                rejected = Exception(
                    f"MQTT connection rejected with code {rc} (Not authorized / invalid credentials)"
                )
                if ready is not None and not ready.done():
                    ready.set_exception(rejected)
                if self._auth_future and not self._auth_future.done():
                    self._safe_set_future_exception(self._auth_future, rejected)
                    return
                if rc in AUTH_REJECTION_CODES:
                    if standard:
                        self._spawn(self._token_manager.async_handle_auth_rejection(rc))
                    return
            except (MqttError, OSError) as err:
                _LOGGER.debug("[%s] MQTT session error: %s", self.ip, err)
                if ready is not None and not ready.done():
                    ready.set_exception(Exception(f"Cannot connect to TV MQTT Broker: {err}"))
            finally:
                if adapter is not None:
                    adapter.close()
                    if self.mqtt_client is adapter:
                        self.mqtt_client = None
                self._handle_disconnected()
            if not reconnect:
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _async_stop_session(self: HisenseTvClient) -> None:
        """Cancels the running MQTT supervisor task and waits for teardown."""
        debounce_handle = getattr(self, "_disconnect_debounce_handle", None)
        if debounce_handle is not None:
            debounce_handle.cancel()
            self._disconnect_debounce_handle = None
        task, self._mqtt_task = self._mqtt_task, None
        query_task, self._query_task = self._query_task, None
        if query_task is not None:
            query_task.cancel()
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self.mqtt_client is not None:
            with contextlib.suppress(Exception):
                self.mqtt_client.close()
            self.mqtt_client = None
        self.connected = False

    async def async_connect_and_run(self: HisenseTvClient) -> None:
        """Starts the persistent supervised MQTT session using the access token as password.

        Raises ``FileNotFoundError``/``ssl.SSLError`` immediately when the client
        certificate cannot be loaded, so setup can surface ``ConfigEntryNotReady``.
        """
        sync_fn = self.__dict__.get("connect_and_run")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn()
            if asyncio.iscoroutine(res):
                await res
            return

        if not self.access_token or not self.client_id or not self.username:
            _LOGGER.error("[%s] Cannot connect to TV: missing credentials (client_id, username, or access_token)", self.ip)
            self._dispatch_auth_failed()
            return
        async with self._reconnect_lock:
            ssl_ctx = await self._async_build_ssl_context()
            await self._async_stop_session()
            self._loop = asyncio.get_running_loop()
            _LOGGER.debug("[%s] Starting background MQTT connection task", self.ip)
            self._mqtt_task = self._loop.create_task(
                self._mqtt_session_loop(
                    self.client_id,
                    self.username,
                    self.access_token,
                    ssl_ctx,
                    reconnect=True,
                    standard=True,
                ),
                name=f"hisense_vidaa_mqtt_{self.ip}",
            )
            self._token_manager.start_token_watch()

    async def async_open_pairing_session(
        self: HisenseTvClient,
        client_id: str,
        username: str,
        password: str,
        timeout: float = 10.0,
    ) -> None:
        """Opens a single (non-reconnecting) session for PIN pairing and awaits CONNACK.

        Raises the CONNACK rejection immediately (so the profile cascade can fall
        back) or a timeout error. The session stays open until ``async_disconnect``.
        """
        ssl_ctx = await self._async_build_ssl_context()
        await self._async_stop_session()
        loop = asyncio.get_running_loop()
        self._loop = loop
        ready: asyncio.Future = loop.create_future()
        self._mqtt_task = loop.create_task(
            self._mqtt_session_loop(
                client_id, username, password, ssl_ctx, reconnect=False, standard=False, ready=ready
            ),
            name=f"hisense_vidaa_pairing_{self.ip}",
        )
        try:
            await asyncio.wait_for(asyncio.shield(ready), timeout=timeout)
        except TimeoutError:
            await self._async_stop_session()
            raise Exception("Cannot connect to TV MQTT Broker (connection timeout)") from None
        except Exception:
            await self._async_stop_session()
            raise

    async def async_ensure_connected(self: HisenseTvClient, min_interval: float = 5.0) -> bool:
        """Ensures the MQTT session is running, rate-limiting reconnect attempts."""
        sync_fn = self.__dict__.get("ensure_connected")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn(min_interval=min_interval)
            if asyncio.iscoroutine(res):
                return await res
            return bool(res)

        if self.connected and self.mqtt_client:
            return True
        now = time.time()
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
            await self.async_check_and_refresh_token()
            await self.async_connect_and_run()
            return True
        except Exception as e:
            _LOGGER.error("[%s] Error during ensure_connected: %s", self.ip, e)
            return False

    def ensure_connected(self: HisenseTvClient, min_interval: float = 5.0) -> bool:
        """Synchronous wrapper for async_ensure_connected (CLI usage)."""
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                raise RuntimeError("Synchronous ensure_connected called from event loop")
            return asyncio.run_coroutine_threadsafe(
                self.async_ensure_connected(min_interval), loop
            ).result(timeout=10)
        return asyncio.run(self.async_ensure_connected(min_interval))

    # ------------------------------------------------------------------
    # Publish / subscribe / query
    # ------------------------------------------------------------------
    async def async_publish(self: HisenseTvClient, topic: str, payload: Any = None) -> bool:
        """Publishes a message on the live session (returns False when disconnected)."""
        adapter = self.mqtt_client
        if not adapter:
            return False
        try:
            await adapter.async_publish(topic, payload)
            return True
        except Exception as err:
            _LOGGER.debug("[%s] Publish to %s failed: %s", self.ip, topic, err)
            return False

    async def async_subscribe(self: HisenseTvClient, topics: Any) -> bool:
        """Subscribes on the live session (returns False when disconnected)."""
        adapter = self.mqtt_client
        if not adapter:
            return False
        try:
            await adapter.async_subscribe(topics)
            return True
        except Exception as err:
            _LOGGER.debug("[%s] Subscribe to %s failed: %s", self.ip, topics, err)
            return False

    async def async_query(
        self: HisenseTvClient, publish_topic: str, subscribe_topic: str, payload: str | None = None, timeout: float = 10.0
    ) -> Any:
        """Publishes a query and awaits the JSON response on ``subscribe_topic``."""
        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_queries.setdefault(subscribe_topic, []).append(future)
        try:
            await self.async_subscribe(subscribe_topic)
            await self.async_publish(publish_topic, payload)
            result = await asyncio.wait_for(future, timeout=timeout)
            return json.loads(result)
        except Exception as error:
            _LOGGER.error("Error querying %s: %s", publish_topic, error)
            raise
        finally:
            waiters = self._pending_queries.get(subscribe_topic)
            if waiters and future in waiters:
                waiters.remove(future)
                if not waiters:
                    self._pending_queries.pop(subscribe_topic, None)

    async def async_disconnect(self: HisenseTvClient) -> None:
        """Cleanly stops the MQTT session and all background tasks."""
        self._token_manager.stop_token_watch()
        self._token_manager.cancel_rejected_retry()
        await self._async_stop_session()
        for task in list(self._background_tasks):
            task.cancel()

    # ------------------------------------------------------------------
    # Synchronous compatibility wrappers (standalone CLI only)
    # ------------------------------------------------------------------
    def connect_and_run(self: HisenseTvClient) -> None:
        """Starts the MQTT session; for standalone CLI tools outside HA."""
        loop = self._loop
        if loop is None or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                import threading

                loop = asyncio.new_event_loop()
                self._loop = loop
                t = threading.Thread(
                    target=loop.run_forever, daemon=True, name=f"hisense_loop_{self.ip}"
                )
                t.start()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(self.async_connect_and_run(), loop).result(timeout=10)
        else:
            loop.run_until_complete(self.async_connect_and_run())

    def disconnect(self: HisenseTvClient) -> None:
        """Non-blocking disconnect: schedules teardown on the client's loop."""
        loop = self._loop
        if loop is None or loop.is_closed():
            self.mqtt_client = None
            self.connected = False
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(self.async_disconnect())
        elif loop.is_running():
            asyncio.run_coroutine_threadsafe(self.async_disconnect(), loop).result(timeout=10)
        else:
            loop.run_until_complete(self.async_disconnect())
