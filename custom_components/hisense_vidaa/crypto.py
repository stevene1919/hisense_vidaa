"""Cryptographic and pairing credential helpers for Hisense VIDAA TV."""

from __future__ import annotations

import hashlib
import logging
import random
import time

_LOGGER = logging.getLogger(__name__)

MODERN_SALT = "h!i@s#$v%i^d&a*a"
STANDARD_SALT = "h*i&s%e!r^v0i1c9"
CLIENT_ID_PATTERN = "38D65DC30F45109A369A86FCE866A85B"
XOR_TIMESTAMP_MASK = 6239759785777146216


def clean_mac(mac: str | None) -> str:
    """Normalize a MAC address's separators (caller's case preserved), or generate a random MAC.

    The MAC case must be preserved: it feeds the case-sensitive ``race`` hash and the
    ``<mac>$his$…`` client_id (see the reference implementations, which note the race
    hash is case-sensitive). Only a synthetic random MAC is uppercased.
    """
    if mac:
        stripped = mac.replace(":", "").replace("-", "").replace(".", "").strip()
        if len(stripped) == 12:
            return ":".join(stripped[i:i + 2] for i in range(0, 12, 2))
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6)).upper()


def generate_initial_credentials(
    mac: str | None = None,
    timestamp: int | None = None,
    auth_profile: str = "auto",
    use_new_auth: bool | None = None,
) -> tuple[str, str, str]:
    """Derive MQTT authentication parameters (client_id, username, password) for VIDAA pairing.

    Returns:
        tuple[client_id, username, password]
    """
    ts = int(time.time()) if timestamp is None else timestamp
    normalized_mac = clean_mac(mac)

    mac_digest = hashlib.md5(f"{CLIENT_ID_PATTERN}${normalized_mac}".encode()).hexdigest().upper()
    client_id = f"{normalized_mac}$his${mac_digest[:6]}_vidaacommon_001"

    profile = (auth_profile or "auto").lower()
    if profile in ("legacy", "static"):
        return client_id, "hisenseservice", "multimqttservice"

    is_modern = (
        use_new_auth is True
        or (use_new_auth is None and profile in ("auto", "modern", "vidaa_2024", "vidaa"))
    )
    is_middle = profile in ("middle", "vidaa_15", "vidaa_middle")

    if is_modern:
        salt = MODERN_SALT
        username = f"his${ts ^ XOR_TIMESTAMP_MASK}"
    elif is_middle:
        salt = STANDARD_SALT
        username = f"his${ts ^ XOR_TIMESTAMP_MASK}"
    else:
        # Standard / RemoteNow dynamic
        salt = STANDARD_SALT
        username = f"his${ts}"

    digit_sum = sum(int(ch) for ch in str(ts) if ch.isdigit()) % 10
    salt_hash = hashlib.md5(f"his{digit_sum}{salt}".encode()).hexdigest().upper()
    password = hashlib.md5(f"{ts}${salt_hash[:6]}".encode()).hexdigest().upper()

    return client_id, username, password


from .protocol.certs import (
    HAS_CRYPTOGRAPHY,
    KNOWN_P12_PASSWORDS,
    check_certs_exist,
    extract_pkcs12_to_pem,
    get_profile_default_cert_paths,
    resolve_ca_certificate,
    resolve_certificates,
)

__all__ = [
    "CLIENT_ID_PATTERN",
    "HAS_CRYPTOGRAPHY",
    "KNOWN_P12_PASSWORDS",
    "MODERN_SALT",
    "STANDARD_SALT",
    "XOR_TIMESTAMP_MASK",
    "check_certs_exist",
    "clean_mac",
    "extract_pkcs12_to_pem",
    "generate_initial_credentials",
    "get_profile_default_cert_paths",
    "resolve_ca_certificate",
    "resolve_certificates",
]
