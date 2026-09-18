"""Tests for Hisense VIDAA sensors, binary sensors, and buttons."""

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
    HisenseVidaaSyncClockButton,
)
from custom_components.hisense_vidaa.media_player import HisenseVidaaMediaPlayer
from custom_components.hisense_vidaa.notify import HisenseVidaaNotifyEntity
from custom_components.hisense_vidaa.number import (
    HisenseVidaaBacklightNumber,
    HisenseVidaaBrightnessNumber,
    HisenseVidaaContrastNumber,
)
from custom_components.hisense_vidaa.remote import HisenseVidaaRemote
from custom_components.hisense_vidaa.select import (
    HisenseVidaaAudioOutputSelect,
    HisenseVidaaPictureModeSelect,
    HisenseVidaaSoundModeSelect,
)
from custom_components.hisense_vidaa.sensor import (
    HisenseVidaaActiveAppSensor,
    HisenseVidaaActiveSourceSensor,
    HisenseVidaaAudioOutputSensor,
    HisenseVidaaAuthProfileSensor,
    HisenseVidaaReportedNameSensor,
    HisenseVidaaSessionStatusSensor,
)
from custom_components.hisense_vidaa.tv.actions import turn_off_tv, turn_on_tv


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
    client.device_name = None
    client.model_name = None
    client.manufacturer = None
    client.firmware_version = None
    client.turn_on.side_effect = lambda mac_targets=None: turn_on_tv(client, mac_targets)
    client.turn_off.side_effect = lambda: turn_off_tv(client)
    return client


@pytest.mark.anyio
async def test_sensor_entities(mock_client, mock_entry):
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
    bs_mqtt = HisenseVidaaMqttConnectedBinarySensor(mock_client, mock_entry)
    assert bs_mqtt.is_on is True


@pytest.mark.anyio
async def test_button_entities(mock_client, mock_entry, monkeypatch):
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


def test_media_player_and_remote_device_info(mock_client, mock_entry):
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        entry=mock_entry,
    )
    dev_info = mp.device_info
    assert mp.device_class == MediaPlayerDeviceClass.TV
    assert dev_info["identifiers"] == {("hisense_vidaa", "test_entry_id")}
    assert dev_info["model"] == "65U7G"
    assert dev_info["manufacturer"] == "Hisense"
    assert dev_info["sw_version"] == "V1.0"

    rem = HisenseVidaaRemote(
        client=mock_client,
        entry=mock_entry,
    )
    rem_info = rem.device_info
    assert rem_info["identifiers"] == {("hisense_vidaa", "test_entry_id")}
    assert rem_info["model"] == "65U7G"


@pytest.mark.anyio
async def test_remote_send_command(mock_client, mock_entry):
    rem = HisenseVidaaRemote(
        client=mock_client,
        entry=mock_entry,
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


@pytest.mark.anyio
async def test_media_player_play_media(mock_client, mock_entry):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        entry=mock_entry,
    )
    mp.hass = hass
    mp._app_dict = {"Netflix": {"appId": "1", "name": "Netflix", "url": "netflix://"}}

    # App launch by name
    await mp.async_play_media("app", "Netflix")
    mock_client.launch_app.assert_called_with("1", "Netflix", "netflix://")

    # Deep link URL
    await mp.async_play_media("url", "https://youtube.com/watch?v=123")
    mock_client.launch_app.assert_called_with("", "https://youtube.com/watch?v=123", "https://youtube.com/watch?v=123")

    # Channel tuning with dot
    mock_client.send_key.reset_mock()
    await mp.async_play_media("channel", "7.1")
    assert mock_client.send_key.call_count == 3


