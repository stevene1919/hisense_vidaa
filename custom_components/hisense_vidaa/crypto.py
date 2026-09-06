"""Cryptographic and certificate helpers for Hisense VIDAA integration."""

import hashlib
import os
import random
import time

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
    last_digit_of_cross_sum = sum(int(digit) for digit in str(timestamp)) % 10

    if use_new_auth is None:
        use_new_auth = (auth_profile or "auto").lower() in ("modern", "vidaa_2024", "vidaa")

    if use_new_auth:
        salt = MODERN_SALT
        username = f"his${timestamp ^ XOR_TIMESTAMP_MASK}"
    else:
        salt = STANDARD_SALT
        username = f"his${timestamp}"

    third_hash = hashlib.md5(f"his{last_digit_of_cross_sum}{salt}".encode()).hexdigest().upper()
    fourth_hash = hashlib.md5(f"{timestamp}${third_hash[:6]}".encode()).hexdigest().upper()

    suffix = "001"
    client_id = f"{cleaned_mac}$his${second_hash[:6]}_vidaacommon_{suffix}"

    return client_id, username, fourth_hash


def resolve_certificates(
    auth_profile: str = "auto",
    certfile: str | None = None,
    keyfile: str | None = None,
    search_dirs: list[str] | None = None,
) -> tuple[str, str]:
    """Resolves certificate and private key paths based on profile and candidate locations.

    Returns:
        tuple[certfile_path, keyfile_path]
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))

    if search_dirs is None:
        search_dirs = [
            os.path.join(script_dir, "certs"),
            os.path.join(repo_root, "certs"),
            os.path.join(repo_root, "hisense_vidaa_certs"),
            "/config/certs",
            "/config/ssl",
            "/opt/usb/homeassistant/certs",
            "/opt/usb/homeassistant/ssl",
        ]

    profile_clean = (auth_profile or "auto").lower()

    if profile_clean in ("modern", "vidaa_2024", "vidaa"):
        cert_names = ["vidaa_2024_cert.pem", "vidaa2024_cert.pem", "cert.pem"]
        key_names = ["vidaa_2024_key.pem", "vidaa2024_key.pem", "key.pem"]
    elif profile_clean in ("remotenow", "remotenow_2018", "standard"):
        cert_names = ["remotenow_2018_cert.pem", "cert.pem"]
        key_names = ["remotenow_2018_key.pem", "key.pem"]
    else:  # auto
        cert_names = [
            "vidaa_2024_cert.pem",
            "vidaa2024_cert.pem",
            "remotenow_2018_cert.pem",
            "cert.pem",
        ]
        key_names = [
            "vidaa_2024_key.pem",
            "vidaa2024_key.pem",
            "remotenow_2018_key.pem",
            "key.pem",
        ]

    resolved_cert = None
    resolved_key = None

    if certfile:
        resolved_cert = os.path.abspath(certfile)
    else:
        for d in search_dirs:
            for name in cert_names:
                candidate = os.path.join(d, name)
                if os.path.exists(candidate):
                    resolved_cert = candidate
                    break
            if resolved_cert:
                break

    if keyfile:
        resolved_key = os.path.abspath(keyfile)
    else:
        for d in search_dirs:
            for name in key_names:
                candidate = os.path.join(d, name)
                if os.path.exists(candidate):
                    resolved_key = candidate
                    break
            if resolved_key:
                break

    default_cert = os.path.join(script_dir, "certs", "cert.pem")
    default_key = os.path.join(script_dir, "certs", "key.pem")

    return resolved_cert or default_cert, resolved_key or default_key
