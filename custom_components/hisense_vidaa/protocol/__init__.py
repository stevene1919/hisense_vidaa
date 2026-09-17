"""Protocol and network communication subpackage for Hisense VIDAA TV."""

from __future__ import annotations

from .auth import apply_mqtt_tls, is_token_expired, perform_token_refresh
from .topics import TOPIC_BROADCAST_BASEPATH, TopicPaths, build_topic_paths
from .wol import send_wake_on_lan

__all__ = [
    "TOPIC_BROADCAST_BASEPATH",
    "TopicPaths",
    "apply_mqtt_tls",
    "build_topic_paths",
    "is_token_expired",
    "perform_token_refresh",
    "send_wake_on_lan",
]
