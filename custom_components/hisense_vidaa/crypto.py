"""Cryptographic and certificate helpers for Hisense VIDAA integration."""

import hashlib
import logging
import os
import random
import time

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

_LOGGER = logging.getLogger(__name__)

MODERN_SALT = "h!i@s#$v%i^d&a*a"
STANDARD_SALT = "h*i&s%e!r^v0i1c9"
CLIENT_ID_PATTERN = "38D65DC30F45109A369A86FCE866A85B"
XOR_TIMESTAMP_MASK = 6239759785777146216

KNOWN_P12_PASSWORDS = [
    b"186e990688070325a1c4b0ce275d2388",
    b"",
    None,
    b"remote",
    b"hisense",
    b"123456",
]


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


def check_certs_exist(certfile: str | None, keyfile: str | None) -> bool:
    """Check if certificate and key files exist and are readable."""
    return bool(
        certfile
        and keyfile
        and os.path.isfile(certfile)
        and os.path.isfile(keyfile)
        and os.access(certfile, os.R_OK)
        and os.access(keyfile, os.R_OK)
    )


def extract_pkcs12_to_pem(
    p12_path: str,
    password: str | bytes | None = None,
    dest_dir: str | None = None,
) -> tuple[str, str] | None:
    """Extracts client certificate and private key from a PKCS#12 (.p12/.pfx) archive.

    Returns:
        tuple[certfile_path, keyfile_path] or None if extraction fails.
    """
    if not HAS_CRYPTOGRAPHY or not p12_path or not os.path.isfile(p12_path):
        return None

    try:
        with open(p12_path, "rb") as f:
            p12_data = f.read()
    except Exception as err:
        _LOGGER.debug("Failed to read PKCS#12 file %s: %s", p12_path, err)
        return None

    passwords_to_try: list[bytes | None] = []
    if password is not None:
        passwords_to_try.append(password.encode("utf-8") if isinstance(password, str) else password)
    passwords_to_try.extend(KNOWN_P12_PASSWORDS)

    private_key = None
    certificate = None

    for pwd in passwords_to_try:
        try:
            key, cert, _ = pkcs12.load_key_and_certificates(p12_data, pwd)
            if key and cert:
                private_key = key
                certificate = cert
                break
        except Exception:
            continue

    if not private_key or not certificate:
        _LOGGER.debug("Could not extract private key and certificate from PKCS#12 file %s", p12_path)
        return None

    if dest_dir is None:
        dest_dir = os.path.dirname(os.path.abspath(p12_path))
    os.makedirs(dest_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(p12_path))[0]
    out_cert_path = os.path.join(dest_dir, f"{base_name}_cert.pem")
    out_key_path = os.path.join(dest_dir, f"{base_name}_key.pem")

    try:
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(out_cert_path, "wb") as f:
            f.write(cert_pem)
        with open(out_key_path, "wb") as f:
            f.write(key_pem)

        return out_cert_path, out_key_path
    except Exception as err:
        _LOGGER.debug("Failed to write extracted PEM files: %s", err)
        return None


def resolve_ca_certificate(
    ca_path: str | None = None,
    search_dirs: list[str] | None = None,
) -> str | None:
    """Resolves CA certificate path for optional server certificate validation.

    Returns:
        ca_cert_path or None
    """
    if ca_path and os.path.isfile(ca_path):
        return os.path.abspath(ca_path)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))

    if search_dirs is None:
        search_dirs = [
            os.path.join(script_dir, "certs"),
            os.path.join(repo_root, "certs"),
            os.path.join(repo_root, "hisense_vidaa_certs"),
            os.path.expanduser("~/.config/hisense_vidaa/certs"),
            "/config/certs",
            "/config/ssl",
            "/config",
            "/ssl",
            "/opt/usb/homeassistant/certs",
            "/opt/usb/homeassistant/ssl",
            "/opt/usb/homeassistant",
        ]

    ca_names = [
        "remote_ca.pem",
        "RemoteCA.crt",
        "RemoteCA.pem",
        "ca.pem",
        "ca.crt",
        "ca_cert.pem",
        "root_ca.pem",
    ]

    for d in search_dirs:
        for name in ca_names:
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

    return None


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
            os.path.expanduser("~/.config/hisense_vidaa/certs"),
            "/config/certs",
            "/config/ssl",
            "/config",
            "/ssl",
            "/opt/usb/homeassistant/certs",
            "/opt/usb/homeassistant/ssl",
            "/opt/usb/homeassistant",
        ]

    # Handle direct PKCS#12 bundle input
    if certfile and (certfile.lower().endswith(".p12") or certfile.lower().endswith(".pfx")):
        extracted = extract_pkcs12_to_pem(certfile)
        if extracted:
            return extracted

    profile_clean = (auth_profile or "auto").lower()

    if profile_clean in ("modern", "vidaa_2024", "vidaa"):
        cert_names = [
            "vidaa_2024_cert.pem",
            "vidaa2024_cert.pem",
            "vidaa_client.pem",
            "hisense.crt",
            "client_cert.pem",
            "cert.pem",
        ]
        key_names = [
            "vidaa_2024_key.pem",
            "vidaa2024_key.pem",
            "vidaa_client.key",
            "hisense.key",
            "client_key.pem",
            "key.pem",
        ]
        p12_names = [
            "vidaa_2024_client_mobile_android.p12",
            "client_mobile_android.p12",
            "3R.p12",
            "vidaa_cert.p12",
            "vidaa.p12",
        ]
    elif profile_clean in ("remotenow", "remotenow_2018", "standard"):
        cert_names = [
            "remotenow_2018_cert.pem",
            "vidaa_client.pem",
            "hisense.crt",
            "client_cert.pem",
            "cert.pem",
        ]
        key_names = [
            "remotenow_2018_key.pem",
            "vidaa_client.key",
            "hisense.key",
            "client_key.pem",
            "key.pem",
        ]
        p12_names = [
            "rcamobile.p12",
            "hisense.p12",
            "remotenow.p12",
        ]
    else:  # auto
        cert_names = [
            "vidaa_client.pem",
            "hisense.crt",
            "client_cert.pem",
            "vidaa_2024_cert.pem",
            "vidaa2024_cert.pem",
            "remotenow_2018_cert.pem",
            "cert.pem",
        ]
        key_names = [
            "vidaa_client.key",
            "hisense.key",
            "client_key.pem",
            "vidaa_2024_key.pem",
            "vidaa2024_key.pem",
            "remotenow_2018_key.pem",
            "key.pem",
        ]
        p12_names = [
            "client_mobile_android.p12",
            "vidaa_2024_client_mobile_android.p12",
            "3R.p12",
            "vidaa_cert.p12",
            "vidaa.p12",
            "rcamobile.p12",
            "hisense.p12",
        ]

    resolved_cert = None
    resolved_key = None

    if certfile and os.path.isfile(certfile):
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

    if keyfile and os.path.isfile(keyfile):
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

    # If no separate cert/key PEM pair found, search for PKCS#12 bundles
    if not (resolved_cert and resolved_key):
        for d in search_dirs:
            for p12_name in p12_names:
                p12_candidate = os.path.join(d, p12_name)
                if os.path.isfile(p12_candidate):
                    extracted = extract_pkcs12_to_pem(p12_candidate)
                    if extracted:
                        return extracted

    default_cert = os.path.join(script_dir, "certs", "cert.pem")
    default_key = os.path.join(script_dir, "certs", "key.pem")

    return resolved_cert or default_cert, resolved_key or default_key
