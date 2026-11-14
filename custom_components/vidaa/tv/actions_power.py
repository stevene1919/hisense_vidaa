"""TV power actions and initial query operations for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def query_initial_state(client: HisenseTvClient, min_interval: float = 3.0) -> None:
    """Queries initial state, volume, source list, app list, and settings from TV."""
    if not (client.connected and client.mqtt_client):
        return

    now = time.time()
    with getattr(client, "_query_lock", contextlib.nullcontext()):
        last_time = getattr(client, "_last_initial_query_time", 0.0)
        if now - last_time < min_interval:
            _LOGGER.debug(
                "[%s] Suppressing duplicate query_initial_state call (%.2fs since last query)",
                client.ip,
                now - last_time,
            )
            return
        client._last_initial_query_time = now

        # The TV already broadcasts its live state automatically on
        # /remoteapp/mobile/broadcast/ui_service/state upon MQTT connect.
        # Do NOT publish actions/gettvstate: on VIDAA firmware, gettvstate
        # is the pairing challenge trigger that commands the TV to pop up a PIN.
        client.mqtt_client.publish(f"{client.topics.ui}actions/capability", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.platform}actions/getvolume", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.ui}actions/sourcelist", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.ui}actions/applist", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.platform}actions/getdeviceinfo", "")
        time.sleep(0.05)
        client.mqtt_client.publish(f"{client.topics.platform}actions/gettvinfo", "")


async def async_query_initial_state(client: HisenseTvClient, min_interval: float = 3.0) -> None:
    """Queries initial state, volume, source list, app list, and settings from TV asynchronously."""
    if not (client.connected and client.mqtt_client):
        return

    now = time.time()
    last_time = getattr(client, "_last_initial_query_time", 0.0)
    if now - last_time < min_interval:
        _LOGGER.debug(
            "[%s] Suppressing duplicate query_initial_state call (%.2fs since last query)",
            getattr(client, "ip", "unknown"),
            now - last_time,
        )
        return
    client._last_initial_query_time = now

    topics = [
        f"{client.topics.ui}actions/capability",
        f"{client.topics.platform}actions/getvolume",
        f"{client.topics.ui}actions/sourcelist",
        f"{client.topics.ui}actions/applist",
        f"{client.topics.platform}actions/getdeviceinfo",
        f"{client.topics.platform}actions/gettvinfo",
    ]
    for topic in topics:
        await client.async_publish(topic, "")
        await asyncio.sleep(0.05)


def turn_on_tv(
    client: HisenseTvClient,
    mac_targets: list[str] | None = None,
) -> None:
    """Powers on or wakes the TV safely and idempotently."""
    if mac_targets:
        client.send_wake_on_lan(mac_targets, ip=getattr(client, "ip", None))

    if client.connected:
        if not client.is_on and getattr(client, "has_active_signal", False) is not True:
            _LOGGER.debug(
                "[%s] TV connected in standby/fake_sleep. Sending KEY_POWER to wake screen",
                getattr(client, "ip", "unknown"),
            )
            client.send_key("KEY_POWER")
        else:
            client.is_on = True
            _LOGGER.debug(
                "[%s] TV already connected and running. Skipping KEY_POWER to prevent powering down",
                getattr(client, "ip", "unknown"),
            )
    else:
        _LOGGER.debug(
            "[%s] TV MQTT not connected. Attempting reconnect to send KEY_POWER",
            getattr(client, "ip", "unknown"),
        )
        try:
            if client.ensure_connected():
                for _ in range(50):
                    if client.connected:
                        client.send_key("KEY_POWER")
                        break
                    time.sleep(0.1)
        except Exception as e:
            _LOGGER.error(
                "[%s] Failed to reconnect and send KEY_POWER: %s",
                getattr(client, "ip", "unknown"),
                e,
            )

    client.is_on = True


async def async_turn_on_tv(
    client: HisenseTvClient,
    mac_targets: list[str] | None = None,
) -> None:
    """Powers on or wakes the TV safely and idempotently asynchronously."""
    if mac_targets:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, functools.partial(client.send_wake_on_lan, mac_targets, ip=getattr(client, "ip", None))
        )

    if client.connected:
        if not client.is_on and getattr(client, "has_active_signal", False) is not True:
            _LOGGER.debug(
                "[%s] TV connected in standby/fake_sleep. Sending KEY_POWER to wake screen",
                getattr(client, "ip", "unknown"),
            )
            await client.async_send_key("KEY_POWER")
        else:
            client.is_on = True
            _LOGGER.debug(
                "[%s] TV already connected and running. Skipping KEY_POWER to prevent powering down",
                getattr(client, "ip", "unknown"),
            )
    else:
        _LOGGER.debug(
            "[%s] TV MQTT not connected. Attempting reconnect to send KEY_POWER",
            getattr(client, "ip", "unknown"),
        )
        try:
            if await client.async_ensure_connected():
                for _ in range(50):
                    if client.connected:
                        await client.async_send_key("KEY_POWER")
                        break
                    await asyncio.sleep(0.1)
        except Exception as e:
            _LOGGER.error(
                "[%s] Failed to reconnect and send KEY_POWER: %s",
                getattr(client, "ip", "unknown"),
                e,
            )

    client.is_on = True


def turn_off_tv(client: HisenseTvClient) -> None:
    """Powers off the TV safely."""
    if client.connected and client.is_on:
        client.send_key("KEY_POWER")
    client.is_on = False


async def async_turn_off_tv(client: HisenseTvClient) -> None:
    """Powers off the TV safely asynchronously."""
    if client.connected and client.is_on:
        await client.async_send_key("KEY_POWER")
    client.is_on = False


class TvPowerActionsMixin:
    """Mixin providing TV power lifecycle and state query operations."""

    def query_initial_state(self) -> None:
        """Queries initial state, volume, source list, app list, and settings from TV."""
        query_initial_state(self)  # type: ignore[arg-type]

    async def async_query_initial_state(self, min_interval: float = 3.0) -> None:
        """Queries initial state, volume, source list, app list, and settings asynchronously."""
        await async_query_initial_state(self, min_interval=min_interval)  # type: ignore[arg-type]

    def turn_on(self, mac_targets: list[str] | None = None) -> None:
        """Powers on or wakes the TV safely and idempotently."""
        turn_on_tv(self, mac_targets=mac_targets)  # type: ignore[arg-type]

    async def async_turn_on(self, mac_targets: list[str] | None = None) -> None:
        """Powers on or wakes the TV safely and idempotently asynchronously."""
        await async_turn_on_tv(self, mac_targets=mac_targets)  # type: ignore[arg-type]

    def turn_off(self) -> None:
        """Powers off the TV safely."""
        turn_off_tv(self)  # type: ignore[arg-type]

    async def async_turn_off(self) -> None:
        """Powers off the TV safely asynchronously."""
        await async_turn_off_tv(self)  # type: ignore[arg-type]
