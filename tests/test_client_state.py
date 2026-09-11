"""Unit tests for HisenseTvClient state processing and callbacks."""

from unittest.mock import MagicMock

from client import HisenseTvClient
from const import KEY_ALIASES


def test_key_aliases():
    """Verify common friendly remote key names map correctly to VIDAA hardware codes."""
    assert KEY_ALIASES["power"] == "KEY_POWER"
    assert KEY_ALIASES["volume_up"] == "KEY_VOLUMEUP"
    assert KEY_ALIASES["volume_down"] == "KEY_VOLUMEDOWN"
    assert KEY_ALIASES["mute"] == "KEY_MUTE"
    assert KEY_ALIASES["home"] == "KEY_HOME"
    assert KEY_ALIASES["menu"] == "KEY_MENU"
    assert KEY_ALIASES["back"] == "KEY_RETURNS"
    assert KEY_ALIASES["ok"] == "KEY_OK"
    assert KEY_ALIASES["voice_up"] == "KEY_VOICEUP"
    assert KEY_ALIASES["dot"] == "KEY_CHANNELDOT"
    assert KEY_ALIASES["mouse_up"] == "KEY_UDULEFTMOUSEKEYS"
    assert KEY_ALIASES["audio_only"] == "KEY_AUDIO"
    assert KEY_ALIASES["screen_off"] == "KEY_AUDIO"


def test_state_dispatch_callbacks():
    """Test state update messages trigger registered callbacks with parsed data."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="test_client")
    client.define_topic_paths()

    received_state = []
    received_volume = []
    received_apps = []
    received_sources = []

    client.register_state_callback(lambda data: received_state.append(data))
    client.register_volume_callback(lambda data: received_volume.append(data))
    client.register_applist_callback(lambda data: received_apps.append(data))
    client.register_sourcelist_callback(lambda data: received_sources.append(data))

    mock_msg = MagicMock()

    # 1. State update message on broadcast topic
    mock_msg.topic = client.topicBrcsBasepath + "ui_service/state"
    mock_msg.payload = b'{"statetype": "fake_sleep_0"}'
    client._on_message(None, None, mock_msg)
    assert len(received_state) == 1
    assert received_state[0]["statetype"] == "fake_sleep_0"

    # 2. Volume update message on broadcast topic
    mock_msg.topic = client.topicBrcsBasepath + "platform_service/actions/volumechange"
    mock_msg.payload = b'{"volume_value": 25, "volume_type": 0}'
    client._on_message(None, None, mock_msg)
    assert len(received_volume) == 1
    assert received_volume[0]["volume_value"] == 25

    # 3. App list update message
    mock_msg.topic = client.topicMobiBasepath + "ui_service/data/applist"
    mock_msg.payload = b'[{"appId": "1", "appName": "Netflix", "appUrl": "netflix://"}, {"appId": "2", "appName": "YouTube", "appUrl": "youtube://"}]'
    client._on_message(None, None, mock_msg)
    assert len(received_apps) == 1
    assert len(received_apps[0]) == 2
    assert received_apps[0][0]["appName"] == "Netflix"

    # 4. Source list update message
    mock_msg.topic = client.topicMobiBasepath + "ui_service/data/sourcelist"
    mock_msg.payload = b'[{"sourceId": "1", "sourceName": "HDMI 1"}, {"sourceId": "2", "sourceName": "HDMI 2 (eARC)"}]'
    client._on_message(None, None, mock_msg)
    assert len(received_sources) == 1
    assert len(received_sources[0]) == 2
    assert received_sources[0][0]["sourceName"] == "HDMI 1"


def test_volume_alternate_topic_dispatch():
    """Test volume update messages on alternate VIDAA firmware topics."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="test_client")
    client.define_topic_paths()

    received_volume = []
    client.on_volume_update = lambda data: received_volume.append(data)

    mock_msg = MagicMock()
    mock_msg.topic = client.topicBrcsBasepath + "ui_service/volume"
    mock_msg.payload = b'{"volume_value": 42, "volume_type": 0}'
    client._on_message(None, None, mock_msg)

    assert len(received_volume) == 1
    assert received_volume[0]["volume_value"] == 42