@pytest.mark.anyio
async def test_media_player_sound_mode_and_waking_state(mock_client, mock_entry):
    from homeassistant.components.media_player import MediaPlayerEntityFeature
    from homeassistant.const import STATE_OFF, STATE_ON

    from custom_components.hisense_vidaa.tv.settings import SettingMenuItem

    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        entry=mock_entry,
    )
    mp.hass = hass

    # 1. When TV does NOT report sound mode settings: feature is omitted and sound_mode_list is None
    mock_client.sound_settings = {}
    mock_client.sound_mode = None
    assert mp.sound_mode_list is None
    assert bool(mp.supported_features & MediaPlayerEntityFeature.SELECT_SOUND_MODE) is False

    # 2. When TV reports sound mode menu options: feature is enabled dynamically
    sm_item = SettingMenuItem(menu_id=1, name="Sound Mode", value="Standard", options=["Standard", "Theatre", "Music"])
    mock_client.sound_settings = {1: sm_item}
    mock_client.sound_mode = "Theatre"
    assert mp.sound_mode == "Theatre"
    assert mp.sound_mode_list == ["Standard", "Theatre", "Music"]
    assert bool(mp.supported_features & MediaPlayerEntityFeature.SELECT_SOUND_MODE) is True

    # Select sound mode
    await mp.async_select_sound_mode("Music")
    mock_client.set_sound_mode.assert_called_with("Music")

    # Waking state transition: fake_sleep_1
    mp._handle_state_update({"statetype": "fake_sleep_0"})
    assert mp.state == STATE_OFF
    assert mock_client.is_on is False

    mp._handle_state_update({"statetype": "fake_sleep_1"})
    assert mp.state == STATE_ON
    assert mock_client.is_on is True

    # Sound update callback
    mp._handle_sound_update({"menu_id": "sound_mode", "value": "Speech"})


@pytest.mark.anyio
async def test_notify_entity(mock_client, mock_entry):
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    notify = HisenseVidaaNotifyEntity(
        client=mock_client,
        entry=mock_entry,
    )
    notify.hass = hass
    assert notify.available is True
    assert notify.unique_id == "test_entry_id_notify"

    await notify.async_send_message("Someone is at the front door!", "Doorbell")
    mock_client.show_message.assert_called_with("Someone is at the front door!", "Doorbell")


@pytest.mark.anyio
async def test_select_entity(mock_client, mock_entry):
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    sel = HisenseVidaaAudioOutputSelect(
        client=mock_client,
        entry=mock_entry,
    )
    sel.hass = hass
    sel.entity_id = "select.audio_output"
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

    # Mute broadcast (volume_type: 2) must not change audio output selection
    sel._handle_volume_update({"volume_type": 2, "volume_value": 0})
    assert sel.current_option == "TV Speakers"


@pytest.mark.anyio
async def test_picture_and_sound_mode_selects(mock_client, mock_entry):
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    pic_sel = HisenseVidaaPictureModeSelect(
        client=mock_client,
        entry=mock_entry,
    )
    pic_sel.hass = hass
    pic_sel.entity_id = "select.picture_mode"
    assert pic_sel.unique_id == "test_entry_id_picture_mode"
    assert "Standard" in pic_sel.options

    await pic_sel.async_select_option("Cinema Day")
    mock_client.set_picture_mode.assert_called_with("Cinema Day")

    snd_sel = HisenseVidaaSoundModeSelect(
        client=mock_client,
        entry=mock_entry,
    )
    snd_sel.hass = hass
    snd_sel.entity_id = "select.sound_mode"
    assert snd_sel.unique_id == "test_entry_id_sound_mode"
    assert "Standard" in snd_sel.options

    await snd_sel.async_select_option("Theater")
    mock_client.set_sound_mode.assert_called_with("Theater")


@pytest.mark.anyio
async def test_picture_calibration_numbers(mock_client, mock_entry):
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    bl = HisenseVidaaBacklightNumber(
        client=mock_client,
        entry=mock_entry,
    )
    bl.hass = hass
    bl.entity_id = "number.backlight"
    assert bl.unique_id == "test_entry_id_backlight"
    assert bl.native_min_value == 0
    assert bl.native_max_value == 100
    await bl.async_set_native_value(85)
    mock_client.set_backlight.assert_called_with(85)

    br = HisenseVidaaBrightnessNumber(
        client=mock_client,
        entry=mock_entry,
    )
    br.hass = hass
    br.entity_id = "number.brightness"
    assert br.unique_id == "test_entry_id_brightness"
    await br.async_set_native_value(52)
    mock_client.set_brightness.assert_called_with(52)

    ct = HisenseVidaaContrastNumber(
        client=mock_client,
        entry=mock_entry,
    )
    ct.hass = hass
    ct.entity_id = "number.contrast"
    assert ct.unique_id == "test_entry_id_contrast"
    await ct.async_set_native_value(90)
    mock_client.set_contrast.assert_called_with(90)


