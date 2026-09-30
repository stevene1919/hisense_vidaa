"""Tests for protocol and tv subpackages."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from custom_components.hisense_vidaa.client import HisenseTvClient
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
from custom_components.hisense_vidaa.tv.navigation import (
    change_source_by_name_or_id,
    cycle_tv_source,
    launch_app_by_name,
)
from custom_components.hisense_vidaa.tv.probe import (
    probe_tv_features_and_report,
)
from custom_components.hisense_vidaa.tv.settings import (
    SettingMenuItem,
    find_menu_item_by_name,
    parse_settings_payload,
)


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


def test_perform_token_refresh_subscriptions() -> None:
    """Test that perform_token_refresh subscribes to exact topics rather than wildcard."""
    from unittest.mock import patch

    import paho.mqtt.client as mqtt

    subscribed_topics = []
    published_topics = []

    def fake_connect(self, ip, port, keepalive):
        # Simulate successful connect
        self.on_connect(self, None, None, 0)

    def fake_subscribe(self, topics, qos=0):
        subscribed_topics.append(topics)

    def fake_publish(self, topic, payload):
        published_topics.append((topic, payload))

    with patch.object(mqtt.Client, "connect", fake_connect), \
         patch.object(mqtt.Client, "subscribe", fake_subscribe), \
         patch.object(mqtt.Client, "publish", fake_publish), \
         patch.object(mqtt.Client, "loop_start"), \
         patch.object(mqtt.Client, "loop_stop"), \
         patch.object(mqtt.Client, "disconnect"):
        perform_token_refresh(
            ip="192.168.50.12",
            client_id="test_client_id",
            username="his$123",
            refresh_token="test_refresh_token",
            timeout=0.1,
        )

    assert len(subscribed_topics) == 1
    topics = subscribed_topics[0]
    # Verify exact topics were subscribed (avoiding wildcard # which modern TVs reject with SUBACK 128)
    assert ("/remoteapp/mobile/test_client_id/platform_service/data/tokenissuance", 0) in topics
    assert ("/remoteapp/mobile/test_client_id/platform_service/data/gettoken", 0) in topics


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


def test_dispatch_incoming_mqtt_message() -> None:
    from custom_components.hisense_vidaa.protocol.dispatcher import dispatch_incoming_mqtt_message

    mock_client = MagicMock()
    mock_client.ip = "192.168.50.12"
    mock_client.topicMobiBasepath = "hisense_sub_test/"
    mock_client.topicBrcsBasepath = "hisense_broadcast/"
    mock_client._auth_future = None
    mock_client._auth_code_future = None
    mock_client._token_future = None

    # Test state update dispatch
    dispatch_incoming_mqtt_message(mock_client, "hisense_broadcast/ui_service/state", '{"statetype": "app", "name": "Netflix"}')
    mock_client._dispatch_state_update.assert_called_with({"statetype": "app", "name": "Netflix"})

    # Test volume update dispatch
    dispatch_incoming_mqtt_message(mock_client, "hisense_broadcast/ui_service/volume", '{"volume_value": 25}')
    mock_client._dispatch_volume_update.assert_called_with({"volume_value": 25})

    # Test device info dispatch
    dispatch_incoming_mqtt_message(mock_client, "hisense_sub_test/platform_service/data/getdeviceinfo", '{"devicename": "Living Room TV"}')
    mock_client._dispatch_device_info_update.assert_called_with({"devicename": "Living Room TV"})


def test_test_tv_ssl_connection_unauthenticated():
    """Verify test_tv_ssl_connection allows testing TLS handshake without presenting client certificates."""
    from custom_components.hisense_vidaa.protocol.auth import test_tv_ssl_connection

    mock_sock = MagicMock()
    mock_ssock = MagicMock()
    mock_ssock.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)
    mock_ssock.version.return_value = "TLSv1.3"
    mock_ssock.__enter__.return_value = mock_ssock

    mock_ctx = MagicMock()
    mock_ctx.wrap_socket.return_value = mock_ssock

    with patch("socket.create_connection", return_value=mock_sock), \
         patch("ssl.SSLContext", return_value=mock_ctx):
        res = test_tv_ssl_connection("192.168.50.12")
        assert res["connected"] is True
        assert res["tls_version"] == "TLSv1.3"
        assert res["cipher"] == "TLS_AES_256_GCM_SHA384"
        assert res["client_cert_presented"] is False
        assert res["certfile"] is None


def test_ping_tv_client_cert_tracking():
    """Verify ping_tv accurately tracks whether client certificates were presented."""
    from custom_components.hisense_vidaa.protocol.ping import ping_tv

    mock_sock = MagicMock()
    with patch("socket.create_connection", return_value=mock_sock), \
         patch("custom_components.hisense_vidaa.protocol.ping.test_tv_ssl_connection", return_value={
             "connected": True,
             "tls_version": "TLSv1.3",
             "cipher": "TLS_AES_256_GCM_SHA384",
             "client_cert_presented": False,
             "certfile": None,
             "keyfile": None,
         }), \
         patch("custom_components.hisense_vidaa.protocol.ping.probe_tv_auth_methods", return_value={
             "legacy_static": {"rc": None, "supported": False},
             "standard_dynamic": {"rc": None, "supported": False},
             "middle_dynamic": {"rc": None, "supported": False},
             "modern_dynamic": {"rc": None, "supported": False},
             "client_cert_presented": False,
         }), \
         patch("custom_components.hisense_vidaa.protocol.ping.get_device_fingerprint", return_value={}):
        res = ping_tv("192.168.50.12")
        assert res["tcp_port_open"] is True
        assert res["tls_handshake"] is True
        assert res["client_cert_presented"] is False


def test_on_connect_subscribes_client_own_mobile_push_tree() -> None:
    """F8-leg3: the live session must subscribe the client's own mobile/<cid>/# tree."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="cid", username="his$1", access_token="tok")
    mqtt_mock = MagicMock()
    client.mqtt_client = mqtt_mock
    with patch.object(client, "query_initial_state"):
        client._on_connect(mqtt_mock, None, None, 0)

    subscribed: list[str] = []
    for call in mqtt_mock.subscribe.call_args_list:
        for topic, _qos in call.args[0]:
            subscribed.append(topic)

    assert client.topicMobiBasepath + "#" in subscribed
    client.disconnect()


def test_query_initial_state_requests_capability() -> None:
    """F7-leg3: query_initial_state must publish ui_service/actions/capability (empty payload)."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="cid")
    mqtt_mock = MagicMock()
    client.mqtt_client = mqtt_mock
    client.connected = True

    client.query_initial_state()

    capability_topic = client.topicTVUIBasepath + "actions/capability"
    published = {c.args[0]: c.args[1] for c in mqtt_mock.publish.call_args_list}
    assert capability_topic in published
    assert published[capability_topic] == ""
