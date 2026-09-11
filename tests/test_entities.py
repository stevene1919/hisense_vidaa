"""Tests for Hisense VIDAA sensors, binary sensors, and buttons."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.binary_sensor import (
    HisenseVidaaMqttConnectedBinarySensor,
)
from custom_components.hisense_vidaa.button import (
    HisenseVidaaForceReconnectButton,
    HisenseVidaaRefreshTokenButton,
    HisenseVidaaSyncClockButton,
)
from custom_components.hisense_vidaa.media_player import HisenseVidaaMediaPlayer
from custom_components.hisense_vidaa.remote import HisenseVidaaRemote
from custom_components.hisense_vidaa.sensor import (
    HisenseVidaaActiveAppSensor,
    HisenseVidaaActiveSourceSensor,
    HisenseVidaaAuthProfileSensor,
    HisenseVidaaTokenExpiresSensor,
)


@pytest.fixture
def mock_entry():
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.title = "Living Room TV"
    entry.data = {
        "ip_address": "192.168.50.12",
        "mac_address": "e8:51:77:ec:98:1c",
        "auth_profile": "modern",
        "model": "65U7G",
        "manufacturer": "Hisense",
        "sw_version": "V1.0",
    }
    entry.options = {"enable_remote": True, "enable_wol": True}
    return entry


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.ip = "192.168.50.12"
    client.connected = True
    client.auth_profile = "modern"
    client.access_token_time = 1700000000
    client.access_token_duration = 3600
    client.refresh_token_time = 1700000000
    client.refresh_token_duration = 86400
    client.current_app = "Netflix"
    client.source = "HDMI 1"
    client.tv_state = "on"
    return client


@pytest.mark.anyio
async def test_sensor_entities(mock_client, mock_entry):
    s_expires = HisenseVidaaTokenExpiresSensor(mock_client, mock_entry)
    s_expires._update_state()
    assert s_expires.native_value == datetime.fromtimestamp(1700000000 + (3600 * 86400), tz=UTC)

    s_profile = HisenseVidaaAuthProfileSensor(mock_client, mock_entry)
    assert s_profile.native_value == "VIDAA 2.0 (Newer Firmware / 2024+)"

    s_app = HisenseVidaaActiveAppSensor(mock_client, mock_entry)
    s_app._handle_applist_update([{"appId": "123", "appName": "Netflix"}])
    s_app._handle_state_update({"appId": "123"})
    assert s_app.native_value == "Netflix"

    s_source = HisenseVidaaActiveSourceSensor(mock_client, mock_entry)
    s_source._handle_sourcelist_update([{"sourceName": "HDMI 1", "is_active": True}])
    assert s_source.native_value == "HDMI 1"


def test_binary_sensor_entities(mock_client, mock_entry):
    bs_mqtt = HisenseVidaaMqttConnectedBinarySensor(mock_client, mock_entry)
    assert bs_mqtt.is_on is True


@pytest.mark.anyio
async def test_button_entities(mock_client, mock_entry, monkeypatch):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    b_refresh = HisenseVidaaRefreshTokenButton(mock_client, mock_entry)
    b_refresh.hass = hass
    await b_refresh.async_press()
    mock_client.check_and_refresh_token.assert_called_once_with(True)

    b_reconnect = HisenseVidaaForceReconnectButton(mock_client, mock_entry)
    b_reconnect.hass = hass
    await b_reconnect.async_press()
    mock_client.disconnect.assert_called_once()
    mock_client.connect_and_run.assert_called_once()

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.button.get_tv_timestamp",
        lambda ip, timeout: 1700000000,
    )
    b_sync = HisenseVidaaSyncClockButton(mock_client, mock_entry)
    b_sync.hass = hass
    await b_sync.async_press()


def test_media_player_and_remote_device_info(mock_client, mock_entry):
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
        options=mock_entry.options,
        model=mock_entry.data["model"],
        manufacturer=mock_entry.data["manufacturer"],
        sw_version=mock_entry.data["sw_version"],
    )
    dev_info = mp.device_info
    assert dev_info["identifiers"] == {("hisense_vidaa", "test_entry_id")}
    assert dev_info["model"] == "65U7G"
    assert dev_info["manufacturer"] == "Hisense"
    assert dev_info["sw_version"] == "V1.0"

    rem = HisenseVidaaRemote(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
        options=mock_entry.options,
        model=mock_entry.data["model"],
        manufacturer=mock_entry.data["manufacturer"],
        sw_version=mock_entry.data["sw_version"],
    )
    rem_info = rem.device_info
    assert rem_info["identifiers"] == {("hisense_vidaa", "test_entry_id")}
    assert rem_info["model"] == "65U7G"
