"""MQTT client connection, lifecycle, and topic subscription management."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import paho.mqtt.client as mqtt

from .auth import apply_mqtt_tls
from .dispatcher import dispatch_incoming_mqtt_message

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def build_mqtt_client(
    client_id: str,
    username: str,
    password: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    use_ssl: bool = True,
    on_connect: Callable | None = None,
    on_message: Callable | None = None,
    on_disconnect: Callable | None = None,
) -> mqtt.Client:
    """Builds and configures an authenticated Paho MQTT client."""
    client = mqtt.Client(
        client_id=client_id,
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
    )
    client.reconnect_delay_set(min_delay=2, max_delay=30)

    apply_mqtt_tls(
        client=client,
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        verify_ssl=verify_ssl,
        use_ssl=use_ssl,
    )
    client.username_pw_set(username=username, password=password)

    if on_connect:
        client.on_connect = on_connect
    if on_message:
        client.on_message = on_message
    if on_disconnect:
        client.on_disconnect = on_disconnect

    return client


def subscribe_standard_tv_topics(
    client: mqtt.Client,
    broadcast_basepath: str,
    mobile_basepath: str,
) -> None:
    """Subscribes to standard VIDAA broadcast and mobile unicast telemetry topics."""
    client.subscribe([
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
    ])


def clean_disconnect_mqtt_client(client: mqtt.Client | None) -> None:
    """Safely unbinds callbacks, stops background loop, and disconnects client."""
    if not client:
        return
    try:
        client.on_connect = None
        client.on_disconnect = None
        client.on_message = None
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        _LOGGER.debug("Error during MQTT client disconnect: %s", e)
    with contextlib.suppress(Exception):
        client.loop_stop()


class ConnectionManagerMixin:
    """Mixin providing MQTT connection lifecycle, loop orchestration, and async query dispatching."""

    def _apply_tls(self: HisenseTvClient, client: mqtt.Client) -> None:
        """Applies TLS certificate configuration to an MQTT client instance."""
        apply_mqtt_tls(
            client=client,
            certfile=self.certfile,
            keyfile=self.keyfile,
            ca_cert=self.ca_cert,
            verify_ssl=self.verify_ssl,
            use_ssl=self.use_ssl,
        )

    def create_mqtt_client(self: HisenseTvClient, client_id: str, username: str, password: str) -> mqtt.Client:
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

    def _safe_set_future_result(self: HisenseTvClient, future: asyncio.Future | None, result: Any) -> None:
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_result, result)
            else:
                future.set_result(result)

    def _safe_set_future_exception(self: HisenseTvClient, future: asyncio.Future | None, exc: Exception) -> None:
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_exception, exc)
            else:
                future.set_exception(exc)

    def _on_connect(self: HisenseTvClient, client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
        if rc == 0:
            self.connected = True
            _LOGGER.info("[%s] Connected to TV MQTT broker", self.ip)
            self._dispatch_connected()
            subscribe_standard_tv_topics(
                client=client,
                broadcast_basepath=self.topicBrcsBasepath,
                mobile_basepath=self.topicMobiBasepath,
            )
            if self.refresh_token and not self._token_manager.refreshing_token:
                self._token_manager.proactive_token_refresh()

            self._query_timer = threading.Timer(0.5, self.query_initial_state)
            self._query_timer.daemon = True
            self._query_timer.start()
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
                self._token_manager.handle_auth_rejection(rc)

    def _on_disconnect(self: HisenseTvClient, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self.connected = False
        _LOGGER.debug("[%s] Disconnected from TV MQTT broker (rc: %d)", self.ip, rc)
        if (self._auth_future and not self._auth_future.done()) or (self._auth_code_future and not self._auth_code_future.done()):
            with contextlib.suppress(Exception):
                client.loop_stop()
        self._dispatch_disconnected()

    def _on_message(self: HisenseTvClient, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        payload = msg.payload.decode("utf-8", errors="ignore")
        dispatch_incoming_mqtt_message(self, topic=msg.topic, payload=payload)

    def connect_and_run(self: HisenseTvClient) -> None:
        """Main client connection loop using the access token as password."""
        if not self.access_token or not self.client_id or not self.username:
            _LOGGER.error("[%s] Cannot connect to TV: missing credentials (client_id, username, or access_token)", self.ip)
            return

        # Serialize concurrent callers (ensure_connected / _rejected_retry_fire /
        # refresh_tokens) so two threads cannot tear down and rebuild the MQTT
        # client at the same time.
        with self._reconnect_lock:
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
            self._token_manager.start_token_watch()

    def ensure_connected(self: HisenseTvClient, min_interval: float = 5.0) -> bool:
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

    async def async_query(self: HisenseTvClient, pub_topic: str, sub_topic: str, payload: str | None = None) -> Any:
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

    def disconnect(self: HisenseTvClient) -> None:
        """Cleanly disconnects the MQTT client and stops the background network thread."""
        self._token_manager.stop_token_watch()
        self._token_manager.cancel_rejected_retry()
        timer, self._query_timer = self._query_timer, None
        if timer:
            with contextlib.suppress(Exception):
                timer.cancel()
        if self.mqtt_client:
            clean_disconnect_mqtt_client(self.mqtt_client)
            self.mqtt_client = None
            self.connected = False
