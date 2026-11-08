"""Tests for Hisense VIDAA select, number platforms and entity availability matrix."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.vidaa.number import (
    HisenseVidaaBacklightNumber,
    HisenseVidaaBrightnessNumber,
    HisenseVidaaContrastNumber,
)
from custom_components.vidaa.select import (
    AUDIO_OUTPUT_TV_SPEAKERS,
    HisenseVidaaAudioOutputSelect,
    HisenseVidaaPictureModeSelect,
    HisenseVidaaSoundModeSelect,
)
from custom_components.vidaa.switch import HisenseVidaaAudioOnlySwitch
from custom_components.vidaa.tv.settings import SettingMenuItem


@pytest.mark.anyio
async def test_select_entity(mock_client, mock_entry):
    """Test Audio Output select entity and volume update filtering."""
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
    """Test Picture Mode and Sound Mode select dropdowns."""
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
    """Test Picture calibration number slider entities (Backlight, Brightness, Contrast)."""
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
async def test_select_and_number_platforms_lifecycle(mock_client, mock_entry, monkeypatch):
    """Test select and number platforms creation, options gating, and lifecycle unregistration."""
    from custom_components.vidaa.const import (
        CONF_ENABLE_PICTURE_CONTROLS,
        CONF_ENABLE_SOUND_CONTROLS,
        DOMAIN,
    )
    from custom_components.vidaa.number import async_setup_entry as async_setup_number
    from custom_components.vidaa.select import async_setup_entry as async_setup_select

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
    from custom_components.vidaa.binary_sensor import HisenseVidaaMqttConnectedBinarySensor
    from custom_components.vidaa.button import (
        HisenseVidaaForceReconnectButton,
        HisenseVidaaTriggerReauthButton,
    )
    from custom_components.vidaa.number import HisenseVidaaBacklightNumber
    from custom_components.vidaa.select import HisenseVidaaPictureModeSelect
    from custom_components.vidaa.sensor import HisenseVidaaActiveSourceSensor, HisenseVidaaSessionStatusSensor
    from custom_components.vidaa.switch import (
        HisenseVidaaAudioOnlySwitch,
        HisenseVidaaDebugLoggingSwitch,
    )

    s_status = HisenseVidaaSessionStatusSensor(mock_client, mock_entry)
    s_source = HisenseVidaaActiveSourceSensor(mock_client, mock_entry)
    bs_mqtt = HisenseVidaaMqttConnectedBinarySensor(mock_client, mock_entry)
    btn_reconnect = HisenseVidaaForceReconnectButton(mock_client, mock_entry)
    btn_reauth = HisenseVidaaTriggerReauthButton(mock_client, mock_entry)
    sw_debug = HisenseVidaaDebugLoggingSwitch(mock_client, mock_entry)
    sw_audio = HisenseVidaaAudioOnlySwitch(mock_client, mock_entry)
    sel_pic = HisenseVidaaPictureModeSelect(mock_client, mock_entry)
    num_backlight = HisenseVidaaBacklightNumber(mock_client, mock_entry)

    # 1. When connected: all entities available
    mock_client.connected = True
    assert s_status.available is True
    assert s_source.available is True
    assert bs_mqtt.available is True
    assert btn_reconnect.available is True
    assert btn_reauth.available is True
    assert sw_debug.available is True
    assert sw_audio.available is True
    assert sel_pic.available is True
    assert num_backlight.available is True

    # 2. When disconnected (standby): status sensors, buttons, and diagnostic switches stay available
    mock_client.connected = False
    assert s_status.available is True
    assert bs_mqtt.available is True
    assert btn_reconnect.available is True
    assert btn_reauth.available is True
    assert sw_debug.available is True

    # Control entities become unavailable while TV is offline
    assert sw_audio.available is False
    assert sel_pic.available is False
    assert num_backlight.available is False


def test_select_audio_output_string_volume_type(mock_client, mock_entry):
    """[F9-leg4] The audio-output select coerces string volume_type broadcasts."""
    sel = HisenseVidaaAudioOutputSelect(client=mock_client, entry=mock_entry)
    assert sel.current_option == "TV Speakers"

    sel._handle_volume_update({"volume_type": "1"})
    assert sel.current_option == "ARC / eARC"

    # A mute broadcast (type 2) must not change the audio output selection.
    sel._handle_volume_update({"volume_type": "2", "volume_value": "0"})
    assert sel.current_option == "ARC / eARC"


@pytest.mark.anyio
async def test_entities_register_connection_callbacks():
    """Select, number, and switch entities register connect/disconnect callbacks."""
    client = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry123"

    audio_sel = HisenseVidaaAudioOutputSelect(client, entry)
    pic_sel = HisenseVidaaPictureModeSelect(client, entry)
    snd_sel = HisenseVidaaSoundModeSelect(client, entry)
    num_ent = HisenseVidaaBacklightNumber(client, entry)
    sw_ent = HisenseVidaaAudioOnlySwitch(client, entry)

    # AudioOutputSelect
    await audio_sel.async_added_to_hass()
    client.register_connected_callback.assert_called()
    client.register_disconnected_callback.assert_called()
    client.reset_mock()

    # PictureModeSelect
    await pic_sel.async_added_to_hass()
    client.register_connected_callback.assert_called()
    client.register_disconnected_callback.assert_called()
    client.reset_mock()

    # SoundModeSelect
    await snd_sel.async_added_to_hass()
    client.register_connected_callback.assert_called()
    client.register_disconnected_callback.assert_called()
    client.reset_mock()

    # Number entity
    await num_ent.async_added_to_hass()
    client.register_connected_callback.assert_called()
    client.register_disconnected_callback.assert_called()
    client.reset_mock()

    # Switch entity
    await sw_ent.async_added_to_hass()
    client.register_connected_callback.assert_called()
    client.register_disconnected_callback.assert_called()


@pytest.mark.anyio
async def test_audio_output_select_dynamic_item_and_no_mute_corruption():
    """AudioOutputSelect uses sound menu item if available and avoids setting volume_type=2."""
    client = MagicMock()
    client.send_key = AsyncMock()
    client.async_send_key = AsyncMock()
    client.async_set_setting = AsyncMock()
    client.sound_settings = {
        10: SettingMenuItem(
            menu_id=10,
            name="Audio Output",
            value="TV Speakers",
            options=["TV Speakers", "ARC / eARC", "Bluetooth"],
        )
    }
    entry = MagicMock()
    entry.entry_id = "entry123"

    sel = HisenseVidaaAudioOutputSelect(client, entry)
    sel.hass = MagicMock()

    # When dynamic setting is present, async_set_setting is used
    await sel.async_select_option("Bluetooth")
    client.async_set_setting.assert_awaited_once_with(10, "Bluetooth")

    # When dynamic setting is absent
    client.sound_settings = {}
    await sel.async_select_option(AUDIO_OUTPUT_TV_SPEAKERS)
    assert sel._volume_type == 0

