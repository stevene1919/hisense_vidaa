"""Token lifecycle, background refresh, and connection retry management for Hisense VIDAA TV."""

from __future__ import annotations

import contextlib
import logging
import threading
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
        self.refresh_lock = threading.Lock()
        self.refreshing_token: bool = False
        self.last_refresh_attempt: float = 0.0
        self.token_watch: threading.Timer | None = None
        self.token_watch_closed: bool = False
        self.awake_refresh_failures: int = 0
        self.last_awake_refresh_attempt: float = 0.0
        self.rejected_refresh_failures: int = 0
        self.rejected_retry_timer: threading.Timer | None = None
        self.broker_rejection_failures: int = 0
        self.last_refresh_connect_rc: int | None = None

    def start_token_watch(self) -> None:
        """Start the periodic token watch timer."""
        with self.refresh_lock:
            if self.token_watch_closed or self.token_watch is not None:
                return
            timer = threading.Timer(self.TOKEN_WATCH_INTERVAL, self._token_watch_tick)
            timer.daemon = True
            self.token_watch = timer
            timer.start()

    def stop_token_watch(self) -> None:
        """Stop the periodic token watch timer."""
        with self.refresh_lock:
            self.token_watch_closed = True
            timer, self.token_watch = self.token_watch, None
        if timer:
            with contextlib.suppress(Exception):
                timer.cancel()

    def _token_watch_tick(self) -> None:
        with self.refresh_lock:
            self.token_watch = None
        try:
            self.client._maybe_refresh_while_awake()
        except Exception as e:
            _LOGGER.debug("[%s] Token watch error: %s", self.client.ip, e)
        self.start_token_watch()

    def can_refresh_in_standby(self) -> bool:
        """Whether a token refresh may run while the TV is in standby (``refresh_in_standby`` option).

        TVs that keep their MQTT broker up when switched off (fake sleep) answer gettoken there, too. A refresh
        drops the main connection and a failed one restores it with the current access token, so in standby it
        is attempted only while that token is still valid: once it has expired the open connection (which keeps
        working) could not be re-established, and it is left alone until the TV wakes.
        """
        client = self.client
        return bool(getattr(client, "refresh_in_standby", False)) and not is_token_expired(
            client.access_token_time, client.access_token_duration
        )

    def maybe_refresh_while_awake(self) -> None:
        """Renews a near-expiry access token once the TV is awake (with backoff on failure)."""
        client = self.client
        if not (client.connected and client.access_token and client.refresh_token):
            return
        if not client.is_on and not self.can_refresh_in_standby():
            return
        if not is_token_expired(client.access_token_time, client.access_token_duration, margin_seconds=43200):
            return
        backoff = min(600 * (2 ** self.awake_refresh_failures), 6 * 3600)
        now = time.time()
        with self.refresh_lock:
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
            ok = client.refresh_tokens()
        except Exception as e:
            _LOGGER.warning("[%s] Token refresh while awake failed: %s", client.ip, e)
        finally:
            with self.refresh_lock:
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

    def proactive_token_refresh(self) -> None:
        """Proactively refreshes the token if access token is within 12h of expiration."""
        client = self.client
        try:
            if client.access_token and is_token_expired(client.access_token_time, client.access_token_duration, margin_seconds=43200):
                time.sleep(self.PROACTIVE_REFRESH_SETTLE_SECONDS)
                if not client.is_on and not self.can_refresh_in_standby():
                    _LOGGER.info(
                        "[%s] Access token is near expiration, but the TV is in standby; deferring token refresh until it is awake",
                        client.ip,
                    )
                    return
                current_time = time.time()
                with self.refresh_lock:
                    should_refresh = not self.refreshing_token and (current_time - self.last_refresh_attempt > 60)
                    if should_refresh:
                        self.refreshing_token = True
                        self.last_refresh_attempt = current_time
                if should_refresh:
                    _LOGGER.info("[%s] Access token is near expiration (<12h remaining). Proactively renewing tokens...", client.ip)
                    client.refresh_tokens()
        except Exception as e:
            _LOGGER.debug("[%s] Proactive token refresh check error: %s", client.ip, e)
        finally:
            with self.refresh_lock:
                self.refreshing_token = False

    def handle_auth_rejection(self, rc: int) -> None:
        """Handles MQTT auth rejection (rc 4 or 5) on connect."""
        client = self.client
        if client.refresh_token and not is_token_expired(client.refresh_token_time, client.refresh_token_duration):
            current_time = time.time()
            with self.refresh_lock:
                retry_after = min(60 * (2 ** self.rejected_refresh_failures), 1800)
                should_refresh = not self.refreshing_token and (current_time - self.last_refresh_attempt > retry_after)
                if should_refresh:
                    self.refreshing_token = True
                    self.last_refresh_attempt = current_time
            if should_refresh:
                _LOGGER.info("[%s] Authentication failed on connect. Refreshing token in background...", client.ip)
                threading.Thread(target=client._refresh_token_and_update_creds, daemon=True).start()
            else:
                client._schedule_rejected_retry(max(5.0, retry_after - (current_time - self.last_refresh_attempt)))
        else:
            _LOGGER.warning("[%s] MQTT authentication rejected and no valid refresh token available. Reauthentication required.", client.ip)
            client._dispatch_auth_failed()

    def schedule_rejected_retry(self, delay: float) -> None:
        with self.refresh_lock:
            if self.rejected_retry_timer is not None:
                return
            timer = threading.Timer(delay, self.client._rejected_retry_fire)
            timer.daemon = True
            self.rejected_retry_timer = timer
            timer.start()
        _LOGGER.debug("[%s] Next reconnect attempt in %.0f s", self.client.ip, delay)

    def _rejected_retry_fire(self) -> None:
        with self.refresh_lock:
            self.rejected_retry_timer = None
        try:
            self.client.connect_and_run()
        except Exception as e:
            _LOGGER.debug("[%s] Scheduled reconnect failed: %s", self.client.ip, e)

    def cancel_rejected_retry(self) -> None:
        with self.refresh_lock:
            timer, self.rejected_retry_timer = self.rejected_retry_timer, None
        if timer:
            with contextlib.suppress(Exception):
                timer.cancel()

    def refresh_token_and_update_creds(self) -> None:
        client = self.client
        try:
            if client.check_and_refresh_token(force=True):
                _LOGGER.info("[%s] Token successfully refreshed on connection failure.", client.ip)
                self.rejected_refresh_failures = 0
                self.broker_rejection_failures = 0
            else:
                self.rejected_refresh_failures += 1
                if self.last_refresh_connect_rc in (4, 5):
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
            with self.refresh_lock:
                self.refreshing_token = False
