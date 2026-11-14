"""Tests for settings parser and probe module."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.vidaa.tv.probe import (
    create_client_from_creds,
    generate_markdown_report,
    load_credentials_file,
    probe_tv_features,
    save_credentials_file,
)
from custom_components.vidaa.tv.settings import (
    DEFAULT_MENU_ID_BACKLIGHT,
    SettingMenuItem,
    find_menu_item_by_name,
    parse_settings_payload,
)


def test_parse_settings_payload() -> None:
    sample_payload = {
        "action": "get_menu_info",
        "menu_info": [
            {
                "menu_id": 0,
                "menu_name": "Picture Mode",
                "menu_type": "list",
                "menu_value": "Standard",
                "menu_opts": ["Standard", "Cinema Day", "Cinema Night", "Dynamic", "Sports"],
            },
            {
                "menu_id": 1,
                "menu_name": "Backlight",
                "menu_type": "slider",
                "menu_value": 80,
                "min_value": 0,
                "max_value": 100,
            },
            {
                "menu_id": 2,
                "menu_name": "Brightness",
                "menu_type": "slider",
                "menu_value": 50,
            },
        ],
    }

    parsed = parse_settings_payload(sample_payload)
    assert len(parsed) == 3
    assert parsed[0].menu_name == "Picture Mode"
    assert parsed[0].value == "Standard"
    assert parsed[0].options == ["Standard", "Cinema Day", "Cinema Night", "Dynamic", "Sports"]
    assert parsed[1].menu_name == "Backlight"
    assert parsed[1].value == 80

    item = find_menu_item_by_name(parsed, "Backlight", DEFAULT_MENU_ID_BACKLIGHT)
    assert item is not None
    assert item.menu_id == 1

    item_missing = find_menu_item_by_name(parsed, "NonExistent", 999)
    assert item_missing is None


def test_probe_tv_features_and_report(tmp_path) -> None:
    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.picture_settings = [
        SettingMenuItem(menu_id=0, name="Picture Mode", value="Cinema Day", options=["Standard", "Cinema Day"]),
        SettingMenuItem(menu_id=1, name="Backlight", value=75),
    ]
    mock_client.sound_settings = [
        SettingMenuItem(menu_id=0, name="Sound Mode", value="Theater", options=["Standard", "Theater", "Music"]),
    ]
    mock_client.apps = [{"name": "Netflix", "appId": "netflix"}, {"name": "YouTube", "appId": "youtube"}]
    mock_client.sources = [{"sourceid": "1", "sourcename": "HDMI 1", "is_signal": "1"}]

    probe_res = probe_tv_features(mock_client, wait_time=0.01)
    assert probe_res.connected is True
    assert len(probe_res.picture_settings) == 2
    assert len(probe_res.sound_settings) == 1
    assert len(probe_res.apps) == 2

    ping_data = {
        "tcp_port_open": True,
        "tls_handshake": True,
        "tls_version": "TLSv1.2",
        "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "mqtt_connected": True,
        "device_info": {
            "model_name": "65U7HAU",
            "manufacturer": "Hisense",
            "firmware_version": "V0000.01.00a.O0818",
            "platform": "6",
        },
        "auth_probe": {
            "modern_dynamic": {"supported": True, "rc": 0},
            "standard_dynamic": {"supported": True, "rc": 0},
            "legacy_static": {"supported": False, "rc": 5},
        },
    }

    report = generate_markdown_report(
        ip="192.168.50.12",
        ping_result=ping_data,
        probe_result=probe_res,
        mac="E8:51:77:EC:98:1C",
        version="1.2.0",
    )

    assert "### 📺 Hardware & System Information" in report
    assert "Hisense 65U7HAU" in report
    assert "Picture Mode" in report
    assert "Cinema Day" in report
    assert "HDMI 1" in report
    assert "Netflix" in report

    # Test load & save credentials
    creds_file = str(tmp_path / "test_creds.json")
    save_credentials_file(creds_file, {"ip_address": "192.168.50.12", "client_id": "test_id"})
    loaded = load_credentials_file(creds_file)
    assert loaded["ip_address"] == "192.168.50.12"
    assert loaded["client_id"] == "test_id"


def test_create_client_from_creds_passes_cert_paths_by_keyword(tmp_path) -> None:
    """create_client_from_creds must forward explicit cert/key paths unswapped (F3-leg1).

    resolve_certificates' signature is (auth_profile, certfile, keyfile); the old caller
    passed (certfile, keyfile) positionally, so auth_profile became the cert path and the
    key path landed in certfile.
    """
    cert = tmp_path / "client_cert.pem"
    key = tmp_path / "client_key.pem"
    cert.write_text("CERT")
    key.write_text("KEY")

    client = create_client_from_creds(
        {"ip_address": "192.168.50.12"},
        certfile=str(cert),
        keyfile=str(key),
        auth_profile="modern",
    )

    assert client.certfile == str(cert)
    assert client.keyfile == str(key)


def test_report_no_false_rejection_when_tv_unreachable() -> None:
    """A TV that is off/unreachable reports rc=None for every tier — not a rejection.

    The report must NOT diagnose "all authentication profiles rejected (rc=5)"
    when no profile was ever actually rejected by the broker (TCP/TLS failed).
    """
    ping_data = {
        "tcp_port_open": False,
        "tls_handshake": False,
        "mqtt_connected": False,
        "client_cert_presented": False,
        "device_info": {},
        "auth_probe": {
            "legacy_static": {"supported": False, "rc": None},
            "standard_dynamic": {"supported": False, "rc": None},
            "middle_dynamic": {"supported": False, "rc": None},
            "modern_dynamic": {"supported": False, "rc": None},
        },
    }

    report = generate_markdown_report(
        ip="192.0.2.1",
        ping_result=ping_data,
        probe_result=None,
        mac="E8:51:77:EC:98:1C",
        version="1.2.0",
    )

    assert "All standard authentication profiles rejected" not in report


def test_report_warns_on_real_rejection() -> None:
    """A broker that actually rejected every tier with rc=5 IS diagnosed."""
    ping_data = {
        "tcp_port_open": True,
        "tls_handshake": True,
        "tls_version": "TLSv1.2",
        "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
        "mqtt_connected": False,
        "client_cert_presented": False,
        "device_info": {"model_name": "65U7HAU"},
        "auth_probe": {
            "legacy_static": {"supported": False, "rc": 5},
            "standard_dynamic": {"supported": False, "rc": 5},
            "middle_dynamic": {"supported": False, "rc": 5},
            "modern_dynamic": {"supported": False, "rc": 5},
        },
    }

    report = generate_markdown_report(
        ip="192.168.50.12",
        ping_result=ping_data,
        probe_result=None,
        mac="E8:51:77:EC:98:1C",
        version="1.2.0",
    )

    assert "All standard authentication profiles rejected (rc=5)" in report


def test_setting_menu_item_menu_type():
    """SettingMenuItem correctly identifies select, slider, and value menu types."""
    select_item = SettingMenuItem(menu_id=1, name="Mode", value="A", options=["A", "B"])
    slider_item = SettingMenuItem(menu_id=2, name="Backlight", value=80, min_value=0, max_value=100)
    value_item = SettingMenuItem(menu_id=3, name="Version", value="1.0")

    assert select_item.menu_type == "select"
    assert select_item.is_select is True
    assert select_item.is_slider is False

    assert slider_item.menu_type == "slider"
    assert slider_item.is_slider is True
    assert slider_item.is_select is False

    assert value_item.menu_type == "value"
    assert value_item.is_slider is False
    assert value_item.is_select is False


def test_apply_picture_update_incremental_broadcast():
    """Verify apply_picture_update preserves menu metadata during incremental broadcast."""
    from custom_components.vidaa.tv.state import apply_picture_update, apply_sound_update

    mock_client = MagicMock()
    mock_client.picture_settings = {}
    mock_client.sound_settings = {}
    mock_client.picture_mode = None
    mock_client.backlight = None
    mock_client.sound_mode = None

    # 1. Full menu tree load from get_menu_info
    initial_payload = {
        "action": "get_menu_info",
        "menu_info": [
            {
                "menu_id": 91,
                "menu_name": "Picture Mode",
                "menu_value": "Standard",
                "menu_opts": ["Standard", "Cinema Day", "Cinema Night", "Dynamic"],
            },
            {
                "menu_id": 92,
                "menu_name": "Backlight",
                "menu_value": 75,
                "min_value": 0,
                "max_value": 100,
            },
        ],
    }
    apply_picture_update(mock_client, initial_payload)
    assert mock_client.picture_mode == "Standard"
    assert mock_client.backlight == 75
    assert mock_client.picture_settings[91].name == "Picture Mode"
    assert mock_client.picture_settings[91].options == ["Standard", "Cinema Day", "Cinema Night", "Dynamic"]
    assert mock_client.picture_settings[92].min_value == 0
    assert mock_client.picture_settings[92].max_value == 100

    # 2. Incremental broadcast update (notify_value_changed) from TV remote
    broadcast_payload = {
        "action": "notify_value_changed",
        "menu_id": 91,
        "menu_value": "Dynamic",
    }
    apply_picture_update(mock_client, broadcast_payload)
    # Must update picture_mode
    assert mock_client.picture_mode == "Dynamic"
    # Must preserve existing name, options, and update value
    assert mock_client.picture_settings[91].value == "Dynamic"
    assert mock_client.picture_settings[91].name == "Picture Mode"
    assert mock_client.picture_settings[91].options == ["Standard", "Cinema Day", "Cinema Night", "Dynamic"]

    # 3. Incremental backlight change
    backlight_broadcast = {
        "action": "notify_value_changed",
        "menu_id": 92,
        "menu_value": 90,
    }
    apply_picture_update(mock_client, backlight_broadcast)
    assert mock_client.backlight == 90
    assert mock_client.picture_settings[92].value == 90
    assert mock_client.picture_settings[92].name == "Backlight"
    assert mock_client.picture_settings[92].max_value == 100

    # 4. Fallback ID resolution when menu wasn't preloaded
    mock_client_unloaded = MagicMock()
    mock_client_unloaded.picture_settings = {}
    mock_client_unloaded.picture_mode = None
    apply_picture_update(mock_client_unloaded, broadcast_payload)
    assert mock_client_unloaded.picture_mode == "Dynamic"

    # 5. Sound mode incremental update
    sound_initial = {
        "action": "get_menu_info",
        "menu_info": [
            {
                "menu_id": 1,
                "menu_name": "Sound Mode",
                "menu_value": "Standard",
                "menu_opts": ["Standard", "Theatre", "Music"],
            }
        ],
    }
    apply_sound_update(mock_client, sound_initial)
    assert mock_client.sound_mode == "Standard"
    assert mock_client.sound_settings[1].name == "Sound Mode"

    sound_broadcast = {
        "action": "notify_value_changed",
        "menu_id": 1,
        "menu_value": "Theatre",
    }
    apply_sound_update(mock_client, sound_broadcast)
    assert mock_client.sound_mode == "Theatre"
    assert mock_client.sound_settings[1].value == "Theatre"
    assert mock_client.sound_settings[1].name == "Sound Mode"
    assert mock_client.sound_settings[1].options == ["Standard", "Theatre", "Music"]
