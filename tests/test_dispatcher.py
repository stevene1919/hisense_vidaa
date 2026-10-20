"""Unit tests for the MQTT message dispatcher."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.protocol.dispatcher import dispatch_incoming_mqtt_message


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
