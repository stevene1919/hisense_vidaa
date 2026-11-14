"""Unit tests for HisenseTvClient authentication algorithms and profile probing."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from custom_components.vidaa.client import HisenseTvClient


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


def test_probe_auth_methods():
    """Test probing various auth algorithms returns structured capability dict."""
    client = HisenseTvClient(ip="192.168.50.12")

    fake_results = {
        "legacy_static": {"rc": 0, "supported": True},
        "standard_dynamic": {"rc": 5, "supported": False},
        "middle_dynamic": {"rc": 5, "supported": False},
        "modern_dynamic": {"rc": 0, "supported": True},
        "client_cert_presented": True,
    }

    with patch("custom_components.vidaa.client.async_probe_tv_auth_methods", return_value=fake_results):
        res = client.probe_auth_methods()

    assert res["legacy_static"]["supported"] is True
    assert res["standard_dynamic"]["supported"] is False
    assert res["middle_dynamic"]["supported"] is False
    assert res["modern_dynamic"]["supported"] is True
    assert res["client_cert_presented"] is True


@pytest.mark.anyio
async def test_async_start_auth_auto_fallback_on_rc5():
    """Test auto profile fallback from modern to middle when modern gets rc 5 rejection."""
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="auto")

    calls = []

    async def mock_internal(profile="modern", use_new_auth=None):
        calls.append(profile)
        if profile == "modern":
            raise Exception("Broker rejected connection with code 5")
        if profile == "middle":
            return
        raise Exception(f"Unexpected profile {profile}")

    with patch.object(client, "get_device_fingerprint", return_value={}), \
         patch.object(client, "_async_start_auth_internal", side_effect=mock_internal):
        await client.async_start_auth()

    assert calls == ["modern", "middle"]
    assert client.auth_profile == "middle"


@pytest.mark.anyio
async def test_async_start_auth_full_cascade_to_legacy():
    """Test auto profile cascades all dynamic profiles (modern, middle, remotenow) when all fail."""
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="auto")

    calls = []

    async def mock_internal(profile="modern", use_new_auth=None):
        calls.append(profile)
        raise Exception("MQTT connection rejected with code 5")

    with patch.object(client, "get_device_fingerprint", return_value={}), \
         patch.object(client, "_async_start_auth_internal", side_effect=mock_internal):
        with pytest.raises(Exception, match="rejected with code 5"):
            await client.async_start_auth()
        assert calls[:3] == ["modern", "middle", "remotenow"]


@pytest.mark.anyio
async def test_async_probe_tv_auth_methods_passes_brand():
    """Verify async_probe_tv_auth_methods accepts brand and generates brand-prefixed credentials."""
    import sys

    from custom_components.vidaa.protocol.auth import async_probe_tv_auth_methods

    probed_creds = []

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            probed_creds.append((kwargs.get("username"), kwargs.get("password")))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_aiomqtt = MagicMock()
    mock_aiomqtt.Client = MockAsyncClient
    mock_aiomqtt.ProtocolVersion = MagicMock()

    with patch.dict(sys.modules, {"aiomqtt": mock_aiomqtt}):
        results = await async_probe_tv_auth_methods("192.168.50.12", brand="tos")

    assert results["legacy_static"]["supported"] is True
    assert results["modern_dynamic"]["supported"] is True
    assert "diagnostic" in results["modern_dynamic"]
    assert results["modern_dynamic"]["diagnostic"] == "accepted"
    usernames = [u for u, _ in probed_creds]
    assert "hisenseservice" in usernames
    assert any(u and u.startswith("tos$") for u in usernames)


@pytest.mark.anyio
async def test_async_probe_tv_auth_methods_toptro_rejection_diagnostics():
    """Verify TOPTRO brand and timestamp propagation and AUTH_REJECTION_CODES classification."""
    import sys

    from custom_components.vidaa.protocol.auth import async_probe_tv_auth_methods

    probed_creds = []

    class MockRejectionError(Exception):
        rc = 135

    class MockRejectingClient:
        def __init__(self, *args, **kwargs):
            probed_creds.append(kwargs)

        async def __aenter__(self):
            raise MockRejectionError()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_aiomqtt = MagicMock()
    mock_aiomqtt.Client = MockRejectingClient
    mock_aiomqtt.ProtocolVersion = MagicMock()
    mock_aiomqtt_exc = MagicMock()
    mock_aiomqtt_exc.MqttConnectError = MockRejectionError

    with patch.dict(sys.modules, {"aiomqtt": mock_aiomqtt, "aiomqtt.exceptions": mock_aiomqtt_exc}):
        results = await async_probe_tv_auth_methods("192.168.50.15", brand="tpo", timestamp=1700000000)

    assert results["brand"] == "tpo"
    assert results["timestamp"] == 1700000000
    assert results["standard_dynamic"]["diagnostic"] == "not_authorized"
    assert results["middle_dynamic"]["diagnostic"] == "not_authorized"
    assert results["modern_dynamic"]["diagnostic"] == "not_authorized"
    assert results["modern_dynamic"]["rc"] == 135

    # Verify brand prefix and timestamp on probed credentials
    usernames = [call_kw.get("username") for call_kw in probed_creds]
    assert any(u and u.startswith("tpo$") for u in usernames)

