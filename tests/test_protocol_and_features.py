"""Tests for protocol and features subpackages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.hisense_vidaa.features.navigation import (
    change_source_by_name_or_id,
    cycle_tv_source,
    launch_app_by_name,
)
from custom_components.hisense_vidaa.features.probe import (
    probe_tv_features_and_report,
)
from custom_components.hisense_vidaa.features.settings import (
    SettingMenuItem,
    find_menu_item_by_name,
    parse_settings_payload,
)
from custom_components.hisense_vidaa.protocol.auth import (
    apply_mqtt_tls,
    is_token_expired,
    perform_token_refresh,
)
from custom_components.hisense_vidaa.protocol.topics import (
    TOPIC_BROADCAST_BASEPATH,
    TopicPaths,
    build_topic_paths,
)
from custom_components.hisense_vidaa.protocol.wol import send_wake_on_lan


def test_topic_paths() -> None:
    paths = build_topic_paths("test_client_123")
    assert isinstance(paths, TopicPaths)
    assert paths.ui == "/remoteapp/tv/ui_service/test_client_123/"
    assert paths.platform == "/remoteapp/tv/platform_service/test_client_123/"
    assert paths.mobile == "/remoteapp/mobile/test_client_123/"
    assert paths.remote == "/remoteapp/tv/remote_service/test_client_123/"
    assert paths.broadcast == TOPIC_BROADCAST_BASEPATH


def test_wake_on_lan_utilities() -> None:
    # Invalid or empty MAC
    assert send_wake_on_lan("") is False
    assert send_wake_on_lan("invalid-mac") is False

    with patch("socket.socket") as mock_socket:
        mock_sock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_sock_instance

        # Single valid MAC
        res = send_wake_on_lan("E8:51:77:EC:98:1C", ip="192.168.50.12")
        assert res is True
        assert mock_sock_instance.sendto.called

        # Multiple MACs
        res_multi = send_wake_on_lan(["E8:51:77:EC:98:1C", "E8:51:77:EC:98:1D"])
        assert res_multi is True


def test_token_expiration_logic() -> None:
    # 0 or None duration/time
    assert is_token_expired(None, None) is False
    assert is_token_expired(1000, 0) is False

    # Valid unexpired token (valid for 30 days, created just now)
    import time
    now = int(time.time())
    assert is_token_expired(now, 30) is False

    # Expired token (created 100 days ago)
    old_time = now - (100 * 86400)
    assert is_token_expired(old_time, 30) is True


def test_apply_mqtt_tls() -> None:
    mock_client = MagicMock()
    # SSL disabled
    apply_mqtt_tls(mock_client, certfile=None, keyfile=None, use_ssl=False)
    assert not mock_client.tls_set.called

    # SSL enabled without CA cert
    apply_mqtt_tls(mock_client, certfile="/fake/cert.pem", keyfile="/fake/key.pem", use_ssl=True)
    assert mock_client.tls_set.called
    assert mock_client.tls_insecure_set.called


def test_perform_token_refresh_validation() -> None:
    # Missing parameters returns None immediately
    assert perform_token_refresh(ip="192.168.50.12", client_id="", username="", refresh_token="") is None


def test_navigation_feature_helpers() -> None:
    mock_client = MagicMock()
    mock_client.apps = [{"appId": "netflix", "name": "Netflix", "url": "https://netflix.com"}]
    mock_client.sources = [{"sourceid": "1", "sourcename": "HDMI 1"}, {"sourceid": "2", "sourcename": "HDMI 2"}]
    mock_client.current_source = "HDMI 1"

    # Match and launch app
    assert launch_app_by_name(mock_client, "Netflix") is True
    mock_client.launch_app.assert_called_with("netflix", "Netflix", "https://netflix.com")

    # Match and change source
    assert change_source_by_name_or_id(mock_client, "HDMI 2") is True
    mock_client.change_source.assert_called_with("2", "HDMI 2")

    # Cycle source
    assert cycle_tv_source(mock_client) is True
    mock_client.change_source.assert_called_with("2", "HDMI 2")


def test_settings_item_and_probe_report() -> None:
    item = SettingMenuItem(menu_id=91, name="Picture Mode", value="Standard", options=["Standard", "Cinema"])
    assert item.menu_id == 91
    assert item.name == "Picture Mode"

    parsed = parse_settings_payload({"menu_info": [{"menu_id": 91, "menu_name": "Picture Mode", "menu_value": "Cinema"}]})
    found = find_menu_item_by_name(parsed, "Picture Mode", 91)
    assert found is not None
    assert found.value == "Cinema"

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.picture_settings = [item]
    mock_client.sound_settings = []
    mock_client.apps = []
    mock_client.sources = []

    report = probe_tv_features_and_report(
        client=mock_client,
        ping_result={"device_info": {"model_name": "TestTV"}, "tcp_port_open": True, "tls_handshake": True},
        ip="192.168.50.12",
        wait_time=0.01,
    )
    assert "TestTV" in report
    assert "Picture Mode" in report
