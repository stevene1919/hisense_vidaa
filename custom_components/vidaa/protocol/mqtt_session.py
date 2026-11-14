"""MQTT session adapter and standard topic definitions (aiomqtt)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiomqtt import Client

_LOGGER = logging.getLogger(__name__)

MQTT_PORT = 36669
AUTH_REJECTION_CODES = (4, 5, 134, 135)
RECONNECT_MIN_DELAY = 2.0
RECONNECT_MAX_DELAY = 30.0
DISCONNECT_DEBOUNCE = 2.0

__all__ = [
    "AUTH_REJECTION_CODES",
    "DISCONNECT_DEBOUNCE",
    "MQTT_PORT",
    "RECONNECT_MAX_DELAY",
    "RECONNECT_MIN_DELAY",
    "MqttSessionAdapter",
    "decode_mqtt_payload",
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


def decode_mqtt_payload(payload: Any) -> str:
    """Decodes raw MQTT byte payloads to unicode strings."""
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode("utf-8", errors="ignore")
    if payload is None:
        return ""
    return str(payload)


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
