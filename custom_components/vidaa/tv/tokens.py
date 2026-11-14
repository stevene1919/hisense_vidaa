"""Token lifecycle and clock synchronization mixin for HisenseTvClient."""

from __future__ import annotations

import asyncio
import inspect
import logging
import sys
import time
from typing import TYPE_CHECKING, Any

from ..protocol.auth import async_perform_token_refresh, is_token_expired
from ..tv.fingerprint import get_tv_timestamp

if TYPE_CHECKING:
    from ..client import HisenseTvClient

_LOGGER = logging.getLogger(__name__)


def _get_perform_token_refresh_fn() -> Any:
    cl = sys.modules.get("custom_components.vidaa.client") or sys.modules.get("custom_components.hisense_vidaa.client")
    if cl and hasattr(cl, "async_perform_token_refresh"):
        return cl.async_perform_token_refresh
    return async_perform_token_refresh


def _get_is_token_expired_fn() -> Any:
    cl = sys.modules.get("custom_components.vidaa.client") or sys.modules.get("custom_components.hisense_vidaa.client")
    if cl and hasattr(cl, "is_token_expired"):
        return cl.is_token_expired
    return is_token_expired


def _get_tv_timestamp_fn() -> Any:
    cl = sys.modules.get("custom_components.vidaa.client") or sys.modules.get("custom_components.hisense_vidaa.client")
    if cl and hasattr(cl, "get_tv_timestamp"):
        return cl.get_tv_timestamp
    return get_tv_timestamp


