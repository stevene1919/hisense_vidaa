"""Tests for settings parser and probe module."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hisense_vidaa.tv.probe import (
    generate_markdown_report,
    load_credentials_file,
    probe_tv_features,
    save_credentials_file,
)
from custom_components.hisense_vidaa.tv.settings import (
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
