"""Unit tests for HisenseTvClient token lifecycle, proactive refresh, and clock drift."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.vidaa.client import HisenseTvClient
from custom_components.vidaa.protocol.auth import is_token_expired
from custom_components.vidaa.protocol.auth_lifecycle import TokenLifecycleManager


def test_check_and_refresh_token_not_expired():
    """Test token refresh is skipped when token is still within validity window."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        access_token="valid_token",
        access_token_time=now - 3600,  # 1 hour old (valid for 48h)
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - 3600,
        refresh_token_duration=30,
    )

    # Should return False without connecting to broker
    assert client.check_and_refresh_token(force=False) is False


def test_check_and_refresh_token_valid_within_12_hours_does_not_refresh():
    """Test token refresh is NOT triggered when token has <12 hours remaining but is still valid (>0s)."""
    now = int(time.time())
    # 2-day duration (172800s), issued 40 hours ago -> 8 hours (28800s) remaining
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        access_token="valid_token",
        access_token_time=now - (40 * 3600),
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (40 * 3600),
        refresh_token_duration=30,
    )

    # Must return False to avoid prompting PIN on TV while access token is still active
    assert client.check_and_refresh_token(force=False) is False


def test_check_and_refresh_token_missing_metadata_does_not_refresh():
    """Test token refresh is skipped when metadata (time or duration) is missing."""
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        access_token="valid_token",
        access_token_time=0,
        access_token_duration=0,
        refresh_token="valid_refresh",
    )

    assert client.check_and_refresh_token(force=False) is False


@pytest.mark.anyio
async def test_check_and_refresh_token_expired():
    """Test token refresh is triggered when token has expired (>48 hours)."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        username="test_client",
        access_token="old_token",
        access_token_time=now - (3 * 86400),  # 3 days old (expired)
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (3 * 86400),
        refresh_token_duration=30,
    )

    with patch("custom_components.vidaa.client.async_perform_token_refresh", return_value=None) as mock_refresh, \
         patch.object(client, "async_sync_clock"):
        assert await client.async_check_and_refresh_token(force=False) is False
        mock_refresh.assert_awaited_once()
        assert mock_refresh.call_args[1]["refresh_token"] == "valid_refresh"
        assert mock_refresh.call_args[1]["username"] == "test_client"


def test_check_and_refresh_token_network_error_resilience():
    """Test token refresh catches network / socket errors gracefully without crashing."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        access_token="old_token",
        access_token_time=now - (3 * 86400),
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (3 * 86400),
        refresh_token_duration=30,
    )

    with patch("paho.mqtt.client.Client") as mock_mqtt:
        mock_instance = MagicMock()
        mock_instance.connect.side_effect = OSError("Connection refused / unreachable host")
        mock_mqtt.return_value = mock_instance

        # Should catch error and return False
        refreshed = client.check_and_refresh_token(force=True)
        assert refreshed is False


def test_auth_failed_and_token_refreshed_callback_dispatches():
    """Test auth_failed and token_refreshed dispatch callbacks pass the client instance."""
    client = HisenseTvClient(ip="192.168.50.12")

    auth_failed_calls = []
    token_refreshed_calls = []

    def on_auth_failed(c):
        auth_failed_calls.append(c)

    def on_token_refreshed(c):
        token_refreshed_calls.append(c)

    client.register_auth_failed_callback(on_auth_failed)
    client.register_token_refreshed_callback(on_token_refreshed)

    client._dispatch_auth_failed()
    assert len(auth_failed_calls) == 1
    assert auth_failed_calls[0] is client

    client._dispatch_token_refreshed()
    assert len(token_refreshed_calls) == 1
    assert token_refreshed_calls[0] is client


@pytest.mark.anyio
async def test_on_connect_rc4_with_valid_refresh_token_triggers_background_refresh():
    """Test rc=4 connection rejection with valid refresh token starts background task and does not dispatch auth_failed immediately."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        refresh_token="valid_refresh_token",
        refresh_token_time=now - 86400,  # 1 day old (valid 30 days)
        refresh_token_duration=30,
    )
    mock_auth_failed = MagicMock()
    client.register_auth_failed_callback(mock_auth_failed)

    with patch.object(client._token_manager, "async_refresh_token_and_update_creds") as mock_refresh, \
         patch.object(client, "async_sync_clock"):
        await client._token_manager.async_handle_auth_rejection(4)
        mock_refresh.assert_called_once()
        mock_auth_failed.assert_not_called()


def test_refresh_failure_with_valid_refresh_token_suppresses_auth_failed():
    """Test failed background refresh (e.g. TV in standby) suppresses auth_failed if refresh token is still unexpired."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        refresh_token="valid_refresh_token",
        refresh_token_time=now - 86400,  # 1 day old (valid 30 days)
        refresh_token_duration=30,
    )
    mock_auth_failed = MagicMock()
    client.register_auth_failed_callback(mock_auth_failed)

    with patch.object(client, "check_and_refresh_token", return_value=False):
        client._refresh_token_and_update_creds()
        mock_auth_failed.assert_not_called()