@pytest.mark.anyio
async def test_media_player_cec_source_naming(mock_client, mock_entry):
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_entry.options = {"enable_cec_names": True, "include_apps_in_sources": True}
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        entry=mock_entry,
    )
    mp.hass = hass
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
    await mp.async_select_source("HDMI2 (PlayStation 5)")
    mock_client.change_source.assert_called_with("HDMI2", "HDMI2")


@pytest.mark.anyio
async def test_remote_and_media_player_idempotent_power_control(mock_client, mock_entry):
    import threading
    hass = MagicMock(spec=HomeAssistant)
    hass.loop_thread_id = threading.get_ident()
    hass.loop = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    rem = HisenseVidaaRemote(
        client=mock_client,
        entry=mock_entry,
    )
    rem.hass = hass
    rem.entity_id = "remote.living_room_tv"

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
        entry=mock_entry,
    )
    mp.hass = hass
    assert mp.state == "on"

    # Calling turn_on when already connected & on must NOT send KEY_POWER
    mock_client.send_key.reset_mock()
    await mp.async_turn_on()
    mock_client.send_key.assert_not_called()
    assert mp.state == "on"

    # In fake sleep, turn_on should wake display
    mp._handle_state_update({"statetype": "fake_sleep_0"})
    assert mp.state == "off"
    await mp.async_turn_on()
    mock_client.send_key.assert_called_once_with("KEY_POWER")
    assert mp.state == "on"


@pytest.mark.anyio
async def test_entry_lifecycle_setup_and_unload(mock_entry, mock_client, monkeypatch):
    """Test that setting up and unloading an entry only unloads enabled platforms."""
    from custom_components.hisense_vidaa import DOMAIN, async_setup_entry, async_unload_entry

    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()
    mock_client.disconnect = MagicMock()

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    # 1. Setup entry with notify and picture_controls disabled
    mock_entry.options = {"enable_remote": True, "enable_notify": False}
    result = await async_setup_entry(hass, mock_entry)
    assert result is True

    # Forward entry setups should have received 7 platforms (excluding notify and number)
    expected_platforms = ["media_player", "sensor", "binary_sensor", "button", "switch", "select", "remote"]
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(mock_entry, expected_platforms)
    assert hass.data[DOMAIN][mock_entry.entry_id]["platforms"] == expected_platforms

    # 2. Unload entry
    unload_result = await async_unload_entry(hass, mock_entry)
    assert unload_result is True
    # Unload platforms must ONLY be called with the 7 loaded platforms, never all PLATFORMS
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(mock_entry, expected_platforms)
    mock_client.disconnect.assert_called_once()
    assert mock_entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.anyio
async def test_switch_entities(mock_client, mock_entry):
    """Test AudioOnly and DebugLogging switch entities."""
    from custom_components.hisense_vidaa.switch import (
        HisenseVidaaAudioOnlySwitch,
        HisenseVidaaDebugLoggingSwitch,
    )

    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    # AudioOnly switch
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
    """Test In Use binary sensor and Live TV channel attributes on media player."""
    from custom_components.hisense_vidaa.binary_sensor import HisenseVidaaInUseBinarySensor

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

    # Media player series and title attributes
    mp = HisenseVidaaMediaPlayer(
        client=mock_client,
        entry=mock_entry,
    )
    mp._state = "on"
    assert mp.media_series_title == "ABC HD (20)"
    assert mp.media_title == "News 7pm"
    assert mp.extra_state_attributes["channel_name"] == "ABC HD"


