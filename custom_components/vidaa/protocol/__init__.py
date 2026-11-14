"""Protocol and network communication subpackage for Hisense VIDAA TV."""

from __future__ import annotations

from .auth import (
    apply_mqtt_tls,
    async_perform_token_refresh,
    async_probe_tv_auth_methods,
    async_test_tv_ssl_connection,
    build_mqtt_ssl_context,
    extract_connect_rc,
    is_token_expired,
    perform_token_refresh,
    probe_tv_auth_methods,
    test_tv_ssl_connection,
)
from .certs import (
    check_certs_exist,
    detect_brand_from_cert_paths,
    extract_pkcs12_to_pem,
    get_profile_default_cert_paths,
    resolve_ca_certificate,
    resolve_certificates,
    validate_ssl_certs,
)
from .connection import (
    ConnectionManagerMixin,
    MqttSessionAdapter,
    standard_tv_topics,
)
from .crypto import (
    CLIENT_ID_PATTERN,
    MODERN_SALT,
    STANDARD_SALT,
    XOR_TIMESTAMP_MASK,
    clean_mac,
    generate_initial_credentials,
    normalize_mac_address,
)
from .discovery import (
    DiscoveredTvInfo,
    normalize_brand_code,
    parse_ssdp_discovery,
    parse_zeroconf_discovery,
)
from .dispatcher import (
    SENSITIVE_KEYS,
    dispatch_incoming_mqtt_message,
    mask_sensitive_data,
    mask_sensitive_payload,
)
from .pairing import async_start_pairing_handshake, async_submit_pin_code
from .ping import async_ping_tv, ping_tv
from .topics import TOPIC_BROADCAST_BASEPATH, TopicPaths, build_topic_paths
from .upnp import HisenseUpnpClient
from .wol import send_wake_on_lan

__all__ = [
    "CLIENT_ID_PATTERN",
    "MODERN_SALT",
    "SENSITIVE_KEYS",
    "STANDARD_SALT",
    "TOPIC_BROADCAST_BASEPATH",
    "XOR_TIMESTAMP_MASK",
    "ConnectionManagerMixin",
    "DiscoveredTvInfo",
    "HisenseUpnpClient",
    "MqttSessionAdapter",
    "TopicPaths",
    "apply_mqtt_tls",
    "async_perform_token_refresh",
    "async_ping_tv",
    "async_probe_tv_auth_methods",
    "async_start_pairing_handshake",
    "async_submit_pin_code",
    "async_test_tv_ssl_connection",
    "build_mqtt_ssl_context",
    "build_topic_paths",
    "check_certs_exist",
    "clean_mac",
    "detect_brand_from_cert_paths",
    "dispatch_incoming_mqtt_message",
    "extract_connect_rc",
    "extract_pkcs12_to_pem",
    "generate_initial_credentials",
    "get_profile_default_cert_paths",
    "is_token_expired",
    "mask_sensitive_data",
    "mask_sensitive_payload",
    "normalize_brand_code",
    "normalize_mac_address",
    "parse_ssdp_discovery",
    "parse_zeroconf_discovery",
    "perform_token_refresh",
    "ping_tv",
    "probe_tv_auth_methods",
    "resolve_ca_certificate",
    "resolve_certificates",
    "send_wake_on_lan",
    "standard_tv_topics",
    "test_tv_ssl_connection",
    "validate_ssl_certs",
]
