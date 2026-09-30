"""Tests for Hisense VIDAA media player and remote control entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.media_player import HisenseVidaaMediaPlayer
from custom_components.hisense_vidaa.remote import HisenseVidaaRemote
from custom_components.hisense_vidaa.tv.settings import SettingMenuItem


def test_media_player_and_remote_device_info(mock_client, mock_entry):
    """Test device info registration for media player and remote."""
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
    """Test remote entity send command handling and burst/hold timings."""
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
    """Test media player play media with apps, URLs, and direct channel numbers."""
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
    """Test dynamic sound mode feature registration and fake sleep waking transitions."""
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

    # (c) a statetype containing "off" must be off — state.py and the media_player agree
    # (regression for leg4-F3: unknown off-ish statetypes flipping is_on True)
    mp._handle_state_update({"statetype": "poweroff"})
    assert mp.state == STATE_OFF
    assert mock_client.is_on is False

    # Sound update callback
    mp._handle_sound_update({"menu_id": "sound_mode", "value": "Speech"})


@pytest.mark.anyio
async def test_media_player_cec_source_naming(mock_client, mock_entry):
    """Test dynamic HDMI-CEC source labeling and label stripping on input change."""
    hass = MagicMock(spec=HomeAssistant)
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
    """Test idempotent power control on media player and remote."""
    hass = MagicMock(spec=HomeAssistant)
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
async def test_remote_send_command_num_repeats_option(mock_client, mock_entry):
    """[F1-leg4] The key_repeat option applies when HA sends the service default."""
    mock_entry.options = {"enable_remote": True, "key_repeat": 5}
    rem = HisenseVidaaRemote(client=mock_client, entry=mock_entry)

    # HA's remote.send_command schema always sends num_repeats (default 1): with the
    # service default the key_repeat option must be honoured.
    await rem.async_send_command(["up"], num_repeats=1, delay_secs=0)
    assert mock_client.send_command.call_count == 5

    # An explicit caller-supplied value still wins.
    mock_client.send_command.reset_mock()
    await rem.async_send_command(["up"], num_repeats=3, delay_secs=0)
    assert mock_client.send_command.call_count == 3


@pytest.mark.anyio
async def test_media_player_mute_is_idempotent(mock_client, mock_entry):
    """[F7-leg4] KEY_MUTE is only sent when the requested state differs from tracked."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mp = HisenseVidaaMediaPlayer(client=mock_client, entry=mock_entry)
    mp.hass = hass

    # Already unmuted → requesting unmute must not toggle the TV.
    mp._muted = False
    await mp.async_mute_volume(False)
    mock_client.send_key.assert_not_called()

    # Requesting mute differs → send KEY_MUTE.
    await mp.async_mute_volume(True)
    mock_client.send_key.assert_called_once_with("KEY_MUTE")

    # Already muted → requesting mute again must not toggle the TV.
    mp._muted = True
    mock_client.send_key.reset_mock()
    await mp.async_mute_volume(True)
    mock_client.send_key.assert_not_called()

    # Requesting unmute differs → send KEY_MUTE.
    await mp.async_mute_volume(False)
    mock_client.send_key.assert_called_once_with("KEY_MUTE")


def test_remote_off_ish_statetypes_stay_off(mock_client, mock_entry):
    """[F3-leg4 residual] remote statetype handling agrees with tv/state.py."""
    rem = HisenseVidaaRemote(client=mock_client, entry=mock_entry)
    rem.entity_id = "remote.living_room_tv"
    mock_client.connected = True

    # (a) an off-ish statetype after a remote callback must keep is_on False
    rem._handle_state_update({"statetype": "poweroff"})
    assert mock_client.is_on is False
    assert rem.is_on is False

    # (b) fake_sleep_1 means the TV is waking up → ON
    rem._handle_state_update({"statetype": "fake_sleep_1"})
    assert mock_client.is_on is True
    assert rem.is_on is True

    # (c) fake_sleep_0 (exact) → OFF
    rem._handle_state_update({"statetype": "fake_sleep_0"})
    assert mock_client.is_on is False
    assert rem.is_on is False


@pytest.mark.anyio
async def test_media_player_parses_camelcase_source_and_app_payloads(mock_client, mock_entry):
    """[F5-leg4] camelCase source/app payloads are keyed like the payload parsers."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mp = HisenseVidaaMediaPlayer(client=mock_client, entry=mock_entry)
    mp.hass = hass

    mp._handle_sourcelist_update(
        [{"sourceName": "HDMI 1", "sourceid": "HDMI1", "is_active": True}]
    )
    assert "HDMI 1" in mp._source_dict

    mp._handle_applist_update([{"appId": "1", "appName": "Netflix", "url": "netflix://"}])
    assert "Netflix" in mp._app_dict


def test_sourcelist_and_applist_parsers_accept_camelcase():
    """[F5-leg4] The data parsers accept the same spellings as the payload parsers."""
    from custom_components.hisense_vidaa.tv.media import (
        parse_applist_data,
        parse_sourcelist_data,
    )

    assert parse_sourcelist_data([{"sourceName": "HDMI 1"}]) == {
        "HDMI 1": {"sourceName": "HDMI 1"}
    }
    assert parse_sourcelist_data([{"sourcename": "TV"}]) == {"TV": {"sourcename": "TV"}}
    assert parse_applist_data([{"appId": "1", "appName": "Netflix"}])[1] == {
        "Netflix": {"appId": "1", "appName": "Netflix"}
    }
    assert parse_applist_data([{"name": "Stan"}])[1] == {"Stan": {"name": "Stan"}}


@pytest.mark.anyio
async def test_media_player_play_media_accepts_alternate_app_keys(mock_client, mock_entry):
    """[F4-leg4] play_media must not raise KeyError on appId/url spelling variants."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mp = HisenseVidaaMediaPlayer(client=mock_client, entry=mock_entry)
    mp.hass = hass
    mp._app_dict = {"Stan": {"app_id": "123", "name": "Stan", "appUrl": "stan://"}}

    await mp.async_play_media("app", "Stan")
    mock_client.launch_app.assert_called_with("123", "Stan", "stan://")


@pytest.mark.anyio
async def test_media_player_string_volume_broadcast(mock_client, mock_entry):
    """[F9-leg4] String volume payloads are coerced like apply_volume_update."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mp = HisenseVidaaMediaPlayer(client=mock_client, entry=mock_entry)
    mp.hass = hass

    mp._handle_volume_update({"volume_type": "1", "volume_value": "35"})
    assert mp._volume == 35
    assert mp._volume_type == 1
    assert mp.volume_level == 0.35

    # Mute broadcast as a string
    mp._handle_volume_update({"volume_type": "2", "volume_value": "1"})
    assert mp._muted is True


@pytest.mark.anyio
async def test_remote_platform_purges_registry_when_disabled(
    mock_client, mock_entry, monkeypatch
):
    """[F10-leg4] remote registry entry is purged when the feature is disabled."""
    from custom_components.hisense_vidaa.const import CONF_ENABLE_REMOTE, DOMAIN
    from custom_components.hisense_vidaa.remote import async_setup_entry as async_setup_remote

    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_entry.entry_id: {"client": mock_client}}}
    mock_reg = MagicMock()
    mock_reg.async_get_entity_id.return_value = "remote.living_room_tv"
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get", lambda h: mock_reg
    )
    mock_entry.options = {CONF_ENABLE_REMOTE: False}

    entities = []
    await async_setup_remote(hass, mock_entry, lambda e: entities.extend(e))
    mock_reg.async_remove.assert_called_once_with("remote.living_room_tv")
    assert entities == []
