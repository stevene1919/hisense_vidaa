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
    """Cleans and standardizes a MAC address string, or generates a random MAC."""
    if mac:
        stripped = mac.replace(":", "").replace("-", "").replace(".", "").strip()
        if len(stripped) == 12:
            return ":".join(stripped[i:i + 2] for i in range(0, 12, 2)).upper()
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6)).upper()


def generate_initial_credentials(
    mac: str | None = None,
    timestamp: int | None = None,
    auth_profile: str = "auto",
    use_new_auth: bool | None = None,
) -> tuple[str, str, str]:
    """Generates the client_id, username, and password for VIDAA initial pairing handshake.

    Returns:
        tuple[client_id, username, password]
    """
    if timestamp is None:
        timestamp = int(time.time())

    cleaned_mac = clean_mac(mac)
    second_hash = hashlib.md5(f"{CLIENT_ID_PATTERN}${cleaned_mac}".encode()).hexdigest().upper()
    suffix = "001"
    client_id = f"{cleaned_mac}$his${second_hash[:6]}_vidaacommon_{suffix}"

    profile_clean = (auth_profile or "auto").lower()

    # Pre-dynamic legacy static authentication
    if profile_clean in ("legacy", "static"):
        return client_id, "hisenseservice", "multimqttservice"

    last_digit_of_cross_sum = sum(int(digit) for digit in str(timestamp)) % 10

    if use_new_auth is True:
        salt = MODERN_SALT
        username = f"his${timestamp ^ XOR_TIMESTAMP_MASK}"
    elif use_new_auth is False:
        salt = STANDARD_SALT
        username = f"his${timestamp}"
    elif profile_clean in ("modern", "vidaa_2024", "vidaa"):
        salt = MODERN_SALT
        username = f"his${timestamp ^ XOR_TIMESTAMP_MASK}"
    elif profile_clean in ("middle", "vidaa_15", "vidaa_middle"):
        salt = STANDARD_SALT
        username = f"his${timestamp ^ XOR_TIMESTAMP_MASK}"
    elif profile_clean in ("remotenow", "remotenow_2018", "standard"):
        salt = STANDARD_SALT
        username = f"his${timestamp}"
    else:  # auto
        salt = MODERN_SALT
        username = f"his${timestamp ^ XOR_TIMESTAMP_MASK}"

    third_hash = hashlib.md5(f"his{last_digit_of_cross_sum}{salt}".encode()).hexdigest().upper()
    fourth_hash = hashlib.md5(f"{timestamp}${third_hash[:6]}".encode()).hexdigest().upper()

    return client_id, username, fourth_hash


try:
    from .protocol.certs import (
        HAS_CRYPTOGRAPHY,
        KNOWN_P12_PASSWORDS,
        check_certs_exist,
        extract_pkcs12_to_pem,
        resolve_ca_certificate,
        resolve_certificates,
    )
except (ImportError, ValueError):
    from protocol.certs import (
        HAS_CRYPTOGRAPHY,
        KNOWN_P12_PASSWORDS,
        check_certs_exist,
        extract_pkcs12_to_pem,
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
    "resolve_ca_certificate",
    "resolve_certificates",
]
