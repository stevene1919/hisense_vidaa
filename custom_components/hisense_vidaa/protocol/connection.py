"""MQTT client connection, lifecycle, and topic subscription management."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt

from .auth import apply_mqtt_tls

_LOGGER = logging.getLogger(__name__)


def build_mqtt_client(
    client_id: str,
    username: str,
    password: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    use_ssl: bool = True,
    on_connect: Callable | None = None,
    on_message: Callable | None = None,
    on_disconnect: Callable | None = None,
) -> mqtt.Client:
    """Builds and configures an authenticated Paho MQTT client."""
    client = mqtt.Client(
        client_id=client_id,
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
    )
    client.reconnect_delay_set(min_delay=2, max_delay=30)

    apply_mqtt_tls(
        client=client,
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        verify_ssl=verify_ssl,
        use_ssl=use_ssl,
    )
    client.username_pw_set(username=username, password=password)

    if on_connect:
        client.on_connect = on_connect
    if on_message:
        client.on_message = on_message
    if on_disconnect:
        client.on_disconnect = on_disconnect

    return client


def subscribe_standard_tv_topics(
    client: mqtt.Client,
    broadcast_basepath: str,
    mobile_basepath: str,
) -> None:
    """Subscribes to standard VIDAA broadcast and mobile unicast telemetry topics."""
    client.subscribe([
        (broadcast_basepath + "ui_service/state", 0),
        (broadcast_basepath + "platform_service/actions/volumechange", 0),
        (broadcast_basepath + "ui_service/volume", 0),
        (broadcast_basepath + "platform_service/actions/tvsleep", 0),
        (broadcast_basepath + "ui_service/data/hotelmodechange", 0),
        (mobile_basepath + "ui_service/data/sourcelist", 0),
        (mobile_basepath + "ui_service/data/applist", 0),
        (mobile_basepath + "ui_service/data/gettvstate", 0),
        (mobile_basepath + "ui_service/data/state", 0),
        (mobile_basepath + "platform_service/data/getvolume", 0),
        (mobile_basepath + "platform_service/data/gettvinfo", 0),
        (mobile_basepath + "platform_service/data/getdeviceinfo", 0),
        (mobile_basepath + "ui_service/data/capability", 0),
        (mobile_basepath + "platform_service/data/picturesetting", 0),
        (broadcast_basepath + "platform_service/data/picturesetting", 0),
        (mobile_basepath + "platform_service/data/soundsetting", 0),
        (broadcast_basepath + "platform_service/data/soundsetting", 0),
    ])


def clean_disconnect_mqtt_client(client: mqtt.Client | None) -> None:
    """Safely unbinds callbacks, stops background loop, and disconnects client."""
    if not client:
        return
    try:
        client.on_connect = None
        client.on_disconnect = None
        client.on_message = None
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        _LOGGER.debug("Error during MQTT client disconnect: %s", e)
    with contextlib.suppress(Exception):
        client.loop_stop()
