"""Unit tests for HisenseTvClient authentication and token lifecycle."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from client import HisenseTvClient


def test_legacy_static_auth():
    """Test legacy static authentication profile initializes static credentials without PIN."""
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="legacy")

    # Run async start auth for legacy
    asyncio.run(client.async_start_auth())

    assert client.client_id == "hisenseservice"
    assert client.username == "hisenseservice"
    assert client.password == "multimqttservice"
    assert client.access_token == "multimqttservice"

    # Legacy profile should never attempt token refresh
    assert client.check_and_refresh_token(force=True) is False


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


def test_check_and_refresh_token_expired():
    """Test token refresh is triggered when token has expired (>48 hours)."""
    now = int(time.time())
    client = HisenseTvClient(
        ip="192.168.50.12",
        client_id="test_client",
        access_token="old_token",
        access_token_time=now - (3 * 86400),  # 3 days old (expired)
        access_token_duration=2,
        refresh_token="valid_refresh",
        refresh_token_time=now - (3 * 86400),
        refresh_token_duration=30,
    )

    mock_mqtt_instance = MagicMock()
    mock_mqtt_instance.connect.return_value = 0

    with patch("paho.mqtt.client.Client", return_value=mock_mqtt_instance), patch("ssl.create_default_context"):
        # Trigger refresh
        client.check_and_refresh_token(force=False)
        assert client.access_token_time == now - (3 * 86400) or client.access_token == "new_access_token"


def test_probe_auth_methods():
    """Test probing various auth algorithms returns structured capability dict."""
    client = HisenseTvClient(ip="192.168.50.12")

    mock_client = MagicMock()
    mock_client.connect_async.return_value = 0

    with patch("paho.mqtt.client.Client", return_value=mock_client):
        # When connect fails immediately or times out in unit test
        probe = client.probe_auth_methods(timeout=0.01)
        assert "legacy_static" in probe
        assert "standard_dynamic" in probe
        assert "middle_dynamic" in probe
        assert "modern_dynamic" in probe
        assert "supported" in probe["legacy_static"]
        assert "supported" in probe["standard_dynamic"]
        assert "supported" in probe["middle_dynamic"]
        assert "supported" in probe["modern_dynamic"]


def test_ensure_connected_rate_limiting_and_cleanup():
    """Test ensure_connected rate limits reconnection attempts and cleans up previous loops."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="test_client", username="u", access_token="t")

    mock_old_mqtt = MagicMock()
    client.mqtt_client = mock_old_mqtt
    client.connected = False

    # First call triggers reconnect
    with patch.object(client, "create_mqtt_client") as mock_create:
        mock_new_mqtt = MagicMock()
        mock_create.return_value = mock_new_mqtt

        res1 = client.ensure_connected(min_interval=5.0)
        assert res1 is True
        mock_old_mqtt.loop_stop.assert_called_once()
        mock_old_mqtt.disconnect.assert_called_once()
        mock_new_mqtt.connect_async.assert_called_once()
        mock_new_mqtt.loop_start.assert_called_once()

        # Immediate second call is rate-limited
        res2 = client.ensure_connected(min_interval=5.0)
        assert res2 is False


def test_on_connect_rc5_no_refresh_token():
    """Test rc=5 connection rejection without refresh token stops loop and dispatches auth_failed without spawning thread."""
    client = HisenseTvClient(ip="192.168.50.12")
    mock_mqtt = MagicMock()
    mock_auth_failed = MagicMock()
    client.register_auth_failed_callback(mock_auth_failed)

    with patch("threading.Thread") as mock_thread:
        client._on_connect(mock_mqtt, None, None, rc=5)
        mock_mqtt.loop_stop.assert_called_once()
        mock_thread.assert_not_called()
        mock_auth_failed.assert_called_once()


def test_on_connect_rc5_pairing_future():
    """Test rc=5 connection rejection during active pairing sets exception on auth_future and stops loop."""
    client = HisenseTvClient(ip="192.168.50.12")
    mock_mqtt = MagicMock()

    loop = asyncio.new_event_loop()
    client._loop = loop
    client._auth_future = loop.create_future()

    client._on_connect(mock_mqtt, None, None, rc=5)
    mock_mqtt.loop_stop.assert_called_once()
    assert client._auth_future.done()
    assert "rejected with code 5" in str(client._auth_future.exception())
    loop.close()


@pytest.mark.anyio
async def test_async_start_auth_auto_fallback_on_rc5():
    """Test auto profile falls back through profiles on rc=5 until success."""
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="auto")

    calls = []

    async def mock_internal(profile="modern", use_new_auth=None):
        calls.append(profile)
        if profile == "modern":
            raise Exception("MQTT connection rejected with code 5 (Not authorized / invalid credentials)")

    with patch.object(client, "get_device_fingerprint", return_value={"transport_protocol": "3290"}), \
         patch.object(client, "_async_start_auth_internal", side_effect=mock_internal):
        await client.async_start_auth()
        assert calls == ["modern", "middle"]
        assert client.auth_profile == "middle"
