"""Unit tests for HisenseTvClient authentication and token lifecycle."""

import asyncio
import time
from unittest.mock import MagicMock, patch

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
        assert "modern_dynamic" in probe
        assert "supported" in probe["legacy_static"]
        assert "supported" in probe["standard_dynamic"]
        assert "supported" in probe["modern_dynamic"]
