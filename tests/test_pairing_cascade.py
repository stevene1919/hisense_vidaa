"""Tests for pairing cascade, profile fallback, and candidate OEM brand probing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.protocol.pairing import (
    _async_execute_pairing_attempt,
    async_start_pairing_handshake,
)


# ---------------------------------------------------------------------------
# [P4-d] Dynamic fallback: the vidaa_app_connect ACK unblocks the retry wait.
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_dynamic_connect_ack_unblocks_retry_wait(monkeypatch):
    client = HisenseTvClient(
        ip="192.168.50.12", mac="e8:51:77:ec:98:1c", auth_profile="modern"
    )
    client.client_id = "aa$his$BB_vidaacommon_001"
    client.username = "his$1"
    client.password = "pw"
    client.access_token = "at"
    client.update_topic_paths()
    client.connected = True

    client.upnp.async_get_tv_timestamp = AsyncMock(return_value=1700000000)

    mqtt = MagicMock()

    def fake_publish(topic, payload="", *args, **kwargs):
        # The TV accepts the connect request but never announces a PIN dialog.
        ack = getattr(client, "_connect_ack_future", None)
        if ack is not None and not ack.done():
            ack.set_result('{"connect_result":1}')
        return (0, 1)

    mqtt.publish.side_effect = fake_publish
    mqtt.async_publish = AsyncMock(side_effect=fake_publish)
    mqtt.async_subscribe = AsyncMock(return_value=True)
    client.create_mqtt_client = MagicMock(return_value=mqtt)

    async def fake_open_session(*args, **kwargs):
        client.mqtt_client = mqtt

    client.async_open_pairing_session = AsyncMock(side_effect=fake_open_session)

    # Must return cleanly (ACK breaks the retry loop) instead of raising the
    # "TV did not show PIN" timeout after three attempts.
    await _async_execute_pairing_attempt(client, profile="modern")

    assert client._auth_future is None
    assert client._connect_ack_future is None


# ---------------------------------------------------------------------------
# [P5] OEM Brand Cascade: On auth rejection (rc:5), cascade probes candidate brands.
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_pairing_brand_fallback_target_profile():
    """Verify that when default brand 'his' is rejected with rc: 5, candidate OEM brands are tried."""

    client = HisenseTvClient(
        ip="192.168.50.12", mac="e8:51:77:ec:98:1c", auth_profile="modern", brand="his"
    )

    calls = []

    async def fake_start_auth_internal(profile="modern"):
        calls.append((client.brand, profile))
        if client.brand == "his":
            raise RuntimeError("Connection error: code 5 (Not authorized)")
        if client.brand == "tos":
            return
        raise RuntimeError("Unexpected brand")

    client._async_start_auth_internal = fake_start_auth_internal

    await async_start_pairing_handshake(client)

    assert client.brand == "tos"
    assert ("his", "modern") in calls
    assert ("tos", "modern") in calls


@pytest.mark.anyio
async def test_pairing_brand_fallback_auto_profile():
    """Verify that in 'auto' mode, auth rejection cascades through candidate brands."""

    client = HisenseTvClient(
        ip="192.168.50.12", mac="e8:51:77:ec:98:1c", auth_profile="auto", brand="his"
    )
    client.get_device_fingerprint = MagicMock(return_value={})

    calls = []

    async def fake_start_auth_internal(profile="modern"):
        calls.append((client.brand, profile))
        if client.brand == "his":
            raise RuntimeError("Broker rejected connection with code 5")
        if client.brand == "tos" and profile == "middle":
            return
        if client.brand == "tos":
            raise RuntimeError("Broker rejected connection with code 5")
        raise RuntimeError("Unexpected brand")

    client._async_start_auth_internal = fake_start_auth_internal

    await async_start_pairing_handshake(client)

    assert client.brand == "tos"
    assert client.auth_profile == "middle"
    assert ("his", "modern") in calls
    assert ("tos", "modern") in calls
    assert ("tos", "middle") in calls


@pytest.mark.anyio
async def test_pairing_brand_fallback_exhausted_resets_brand():
    """Verify that when all candidate brands fail with auth rejection, brand is reset to 'his'."""

    client = HisenseTvClient(
        ip="192.168.50.12", mac="e8:51:77:ec:98:1c", auth_profile="modern", brand="his"
    )

    async def fake_start_auth_internal(profile="modern"):
        raise RuntimeError("Broker rejected connection with code 5")

    client._async_start_auth_internal = fake_start_auth_internal

    with pytest.raises(RuntimeError, match="code 5"):
        await async_start_pairing_handshake(client)

    assert client.brand == "his"