def test_refresh_failure_with_expired_refresh_token_dispatches_auth_failed():
    """Test failed background refresh when refresh token IS expired (>30 days) dispatches auth_failed."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        refresh_token="expired_refresh_token",
        refresh_token_time=now - (31 * 86400),  # 31 days old (expired)
        refresh_token_duration=30,
    )
    mock_auth_failed = MagicMock()
    client.register_auth_failed_callback(mock_auth_failed)

    with patch.object(client, "check_and_refresh_token", return_value=False):
        client._refresh_token_and_update_creds()
        mock_auth_failed.assert_called_once()


def test_proactive_token_refresh_triggers_within_12_hours():
    """Test proactive token refresh triggers renewal when access token has <12h remaining."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        access_token="expiring_soon_token",
        access_token_time=now - (40 * 3600),  # 40 hours old (8h left on 48h token)
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (40 * 3600),
        refresh_token_duration=30,
    )

    client.PROACTIVE_REFRESH_SETTLE_SECONDS = 0
    client.state = "on"  # TV awake: gettoken is answered

    with patch.object(client, "refresh_tokens") as mock_refresh:
        client._proactive_token_refresh()
        mock_refresh.assert_called_once()


def test_proactive_token_refresh_deferred_in_standby():
    """Proactive refresh must not drop the working connection while the TV is in standby."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        access_token="expiring_soon_token",
        access_token_time=now - (40 * 3600),
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (40 * 3600),
        refresh_token_duration=30,
    )
    client.PROACTIVE_REFRESH_SETTLE_SECONDS = 0
    client.state = "off"  # retained fake_sleep_0 received

    with patch.object(client, "refresh_tokens") as mock_refresh:
        client._proactive_token_refresh()
        mock_refresh.assert_not_called()
    assert client._refreshing_token is False


def _standby_client(access_age_hours: float, refresh_in_standby: bool) -> HisenseTvClient:
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        access_token="token",
        access_token_time=int(now - access_age_hours * 3600),
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (40 * 3600),
        refresh_token_duration=30,
        refresh_in_standby=refresh_in_standby,
    )
    client.PROACTIVE_REFRESH_SETTLE_SECONDS = 0
    client.state = "off"  # retained fake_sleep_0 received
    client.connected = True
    return client


def test_proactive_token_refresh_in_standby_when_enabled():
    """With refresh_in_standby a near-expiry (still valid) token is renewed although the TV is in standby."""
    client = _standby_client(access_age_hours=40, refresh_in_standby=True)
    with patch.object(client, "refresh_tokens") as mock_refresh:
        client._proactive_token_refresh()
        mock_refresh.assert_called_once()


def test_proactive_token_refresh_in_standby_skipped_once_expired():
    """In standby an expired token is not refreshed: the open connection could not be re-established."""
    client = _standby_client(access_age_hours=50, refresh_in_standby=True)
    with patch.object(client, "refresh_tokens") as mock_refresh:
        client._proactive_token_refresh()
        mock_refresh.assert_not_called()


def test_token_watch_refreshes_in_standby_when_enabled():
    """The periodic token watch also renews in standby when the option is on, and not when it is off."""
    enabled = _standby_client(access_age_hours=40, refresh_in_standby=True)
    with patch.object(enabled, "refresh_tokens", return_value=True) as mock_refresh:
        enabled._maybe_refresh_while_awake()
        mock_refresh.assert_called_once()

    disabled = _standby_client(access_age_hours=40, refresh_in_standby=False)
    with patch.object(disabled, "refresh_tokens") as mock_refresh:
        disabled._maybe_refresh_while_awake()
        mock_refresh.assert_not_called()


@pytest.mark.anyio
async def test_refresh_tokens_restores_connection_on_failure():
    """A failed refresh (TV in standby) must reconnect with the current access token."""
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="cid",
        username="his$1",
        access_token="still_valid",
        refresh_token="valid_refresh",
    )
    client.mqtt_client = MagicMock()
    client.connected = True

    with patch("custom_components.vidaa.client.async_perform_token_refresh", return_value=None), \
         patch.object(client, "async_sync_clock"), \
         patch.object(client, "async_connect_and_run") as mock_connect:
        assert await client.async_refresh_tokens() is False
        mock_connect.assert_awaited_once()


def test_is_token_expired_with_clock_offset():
    """Test is_token_expired correctly respects positive and negative clock offsets."""
    host_now = int(time.time())
    tv_offset = -518400
    tv_now = host_now + tv_offset
    token_time = tv_now - 3600  # 1 hour old in TV epoch

    # Without offset: host is 6 days ahead, so 2-day token appears expired
    assert is_token_expired(token_time, 2, clock_offset=0) is True

    # With TV clock offset: token is only 1 hour old in TV epoch
    assert is_token_expired(token_time, 2, clock_offset=tv_offset) is False


def test_sync_clock_and_clock_drift_callback():
    """Test HisenseTvClient.sync_clock updates offset and dispatches callback."""
    client = HisenseTvClient(ip="192.168.50.12")
    host_now = int(time.time())
    mock_tv_ts = host_now - 500000

    drift_records = []
    client.register_clock_drift_callback(lambda offset: drift_records.append(offset))

    with patch.object(client.upnp, "async_get_tv_timestamp", AsyncMock(return_value=mock_tv_ts)):
        offset = client.sync_clock()

    assert offset == mock_tv_ts - host_now
    assert client.clock_offset == offset
    assert client.tv_timestamp == mock_tv_ts
    assert len(drift_records) == 1
    assert drift_records[0] == offset


def test_check_and_refresh_token_respects_clock_offset():
    """Test check_and_refresh_token does not falsely refresh when clock offset is applied."""
    host_now = int(time.time())
    tv_offset = -500000
    tv_now = host_now + tv_offset
    token_time = tv_now - 3600

    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        access_token="valid_token",
        access_token_time=token_time,
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=token_time,
        refresh_token_duration=30,
    )
    client.clock_offset = tv_offset

    with patch.object(client, "refresh_tokens") as mock_refresh:
        res = client.check_and_refresh_token(force=False)
        assert res is False
        mock_refresh.assert_not_called()


@pytest.mark.anyio
async def test_token_refresh_failure_honors_clock_offset():
    """Verify background token refresh failure evaluates refresh token expiry with clock_offset."""
    client = MagicMock()
    client.ip = "192.168.50.12"
    client.refresh_token = "valid_refresh_token"
    # Hardware clock is 100 days in the past (clock_offset = -8,640,000)
    client.clock_offset = -8640000
    tv_now = int(time.time()) + client.clock_offset
    client.refresh_token_time = tv_now - (5 * 86400)
    client.refresh_token_duration = 60
    client.async_check_and_refresh_token = AsyncMock(return_value=False)
    client._dispatch_auth_failed = MagicMock()

    mgr = TokenLifecycleManager(client)
    mgr.last_refresh_connect_rc = 5
    mgr.broker_rejection_failures = 1  # Less than max 3

    await mgr.async_refresh_token_and_update_creds()

    # Even though refresh failed once, the refresh token has 55 days left in TV epoch,
    # so auth_failed MUST NOT be dispatched if clock_offset is applied properly!
    client._dispatch_auth_failed.assert_not_called()


@pytest.mark.anyio
async def test_async_sync_clock_fallback_uses_thread():
    """Test async_sync_clock falls back to synchronous fn in a thread without blocking (Issue #59)."""
    client = HisenseTvClient(ip="192.168.50.12")
    host_now = int(time.time())
    mock_tv_ts = host_now - 100

    def mock_sync_get_tv_timestamp(ip, timeout=2.0):
        import threading
        assert threading.current_thread() is not threading.main_thread()
        return mock_tv_ts

    with (
        patch.object(client.upnp, "async_get_tv_timestamp", AsyncMock(return_value=None)),
        patch("custom_components.vidaa.tv.tokens._get_tv_timestamp_fn", return_value=mock_sync_get_tv_timestamp),
    ):
        offset = await client.async_sync_clock()

    assert offset == mock_tv_ts - host_now
    assert client.tv_timestamp == mock_tv_ts

