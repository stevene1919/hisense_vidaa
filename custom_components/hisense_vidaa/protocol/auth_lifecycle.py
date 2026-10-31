"""Token lifecycle, background refresh, and connection retry management for Hisense VIDAA TV."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING

from .auth import is_token_expired

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


class TokenLifecycleManager:
    """Manages proactive and reactive token renewal and exponential retry backoff."""

    TOKEN_WATCH_INTERVAL = 300
    PROACTIVE_REFRESH_SETTLE_SECONDS = 3.0
    MAX_BROKER_REJECTION_ATTEMPTS = 3

    def __init__(self, client: HisenseTvClient) -> None:
        self.client = client
        self.refresh_lock = asyncio.Lock()
        self.refreshing_token: bool = False
        self.last_refresh_attempt: float = 0.0
        self.token_watch_task: asyncio.Task | None = None
        self.token_watch_closed: bool = False
        self.awake_refresh_failures: int = 0
        self.last_awake_refresh_attempt: float = 0.0
        self.rejected_refresh_failures: int = 0
        self.rejected_retry_task: asyncio.Task | None = None
        self.broker_rejection_failures: int = 0
        self.last_refresh_connect_rc: int | None = None

    def start_token_watch(self) -> None:
        """Start the periodic token watch loop task."""
        self.token_watch_closed = False
        if self.token_watch_task is not None and not self.token_watch_task.done():
            return
        with contextlib.suppress(RuntimeError):
            self.token_watch_task = asyncio.create_task(self._token_watch_loop())

    def stop_token_watch(self) -> None:
        """Stop the periodic token watch loop task."""
        self.token_watch_closed = True
        if self.token_watch_task is not None:
            self.token_watch_task.cancel()
            self.token_watch_task = None

    async def _token_watch_loop(self) -> None:
        """Runs periodic checks for token expiry while awake."""
        while not self.token_watch_closed:
            await asyncio.sleep(self.TOKEN_WATCH_INTERVAL)
            if self.token_watch_closed:
                break
            try:
                await self.async_maybe_refresh_while_awake()
            except Exception as e:
                _LOGGER.debug("[%s] Token watch error: %s", self.client.ip, e)

    def _token_watch_tick(self) -> None:
        """Synchronous tick helper for manual testing or timer callbacks."""
        try:
            loop = asyncio.get_running_loop()
            self._watch_tick_task = loop.create_task(self.async_maybe_refresh_while_awake())
        except RuntimeError:
            asyncio.run(self.async_maybe_refresh_while_awake())

    def can_refresh_in_standby(self) -> bool:
        """Whether a token refresh may run while the TV is in standby (``refresh_in_standby`` option)."""
        client = self.client
        return bool(getattr(client, "refresh_in_standby", False)) and not is_token_expired(
            client.access_token_time,
            client.access_token_duration,
            clock_offset=client.clock_offset,
        )

    async def async_maybe_refresh_while_awake(self) -> None:
        """Renews a near-expiry access token once the TV is awake (with backoff on failure)."""
        client = self.client
        if not (client.connected and client.access_token and client.refresh_token):
            return
        if not client.is_on and not self.can_refresh_in_standby():
            return
        if not is_token_expired(
            client.access_token_time,
            client.access_token_duration,
            margin_seconds=43200,
            clock_offset=client.clock_offset,
        ):
            return

        backoff = min(600 * (2 ** self.awake_refresh_failures), 6 * 3600)
        now = time.time()
        async with self.refresh_lock:
            if (
                self.refreshing_token
                or now - self.last_awake_refresh_attempt < backoff
                or now - self.last_refresh_attempt < 60
            ):
                return
            self.refreshing_token = True
            self.last_refresh_attempt = now
            self.last_awake_refresh_attempt = now

        ok = False
        try:
            _LOGGER.info("[%s] TV is awake and the access token is near expiration. Renewing tokens...", client.ip)
            ok = await client.async_refresh_tokens()
        except Exception as e:
            _LOGGER.warning("[%s] Token refresh while awake failed: %s", client.ip, e)
        finally:
            async with self.refresh_lock:
                self.refreshing_token = False

        if ok:
            self.awake_refresh_failures = 0
            _LOGGER.info("[%s] Tokens renewed successfully", client.ip)
        else:
            self.awake_refresh_failures += 1
            _LOGGER.warning(
                "[%s] Token refresh failed while the TV is awake (attempt %d); next retry in %d min",
                client.ip,
                self.awake_refresh_failures,
                min(600 * (2 ** self.awake_refresh_failures), 6 * 3600) // 60,
            )

    def maybe_refresh_while_awake(self) -> None:
        """Synchronous wrapper for async_maybe_refresh_while_awake."""
        try:
            loop = asyncio.get_running_loop()
            self._awake_refresh_task = loop.create_task(self.async_maybe_refresh_while_awake())
        except RuntimeError:
            asyncio.run(self.async_maybe_refresh_while_awake())

    async def async_proactive_token_refresh(self) -> None:
        """Proactively refreshes the token if access token is within 12h of expiration."""
        client = self.client
        should_refresh = False
        try:
            if client.access_token and is_token_expired(
                client.access_token_time,
                client.access_token_duration,
                margin_seconds=43200,
                clock_offset=client.clock_offset,
            ):
                await asyncio.sleep(self.PROACTIVE_REFRESH_SETTLE_SECONDS)
                if not client.is_on and not self.can_refresh_in_standby():
                    _LOGGER.info(
                        "[%s] Access token is near expiration, but the TV is in standby; deferring token refresh until it is awake",
                        client.ip,
                    )
                    return
                current_time = time.time()
                async with self.refresh_lock:
                    should_refresh = not self.refreshing_token and (current_time - self.last_refresh_attempt > 60)
                    if should_refresh:
                        self.refreshing_token = True
                        self.last_refresh_attempt = current_time
                if should_refresh:
                    _LOGGER.info("[%s] Access token is near expiration (<12h remaining). Proactively renewing tokens...", client.ip)
                    await client.async_refresh_tokens()
        except Exception as e:
            _LOGGER.debug("[%s] Proactive token refresh check error: %s", client.ip, e)
        finally:
            async with self.refresh_lock:
                if should_refresh:
                    self.refreshing_token = False

    def proactive_token_refresh(self) -> None:
        """Synchronous wrapper for async_proactive_token_refresh."""
        try:
            loop = asyncio.get_running_loop()
            self._proactive_refresh_task = loop.create_task(self.async_proactive_token_refresh())
        except RuntimeError:
            asyncio.run(self.async_proactive_token_refresh())

    async def async_handle_auth_rejection(self, rc: int) -> None:
        """Handles MQTT auth rejection (rc 4, 5, 134, 135) on connect."""
        client = self.client
        with contextlib.suppress(Exception):
            await client.async_sync_clock(timeout=2.0)

        if client.refresh_token and not is_token_expired(
            client.refresh_token_time,
            client.refresh_token_duration,
            clock_offset=client.clock_offset,
        ):
            current_time = time.time()
            retry_after = min(60 * (2 ** self.rejected_refresh_failures), 1800)
            should_refresh = False
            async with self.refresh_lock:
                should_refresh = not self.refreshing_token and (current_time - self.last_refresh_attempt > retry_after)
                if should_refresh:
                    self.refreshing_token = True
                    self.last_refresh_attempt = current_time
            if should_refresh:
                _LOGGER.info("[%s] Authentication failed on connect. Refreshing token in background...", client.ip)
                self.auth_refresh_task = asyncio.create_task(self.async_refresh_token_and_update_creds())
            else:
                self.client._schedule_rejected_retry(max(5.0, retry_after - (current_time - self.last_refresh_attempt)))
        else:
            _LOGGER.warning("[%s] MQTT authentication rejected and no valid refresh token available. Reauthentication required.", client.ip)
            client._dispatch_auth_failed()

    def handle_auth_rejection(self, rc: int) -> None:
        """Synchronous wrapper for async_handle_auth_rejection."""
        try:
            loop = asyncio.get_running_loop()
            self._handle_rejection_task = loop.create_task(self.async_handle_auth_rejection(rc))
        except RuntimeError:
            asyncio.run(self.async_handle_auth_rejection(rc))

    def schedule_rejected_retry(self, delay: float) -> None:
        """Schedules a delayed reconnection attempt after rejection."""
        self.cancel_rejected_retry()
        with contextlib.suppress(RuntimeError):
            self.rejected_retry_task = asyncio.create_task(self._rejected_retry_runner(delay))
        _LOGGER.debug("[%s] Next reconnect attempt in %.0f s", self.client.ip, delay)

    async def _rejected_retry_runner(self, delay: float) -> None:
        """Waits delay seconds and triggers reconnection."""
        await asyncio.sleep(delay)
        self.rejected_retry_task = None
        try:
            await self.client.async_connect_and_run()
        except Exception as e:
            _LOGGER.debug("[%s] Scheduled reconnect failed: %s", self.client.ip, e)

    def _rejected_retry_fire(self) -> None:
        """Immediate retry trigger for tests or manual invocation."""
        try:
            loop = asyncio.get_running_loop()
            self._retry_fire_task = loop.create_task(self.client.async_connect_and_run())
        except RuntimeError:
            asyncio.run(self.client.async_connect_and_run())

    def cancel_rejected_retry(self) -> None:
        """Cancels any pending rejection retry task."""
        if self.rejected_retry_task is not None:
            self.rejected_retry_task.cancel()
            self.rejected_retry_task = None

    async def async_refresh_token_and_update_creds(self) -> None:
        """Attempts token refresh and dispatches reauth if broker repeatedly rejects."""
        client = self.client
        try:
            if await client.async_check_and_refresh_token(force=True):
                _LOGGER.info("[%s] Token successfully refreshed on connection failure.", client.ip)
                self.rejected_refresh_failures = 0
                self.broker_rejection_failures = 0
            else:
                self.rejected_refresh_failures += 1
                if self.last_refresh_connect_rc in (4, 5, 134, 135):
                    self.broker_rejection_failures += 1
                else:
                    self.broker_rejection_failures = 0

                _LOGGER.warning(
                    "[%s] Token refresh after rejected connection failed (attempt %d); next retry in %d min",
                    client.ip,
                    self.rejected_refresh_failures,
                    min(60 * (2 ** self.rejected_refresh_failures), 1800) // 60,
                )
                if self.broker_rejection_failures >= self.MAX_BROKER_REJECTION_ATTEMPTS:
                    _LOGGER.warning(
                        "[%s] Refresh token actively rejected by broker %d times (rc: %s). "
                        "TV likely invalidated all tokens (firmware update / power-cycle). "
                        "Triggering reauthentication.",
                        client.ip,
                        self.broker_rejection_failures,
                        self.last_refresh_connect_rc,
                    )
                    client._dispatch_auth_failed()
                    return
                if not client.refresh_token or is_token_expired(client.refresh_token_time, client.refresh_token_duration):
                    _LOGGER.warning("[%s] Refresh token is missing or expired. Reauthentication required.", client.ip)
                    client._dispatch_auth_failed()
        except Exception as e:
            _LOGGER.warning("[%s] Background token refresh error: %s", client.ip, e)
            if not client.refresh_token or is_token_expired(client.refresh_token_time, client.refresh_token_duration):
                client._dispatch_auth_failed()
        finally:
            async with self.refresh_lock:
                self.refreshing_token = False

    def refresh_token_and_update_creds(self) -> None:
        """Synchronous wrapper for async_refresh_token_and_update_creds."""
        try:
            loop = asyncio.get_running_loop()
            self._creds_refresh_task = loop.create_task(self.async_refresh_token_and_update_creds())
        except RuntimeError:
            asyncio.run(self.async_refresh_token_and_update_creds())
