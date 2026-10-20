"""MQTT topic path definitions and builders for Hisense VIDAA TV."""

from __future__ import annotations

from dataclasses import dataclass

TOPIC_BROADCAST_BASEPATH = "/remoteapp/mobile/broadcast/"


@dataclass
class TopicPaths:
    """Holds the active MQTT topic basepaths for a given client ID."""

    ui: str
    platform: str
    mobile: str
    broadcast: str
    remote: str


def build_topic_paths(client_id: str) -> TopicPaths:
    """Builds standard VIDAA MQTT topic paths for a client session."""
    resolved_client_id = client_id or "hisense_service"
    return TopicPaths(
        ui=f"/remoteapp/tv/ui_service/{resolved_client_id}/",
        platform=f"/remoteapp/tv/platform_service/{resolved_client_id}/",
        mobile=f"/remoteapp/mobile/{resolved_client_id}/",
        broadcast=TOPIC_BROADCAST_BASEPATH,
        remote=f"/remoteapp/tv/remote_service/{resolved_client_id}/",
    )
