"""Tests for Hisense VIDAA operational and diagnostic sensors, binary sensors, buttons, and switches."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.binary_sensor import (
    HisenseVidaaInUseBinarySensor,
    HisenseVidaaMqttConnectedBinarySensor,
)
from custom_components.hisense_vidaa.button import (
    HisenseVidaaForceReconnectButton,
    HisenseVidaaSyncClockButton,
)
from custom_components.hisense_vidaa.sensor import (
    HisenseVidaaActiveAppSensor,
    HisenseVidaaActiveSourceSensor,
)
from custom_components.hisense_vidaa.sensors_diagnostic import (
    HisenseVidaaAudioOutputSensor,
    HisenseVidaaAuthProfileSensor,
    HisenseVidaaReportedNameSensor,
    HisenseVidaaSessionStatusSensor,
)
from custom_components.hisense_vidaa.switch import (
    HisenseVidaaAudioOnlySwitch,
    HisenseVidaaDebugLoggingSwitch,
)


@pytest.mark.anyio
async def test_sensor_entities(mock_client, mock_entry):
    """Test operational and diagnostic sensor entities."""
    s_status = HisenseVidaaSessionStatusSensor(mock_client, mock_entry)
    s_status._update_state()
    assert s_status.native_value == "Active"
    assert s_status.extra_state_attributes["encryption"] == "TLSv1.2 (Port 36669)"
    assert s_status.extra_state_attributes["local_only"] is True
    assert "paired_at" in s_status.extra_state_attributes
    assert "access_token_expires_at" in s_status.extra_state_attributes
    assert "refresh_token_expires_at" in s_status.extra_state_attributes

    mock_client.connected = False
    s_status._update_state()
    assert s_status.native_value == "Standby"

    s_status._handle_auth_failed(mock_client)
    assert s_status.native_value == "Reauth Required"

    mock_client.connected = True
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

    s_name = HisenseVidaaReportedNameSensor(mock_client, mock_entry)
    assert s_name.native_value == "Living Room TV"
    mock_client.device_name = "Bedroom VIDAA TV"
    s_name._handle_device_info({"friendly_name": "Bedroom VIDAA TV"})
    assert s_name.native_value == "Bedroom VIDAA TV"
    assert s_name.extra_state_attributes["ip_address"] == "192.168.50.12"
    assert s_name.extra_state_attributes["mac_address"] == "e8:51:77:ec:98:1c"


def test_binary_sensor_entities(mock_client, mock_entry):
    """Test MQTT connected binary sensor entity."""
    bs_mqtt = HisenseVidaaMqttConnectedBinarySensor(mock_client, mock_entry)
    assert bs_mqtt.is_on is True


@pytest.mark.anyio
async def test_button_entities(mock_client, mock_entry, monkeypatch):
    """Test Force Reconnect and Sync Clock button entities."""
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

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


@pytest.mark.anyio
async def test_switch_entities(mock_client, mock_entry):
    """Test AudioOnly and DebugLogging switch entities."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    sw_audio = HisenseVidaaAudioOnlySwitch(mock_client, mock_entry)
    sw_audio.hass = hass
    assert sw_audio.is_on is False
    assert sw_audio.unique_id == "test_entry_id_audio_only"

    # Turn on audio only (idempotent screen off)
    await sw_audio.async_turn_on()
    assert sw_audio.is_on is True
    mock_client.send_key.assert_any_call("KEY_INFO")
    mock_client.send_key.assert_any_call("KEY_AUDIO")

    # Turn off audio only (wake screen)
    mock_client.send_key.reset_mock()
    await sw_audio.async_turn_off()
    assert sw_audio.is_on is False
    mock_client.send_key.assert_called_once_with("KEY_INFO")

    # DebugLogging switch
    sw_debug = HisenseVidaaDebugLoggingSwitch(mock_client, mock_entry)
    sw_debug.hass = hass
    assert sw_debug.unique_id == "test_entry_id_debug_logging"

    await sw_debug.async_turn_on()
    assert sw_debug.is_on is True

    await sw_debug.async_turn_off()
    assert sw_debug.is_on is False


@pytest.mark.anyio
async def test_in_use_binary_sensor_and_live_tv_metadata(mock_client, mock_entry):
    """Test In Use binary sensor and Live TV broadcast attributes."""
    mock_client.state = "on"
    mock_client.connected = True
    mock_client.current_channel = "ABC HD"
    mock_client.channel_number = "20"
    mock_client.current_program = "News 7pm"

    bin_in_use = HisenseVidaaInUseBinarySensor(mock_client, mock_entry)
    assert bin_in_use.is_on is True
    assert bin_in_use.extra_state_attributes["channel_name"] == "ABC HD"
    assert bin_in_use.extra_state_attributes["channel_number"] == "20"
    assert bin_in_use.extra_state_attributes["program_title"] == "News 7pm"