def test_wake_on_lan_subnet_broadcast():
    """Test Wake-on-LAN sends magic packets to both subnet directed broadcast and 255.255.255.255."""
    from unittest.mock import patch

    sent_targets = []

    def mock_sendto(self, data, addr):
        sent_targets.append(addr[0])
        return len(data)

    with patch("socket.socket.sendto", new=mock_sendto):
        result = HisenseTvClient.send_wake_on_lan(
            mac="e8:51:77:ec:98:1c",
            ip="192.168.50.12",
        )
        assert result is True
        assert "255.255.255.255" in sent_targets
        assert "192.168.50.255" in sent_targets


def test_callback_unregistration_and_safety():
    """Test callback registration, unregistration, and error isolation."""
    client = HisenseTvClient(ip="192.168.50.12")
    called = []

    def faulty_cb(data):
        raise RuntimeError("Isolated error")

    def good_cb(data):
        called.append(data)

    client.register_state_callback(faulty_cb)
    client.register_state_callback(good_cb)

    # Dispatch should not raise and should successfully call good_cb
    client._dispatch_state_update({"test": "ok"})
    assert len(called) == 1

    # Unregister
    client.unregister_state_callback(good_cb)
    client._dispatch_state_update({"test": "again"})
    assert len(called) == 1


def test_connected_and_disconnected_callbacks():
    """Test connected and disconnected callback lifecycle."""
    client = HisenseTvClient(ip="192.168.50.12")
    events = []

    def on_conn():
        events.append("connected")

    def on_disconn():
        events.append("disconnected")

    client.register_connected_callback(on_conn)
    client.register_disconnected_callback(on_disconn)

    client._dispatch_connected()
    assert events == ["connected"]

    client._dispatch_disconnected()
    assert events == ["connected", "disconnected"]

    client.unregister_connected_callback(on_conn)
    client.unregister_disconnected_callback(on_disconn)
    client._dispatch_connected()
    client._dispatch_disconnected()
    assert events == ["connected", "disconnected"]


def test_source_cycling_and_command_helpers():
    """Test cycle_source and send_command with input, source, and app prefixes."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="test_client")
    client.change_source = MagicMock()
    client.send_key = MagicMock()
    client.launch_app = MagicMock()

    client.sources = [
        {"sourceid": "0", "sourcename": "TV"},
        {"sourceid": "3", "sourcename": "HDMI1"},
        {"sourceid": "4", "sourcename": "HDMI2"},
    ]
    client.apps = [
        {"appId": "123", "name": "Stan", "url": "stan://"},
    ]
    client.current_source = "TV"

    # 1. Input cycling from TV -> HDMI1
    assert client.send_command("input") is True
    client.change_source.assert_called_with("3", "HDMI1")

    # 2. Cycling from HDMI1 -> HDMI2 with KEY_INPUT
    client.current_source = "HDMI1"
    assert client.send_command("KEY_INPUT") is True
    client.change_source.assert_called_with("4", "HDMI2")

    # 3. Cycling from HDMI2 -> TV (wraparound)
    client.current_source = "HDMI2"
    assert client.send_command("source") is True
    client.change_source.assert_called_with("0", "TV")

    # 4. Direct source targeting
    assert client.send_command("source:HDMI2") is True
    client.change_source.assert_called_with("4", "HDMI2")

    # 5. App targeting via app: prefix (case-insensitive and normalized)
    assert client.send_command("app:stan") is True
    client.launch_app.assert_called_with("123", "Stan", "stan://")

    # 6. Built-in app shortcuts
    assert client.send_command("app:netflix") is True
    client.send_key.assert_called_with("KEY_NETFLIX")

