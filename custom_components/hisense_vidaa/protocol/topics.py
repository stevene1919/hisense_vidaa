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
    cid = client_id or "hisense_service"
    return TopicPaths(
        ui=f"/remoteapp/tv/ui_service/{cid}/",
        platform=f"/remoteapp/tv/platform_service/{cid}/",
        mobile=f"/remoteapp/mobile/{cid}/",
        broadcast=TOPIC_BROADCAST_BASEPATH,
        remote=f"/remoteapp/tv/remote_service/{cid}/",
    )
