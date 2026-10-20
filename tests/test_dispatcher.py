"""Unit tests for the MQTT message dispatcher."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.protocol.dispatcher import (
    dispatch_incoming_mqtt_message,
    mask_sensitive_payload,
)


def _create_test_client() -> HisenseTvClient:
    """Create a client with initialized topics for dispatcher testing."""
    client = HisenseTvClient(ip="192.168.50.12", client_id="hisenseservice", auth_profile="legacy")
    client.update_topic_paths()
    return client


def test_dispatcher_connect_ack_does_not_resolve_pin_future() -> None:
    """connect_result acknowledgement must not resolve the challenge future."""
    client = _create_test_client()
    loop = asyncio.new_event_loop()
    try:
        client._auth_future = loop.create_future()
        client._connect_ack_future = loop.create_future()
        dispatch_incoming_mqtt_message(
            client,
            f"{client.topics.mobile}ui_service/data/vidaa_app_connect",
            '{"connect_result":1}',
        )
        assert not client._auth_future.done(), "connect-ACK must not resolve the PIN future"
        assert client._connect_ack_future.done(), "connect-ACK is tracked on its own future"
    finally:
        loop.close()


def test_dispatcher_auth_challenge_resolves_pin_future() -> None:
    """The .../data/authentication push is the PIN-shown signal."""
    client = _create_test_client()
    loop = asyncio.new_event_loop()
    try:
        client._auth_future = loop.create_future()
        dispatch_incoming_mqtt_message(
            client, f"{client.topics.mobile}ui_service/data/authentication", ""
        )
        assert client._auth_future.done()
        assert client._auth_future.result() == ""
    finally:
        loop.close()


def test_dispatcher_close_and_toast_resolve_pairing_event_future() -> None:
    """close -> 'closed', toast -> 'busy' on the dedicated event future."""
    client = _create_test_client()
    for topic_suffix, expected in (
        ("ui_service/data/authenticationcodetoast", "busy"),
        ("ui_service/data/authenticationcodeclose", "closed"),
    ):
        loop = asyncio.new_event_loop()
        try:
            fut = loop.create_future()
            client._pairing_event_future = fut
            dispatch_incoming_mqtt_message(client, f"{client.topics.mobile}{topic_suffix}", "")
            assert fut.done() and fut.result() == expected
        finally:
            loop.close()


def test_dispatcher_ignores_topic_with_foreign_client_id() -> None:
    """An exact-topic match, not a loose endswith on a foreign basepath."""
    client = _create_test_client()
    loop = asyncio.new_event_loop()
    try:
        client._auth_future = loop.create_future()
        dispatch_incoming_mqtt_message(
            client, "/remoteapp/mobile/someone_else/ui_service/data/authentication", ""
        )
        assert not client._auth_future.done()
    finally:
        loop.close()


def test_dispatcher_device_info_requires_exact_topic() -> None:
    """A getdeviceinfo/gettvinfo push on a foreign client-id basepath must not route."""
    client = _create_test_client()
    client._dispatch_device_info_update = MagicMock()

    # Foreign basepath: an endswith match would wrongly sweep this in
    dispatch_incoming_mqtt_message(
        client, "/remoteapp/mobile/someone_else/platform_service/data/getdeviceinfo", "{}"
    )
    dispatch_incoming_mqtt_message(
        client, "/remoteapp/mobile/someone_else/platform_service/data/gettvinfo", "{}"
    )
    assert not client._dispatch_device_info_update.called

    # Exact topic for this client routes correctly
    dispatch_incoming_mqtt_message(
        client, f"{client.topics.mobile}platform_service/data/getdeviceinfo", "{}"
    )
    assert client._dispatch_device_info_update.called


def test_mask_sensitive_payload_tokens() -> None:
    """Sensitive tokens and credentials in JSON payloads must be masked."""
    raw_payload = (
        '{"accesstoken": "super_secret_access_token_12345", '
        '"refreshtoken": "super_secret_refresh_token_67890", '
        '"accesstoken_time": 1729000000, '
        '"accesstoken_duration_day": 30, '
        '"refreshtoken_time": 1729000000, '
        '"refreshtoken_duration_day": 30}'
    )
    masked = mask_sensitive_payload(raw_payload, "/remoteapp/mobile/test/platform_service/data/tokenissuance")
    import json
    parsed = json.loads(masked)
    assert parsed["accesstoken"] == "***"
    assert parsed["refreshtoken"] == "***"
    assert parsed["accesstoken_time"] == 1729000000
    assert parsed["accesstoken_duration_day"] == 30
    assert parsed["refreshtoken_time"] == 1729000000
    assert parsed["refreshtoken_duration_day"] == 30
    assert "super_secret" not in masked


def test_mask_sensitive_payload_token_topics_fallback() -> None:
    """Non-JSON or malformed payloads on token topics must be replaced with [payload masked]."""
    raw_payload = "raw_unformatted_secret_token_12345"
    masked = mask_sensitive_payload(raw_payload, "/remoteapp/mobile/test/platform_service/data/tokenissuance")
    assert masked == "[payload masked]"
    assert "secret" not in masked

    masked_gettoken = mask_sensitive_payload(raw_payload, "/remoteapp/mobile/test/platform_service/data/gettoken")
    assert masked_gettoken == "[payload masked]"


def test_mask_sensitive_payload_regex_fallback() -> None:
    """Malformed JSON containing tokens on non-token topics must be masked via regex."""
    malformed = '{"accesstoken": "secret_abc_123", "broken_json": '
    masked = mask_sensitive_payload(malformed, "/some/other/topic")
    assert '"accesstoken": "***"' in masked
    assert "secret_abc_123" not in masked


def test_mask_sensitive_payload_preserves_non_sensitive_data() -> None:
    """Non-sensitive payloads should pass through intact."""
    assert mask_sensitive_payload("") == ""
    normal_payload = '{"statetype": "fake_sleep_0", "volume": 20}'
    masked = mask_sensitive_payload(normal_payload, "/remoteapp/tv/broadcast/ui_service/state")
    assert masked == normal_payload


def test_dispatcher_masks_token_payload_in_debug_logs(caplog) -> None:
    """Verify that dispatching incoming token messages masks tokens in debug logs."""
    import logging
    client = _create_test_client()
    raw_payload = (
        '{"accesstoken": "LEAK_SECRET_ACCESS_TOKEN", '
        '"refreshtoken": "LEAK_SECRET_REFRESH_TOKEN", '
        '"accesstoken_duration_day": 30}'
    )
    topic = f"{client.topics.mobile}platform_service/data/tokenissuance"

    with caplog.at_level(logging.DEBUG):
        dispatch_incoming_mqtt_message(client, topic, raw_payload)

    log_output = caplog.text
    assert "LEAK_SECRET_ACCESS_TOKEN" not in log_output
    assert "LEAK_SECRET_REFRESH_TOKEN" not in log_output
    assert "***" in log_output
    assert "accesstoken" in log_output
    assert "30" in log_output


def test_auth_token_message_masks_tokens_in_debug_logs(caplog) -> None:
    """Verify that on_token_message in perform_token_refresh masks debug logs."""
    import logging
    from unittest.mock import MagicMock, patch

    import paho.mqtt.client as mqtt

    from custom_components.hisense_vidaa.protocol.auth import perform_token_refresh

    raw_payload = (
        '{"accesstoken": "AUTH_REFRESH_SECRET_ACCESS", '
        '"refreshtoken": "AUTH_REFRESH_SECRET_REFRESH", '
        '"accesstoken_duration_day": 30}'
    )

    def fake_connect(self, ip, port, keepalive):
        self.on_connect(self, None, None, 0)
        # Simulate incoming token message immediately
        msg = MagicMock()
        msg.topic = "/remoteapp/mobile/test_client/platform_service/data/tokenissuance"
        msg.payload = raw_payload.encode("utf-8")
        self.on_message(self, None, msg)

    with patch.object(mqtt.Client, "connect", fake_connect), \
         patch.object(mqtt.Client, "subscribe"), \
         patch.object(mqtt.Client, "publish"), \
         patch.object(mqtt.Client, "loop_start"), \
         patch.object(mqtt.Client, "loop_stop"), \
         patch.object(mqtt.Client, "disconnect"), \
         caplog.at_level(logging.DEBUG):
        result = perform_token_refresh(
            ip="192.168.50.12",
            client_id="test_client",
            username="user_123",
            refresh_token="some_refresh_token",
            timeout=0.1,
        )

    assert result is not None
    assert result["accesstoken"] == "AUTH_REFRESH_SECRET_ACCESS"
    log_output = caplog.text
    assert "AUTH_REFRESH_SECRET_ACCESS" not in log_output
    assert "AUTH_REFRESH_SECRET_REFRESH" not in log_output
    assert "***" in log_output


