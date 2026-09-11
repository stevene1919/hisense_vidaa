"""Tests for Hisense VIDAA sensors, binary sensors, and buttons."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
)
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
from custom_components.hisense_vidaa.notify import HisenseVidaaNotifyEntity
from custom_components.hisense_vidaa.remote import HisenseVidaaRemote
from custom_components.hisense_vidaa.select import HisenseVidaaAudioOutputSelect
from custom_components.hisense_vidaa.sensor import (
    HisenseVidaaActiveAppSensor,
    HisenseVidaaActiveSourceSensor,
    HisenseVidaaAudioOutputSensor,
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
    s_source._handle_state_update({
        "statetype": "sourceswitch",
        "sourcename": "HDMI 1",
        "displayname2": "PlayStation 5",
    })
    assert s_source.extra_state_attributes["connected_device"] == "PlayStation 5"

    s_source._handle_state_update({
        "statetype": "livetv",
        "channel_name": "ABC HD",
        "channel_num": "20",
    })
    assert s_source.extra_state_attributes["channel_name"] == "ABC HD"
    assert s_source.extra_state_attributes["channel_num"] == "20"

    s_audio = HisenseVidaaAudioOutputSensor(mock_client, mock_entry)
    assert s_audio.native_value == "TV Speakers"
    s_audio._handle_volume_update({"volume_type": 1, "volume_value": 20})
    assert s_audio.native_value == "ARC / eARC"


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
    assert mp.device_class == MediaPlayerDeviceClass.TV
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


@pytest.mark.anyio
async def test_remote_send_command(mock_client, mock_entry):
    rem = HisenseVidaaRemote(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
    )
    # Standard command
    await rem.async_send_command(["home", "ok"], delay_secs=0.01)
    assert mock_client.send_command.call_count == 2

    # Hold secs for OK long press
    await rem.async_send_command(["ok"], hold_secs=0.5)
    mock_client.send_key.assert_called_with("KEY_OK_LONG_PRESS")

    # Hold secs for arbitrary key burst
    mock_client.send_command.reset_mock()
    await rem.async_send_command(["up"], hold_secs=0.3)
    assert mock_client.send_command.call_count == 3


def test_media_player_play_media(mock_client, mock_entry):
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
    )
    mp._app_dict = {"Netflix": {"appId": "1", "name": "Netflix", "url": "netflix://"}}

    # App launch by name
    mp.play_media("app", "Netflix")
    mock_client.launch_app.assert_called_with("1", "Netflix", "netflix://")

    # Deep link URL
    mp.play_media("url", "https://youtube.com/watch?v=123")
    mock_client.launch_app.assert_called_with("", "https://youtube.com/watch?v=123", "https://youtube.com/watch?v=123")

    # Channel tuning with dot
    mock_client.send_key.reset_mock()
    mp.play_media("channel", "7.1")
    assert mock_client.send_key.call_count == 3


@pytest.mark.anyio
async def test_notify_entity(mock_client, mock_entry):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    notify = HisenseVidaaNotifyEntity(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
    )
    notify.hass = hass
    assert notify.available is True
    assert notify.unique_id == "test_entry_id_notify"

    await notify.async_send_message("Someone is at the front door!", "Doorbell")
    mock_client.show_message.assert_called_with("Someone is at the front door!", "Doorbell")


@pytest.mark.anyio
async def test_select_entity(mock_client, mock_entry):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    sel = HisenseVidaaAudioOutputSelect(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
    )
    sel.hass = hass
    assert sel.available is True
    assert sel.unique_id == "test_entry_id_audio_output_select"
    assert sel.current_option == "TV Speakers"

    # Handle volume update to ARC
    sel._handle_volume_update({"volume_type": 1})
    assert sel.current_option == "ARC / eARC"

    # Select TV Speakers
    await sel.async_select_option("TV Speakers")
    mock_client.send_key.assert_called_with("KEY_AUDIO_ONLY")
    assert sel.current_option == "TV Speakers"


def test_media_player_cec_source_naming(mock_client, mock_entry):
    mock_entry.options = {"enable_cec_names": True, "include_apps_in_sources": True}
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
        options=mock_entry.options,
    )
    mp.hass = MagicMock()
    mp._source_dict = {
        "HDMI1": {"sourceid": "HDMI1", "sourcename": "HDMI1"},
        "HDMI2": {"sourceid": "HDMI2", "sourcename": "HDMI2"},
    }
    mp._source = "HDMI2"
    mp._connected_device = "PlayStation 5"

    assert mp.source == "HDMI2 (PlayStation 5)"
    assert "HDMI2 (PlayStation 5)" in mp.source_list
    assert "HDMI1" in mp.source_list

    # Test select_source stripping HDMI-CEC device label
    mp.select_source("HDMI2 (PlayStation 5)")
    mock_client.change_source.assert_called_with("HDMI2", "HDMI2")


@pytest.mark.anyio
async def test_remote_and_media_player_idempotent_power_control(mock_client, mock_entry):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    rem = HisenseVidaaRemote(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
        options=mock_entry.options,
    )
    rem.hass = hass

    # Mock client connected: initial state should be ON
    mock_client.connected = True
    assert rem.is_on is True

    # Calling async_turn_on when already connected & ON must NOT send KEY_POWER
    mock_client.send_key.reset_mock()
    await rem.async_turn_on()
    mock_client.send_key.assert_not_called()
    assert rem.is_on is True

    # Simulate TV entering fake sleep (screen off)
    rem._handle_state_update({"statetype": "fake_sleep_0"})
    assert rem.is_on is False

    # Calling async_turn_on while in fake_sleep_0 MUST send KEY_POWER to wake screen
    await rem.async_turn_on()
    mock_client.send_key.assert_called_once_with("KEY_POWER")
    assert rem.is_on is True

    # Test media_player turn_on idempotence
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        mac=mock_entry.data["mac_address"],
        entry_id=mock_entry.entry_id,
        name=mock_entry.title,
        options=mock_entry.options,
    )
    mp.hass = hass
    assert mp.state == "on"

    # Calling turn_on when already connected & on must NOT send KEY_POWER
    mock_client.send_key.reset_mock()
    mp.turn_on()
    mock_client.send_key.assert_not_called()
    assert mp.state == "on"

    # In fake sleep, turn_on should wake display
    mp._handle_state_update({"statetype": "fake_sleep_0"})
    assert mp.state == "off"
    mp.turn_on()
    mock_client.send_key.assert_called_once_with("KEY_POWER")
    assert mp.state == "on"