def _run_sync(coro: Any) -> Any:
    """Runs a coroutine to completion from synchronous (CLI) code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise RuntimeError("Synchronous client API called from a running event loop; use the async_* variant")


class TvTokenLifecycleMixin:
    """Delegator properties and methods for token lifecycle and TV clock sync."""

    # --------------------------------------------------------------------------
    # Backward compatibility properties for TokenLifecycleManager
    # --------------------------------------------------------------------------
    @property
    def _refresh_lock(self: HisenseTvClient) -> asyncio.Lock:
        return self._token_manager.refresh_lock

    @property
    def _refreshing_token(self: HisenseTvClient) -> bool:
        return self._token_manager.refreshing_token

    @_refreshing_token.setter
    def _refreshing_token(self: HisenseTvClient, value: bool) -> None:
        self._token_manager.refreshing_token = value

    @property
    def _last_refresh_attempt(self: HisenseTvClient) -> float:
        return self._token_manager.last_refresh_attempt

    @_last_refresh_attempt.setter
    def _last_refresh_attempt(self: HisenseTvClient, value: float) -> None:
        self._token_manager.last_refresh_attempt = value

    @property
    def _last_awake_refresh_attempt(self: HisenseTvClient) -> float:
        return self._token_manager.last_awake_refresh_attempt

    @_last_awake_refresh_attempt.setter
    def _last_awake_refresh_attempt(self: HisenseTvClient, value: float) -> None:
        self._token_manager.last_awake_refresh_attempt = value

    @property
    def _rejected_refresh_failures(self: HisenseTvClient) -> int:
        return self._token_manager.rejected_refresh_failures

    @_rejected_refresh_failures.setter
    def _rejected_refresh_failures(self: HisenseTvClient, value: int) -> None:
        self._token_manager.rejected_refresh_failures = value

    @property
    def _broker_rejection_failures(self: HisenseTvClient) -> int:
        return self._token_manager.broker_rejection_failures

    @_broker_rejection_failures.setter
    def _broker_rejection_failures(self: HisenseTvClient, value: int) -> None:
        self._token_manager.broker_rejection_failures = value

    @property
    def _last_refresh_connect_rc(self: HisenseTvClient) -> int | None:
        return self._token_manager.last_refresh_connect_rc

    @_last_refresh_connect_rc.setter
    def _last_refresh_connect_rc(self: HisenseTvClient, value: int | None) -> None:
        self._token_manager.last_refresh_connect_rc = value

    @property
    def _token_watch(self: HisenseTvClient) -> asyncio.Task | None:
        return self._token_manager.token_watch_task

    @property
    def _token_watch_closed(self: HisenseTvClient) -> bool:
        return self._token_manager.token_watch_closed

    @_token_watch_closed.setter
    def _token_watch_closed(self: HisenseTvClient, value: bool) -> None:
        self._token_manager.token_watch_closed = value

    def _start_token_watch(self: HisenseTvClient) -> None:
        self._token_manager.start_token_watch()

    def _stop_token_watch(self: HisenseTvClient) -> None:
        self._token_manager.stop_token_watch()

    def _token_watch_tick(self: HisenseTvClient) -> None:
        self._token_manager._token_watch_tick()

    def _maybe_refresh_while_awake(self: HisenseTvClient) -> None:
        self._token_manager.maybe_refresh_while_awake()

    def _proactive_token_refresh(self: HisenseTvClient) -> None:
        self._token_manager.proactive_token_refresh()

    def _schedule_rejected_retry(self: HisenseTvClient, delay: float) -> None:
        self._token_manager.schedule_rejected_retry(delay)

    def _rejected_retry_fire(self: HisenseTvClient) -> None:
        self._token_manager._rejected_retry_fire()

    def _cancel_rejected_retry(self: HisenseTvClient) -> None:
        self._token_manager.cancel_rejected_retry()

    def _refresh_token_and_update_creds(self: HisenseTvClient) -> None:
        self._token_manager.refresh_token_and_update_creds()

    # --------------------------------------------------------------------------
    # Clock Synchronization & Token Refresh
    # --------------------------------------------------------------------------
    async def async_sync_clock(self: HisenseTvClient, timeout: float = 2.0) -> int | None:
        """Queries TV UPnP HTTP header to synchronize system clocks and calculate drift offset."""
        sync_fn = self.__dict__.get("sync_clock")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn(timeout=timeout)
            if inspect.iscoroutine(res):
                return await res
            return res

        tv_timestamp = await self.upnp.async_get_tv_timestamp(timeout=timeout)
        if tv_timestamp is None:
            try:
                fn = _get_tv_timestamp_fn()
                if inspect.iscoroutinefunction(fn):
                    tv_timestamp = await fn(self.ip, timeout=timeout)
                else:
                    tv_timestamp = await asyncio.to_thread(fn, self.ip, timeout=timeout)
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

    def sync_clock(self: HisenseTvClient, timeout: float = 2.0) -> int | None:
        """Synchronous (CLI) wrapper for async_sync_clock."""
        return _run_sync(self.async_sync_clock(timeout))

    async def async_check_and_refresh_token(
        self: HisenseTvClient,
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
            exp_fn = _get_is_token_expired_fn()
            if not exp_fn(
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
        self: HisenseTvClient,
        force: bool = False,
        margin_seconds: int = 0,
        clock_offset: int | None = None,
    ) -> bool:
        """Synchronous (CLI) wrapper for async_check_and_refresh_token."""
        if not self.refresh_token:
            return False
        return _run_sync(self.async_check_and_refresh_token(force, margin_seconds, clock_offset))

    async def async_refresh_tokens(self: HisenseTvClient) -> bool:
        """Connects with the refresh token to obtain a fresh access token."""
        sync_fn = self.__dict__.get("refresh_tokens")
        if sync_fn is not None and callable(sync_fn):
            res = sync_fn()
            if asyncio.iscoroutine(res):
                return await res
            return bool(res)

        await self.async_sync_clock(timeout=2.0)

        had_session = self._mqtt_task is not None or self.mqtt_client is not None
        if had_session:
            await self._async_stop_session()

        refresh_status: dict[str, Any] = {}
        perform_fn = _get_perform_token_refresh_fn()
        updated_data = await perform_fn(
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

    def refresh_tokens(self: HisenseTvClient) -> bool:
        """Synchronous (CLI) wrapper for async_refresh_tokens."""
        return _run_sync(self.async_refresh_tokens())
