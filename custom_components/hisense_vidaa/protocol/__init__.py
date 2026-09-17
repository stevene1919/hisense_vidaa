"""Protocol and network communication subpackage for Hisense VIDAA TV."""

from __future__ import annotations

from .auth import (
    apply_mqtt_tls,
    is_token_expired,
    perform_token_refresh,
    probe_tv_auth_methods,
    test_tv_ssl_connection,
)
from .certs import (
    check_certs_exist,
    extract_pkcs12_to_pem,
    get_profile_default_cert_paths,
    resolve_ca_certificate,
    resolve_certificates,
)
from .dispatcher import dispatch_incoming_mqtt_message
from .pairing import async_start_pairing_handshake, async_submit_pin_code
from .topics import TOPIC_BROADCAST_BASEPATH, TopicPaths, build_topic_paths
from .wol import send_wake_on_lan

__all__ = [
    "TOPIC_BROADCAST_BASEPATH",
    "TopicPaths",
    "apply_mqtt_tls",
    "async_start_pairing_handshake",
    "async_submit_pin_code",
    "build_topic_paths",
    "check_certs_exist",
    "dispatch_incoming_mqtt_message",
    "extract_pkcs12_to_pem",
    "get_profile_default_cert_paths",
    "is_token_expired",
    "perform_token_refresh",
    "probe_tv_auth_methods",
    "resolve_ca_certificate",
    "resolve_certificates",
    "send_wake_on_lan",
    "test_tv_ssl_connection",
]
