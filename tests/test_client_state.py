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