@pytest.mark.anyio
async def test_select_and_number_platforms_lifecycle(mock_client, mock_entry, monkeypatch):
    """Test select and number platforms creation, options gating, and lifecycle unregistration."""
    from custom_components.hisense_vidaa.const import (
        CONF_ENABLE_PICTURE_CONTROLS,
        CONF_ENABLE_SOUND_CONTROLS,
        DOMAIN,
    )
    from custom_components.hisense_vidaa.number import async_setup_entry as async_setup_number
    from custom_components.hisense_vidaa.select import async_setup_entry as async_setup_select

    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_entry.entry_id: {"client": mock_client}}}
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_reg = MagicMock()
    mock_reg.async_get_entity_id.return_value = None
    monkeypatch.setattr("homeassistant.helpers.entity_registry.async_get", lambda h: mock_reg)

    # 1. Default options: picture and sound controls disabled
    mock_entry.options = {}
    default_select_entities = []
    await async_setup_select(hass, mock_entry, lambda entities: default_select_entities.extend(entities))
    assert len(default_select_entities) == 1  # Only audio output select

    default_number_entities = []
    await async_setup_number(hass, mock_entry, lambda entities: default_number_entities.extend(entities))
    assert len(default_number_entities) == 0

    # 2. Enabled options: picture and sound controls enabled
    mock_entry.options = {
        CONF_ENABLE_PICTURE_CONTROLS: True,
        CONF_ENABLE_SOUND_CONTROLS: True,
    }
    select_entities = []
    await async_setup_select(hass, mock_entry, lambda entities: select_entities.extend(entities))
    assert len(select_entities) == 3

    for sel in select_entities:
        await sel.async_added_to_hass()
        await sel.async_will_remove_from_hass()

    number_entities = []
    await async_setup_number(hass, mock_entry, lambda entities: number_entities.extend(entities))
    assert len(number_entities) == 3

    for num in number_entities:
        await num.async_added_to_hass()
        await num.async_will_remove_from_hass()


@pytest.mark.anyio
async def test_entity_availability_matrix(mock_client, mock_entry):
    """Test availability of various entities during online and offline TV states."""
    from custom_components.hisense_vidaa.binary_sensor import HisenseVidaaMqttConnectedBinarySensor
    from custom_components.hisense_vidaa.button import HisenseVidaaForceReconnectButton
    from custom_components.hisense_vidaa.number import HisenseVidaaBacklightNumber
    from custom_components.hisense_vidaa.select import HisenseVidaaPictureModeSelect
    from custom_components.hisense_vidaa.sensor import HisenseVidaaSessionStatusSensor
    from custom_components.hisense_vidaa.switch import (
        HisenseVidaaAudioOnlySwitch,
        HisenseVidaaDebugLoggingSwitch,
    )

    s_status = HisenseVidaaSessionStatusSensor(mock_client, mock_entry)
    bs_mqtt = HisenseVidaaMqttConnectedBinarySensor(mock_client, mock_entry)
    btn_reconnect = HisenseVidaaForceReconnectButton(mock_client, mock_entry)
    sw_debug = HisenseVidaaDebugLoggingSwitch(mock_client, mock_entry)
    sw_audio = HisenseVidaaAudioOnlySwitch(mock_client, mock_entry)
    sel_pic = HisenseVidaaPictureModeSelect(mock_client, mock_entry)
    num_backlight = HisenseVidaaBacklightNumber(mock_client, mock_entry)

    # 1. When connected: all entities available
    mock_client.connected = True
    assert s_status.available is True
    assert bs_mqtt.available is True
    assert btn_reconnect.available is True
    assert sw_debug.available is True
    assert sw_audio.available is True
    assert sel_pic.available is True
    assert num_backlight.available is True

    # 2. When disconnected (standby): status sensors, buttons, and diagnostic switches stay available
    mock_client.connected = False
    assert s_status.available is True
    assert bs_mqtt.available is True
    assert btn_reconnect.available is True
    assert sw_debug.available is True

    # Control entities become unavailable while TV is offline
    assert sw_audio.available is False
    assert sel_pic.available is False
    assert num_backlight.available is False




