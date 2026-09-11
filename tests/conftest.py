"""Pytest fixtures for Hisense VIDAA unit test suite."""

import os
import sys
from unittest.mock import MagicMock

import pytest

# Ensure custom_components/hisense_vidaa is in Python path for test execution
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
INTEGRATION_DIR = os.path.join(PROJECT_DIR, "custom_components", "hisense_vidaa")

if INTEGRATION_DIR not in sys.path:
    sys.path.insert(0, INTEGRATION_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


class MockMQTTMessage:
    """Mock paho-mqtt message object."""

    def __init__(self, topic: str, payload: bytes | str):
        self.topic = topic
        self.payload = payload.encode("utf-8") if isinstance(payload, str) else payload


@pytest.fixture
def mock_mqtt_message():
    """Factory fixture to create mock MQTT messages."""
    def _create(topic: str, payload: str | bytes):
        return MockMQTTMessage(topic, payload)
    return _create


@pytest.fixture
def mock_paho_client(monkeypatch):
    """Mocks paho.mqtt.client.Client with simulated broker responses."""
    mock_client_instance = MagicMock()
    mock_client_instance.connect_async.return_value = 0
    mock_client_instance.disconnect.return_value = 0
    mock_client_instance.publish.return_value = (0, 1)
    mock_client_instance.subscribe.return_value = (0, 1)

    mock_client_class = MagicMock(return_value=mock_client_instance)
    monkeypatch.setattr("paho.mqtt.client.Client", mock_client_class)
    return mock_client_instance
