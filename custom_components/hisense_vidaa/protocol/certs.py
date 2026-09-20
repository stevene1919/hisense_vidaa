"""Certificate resolution and PKCS#12 bundle extraction for Hisense VIDAA TV."""

from __future__ import annotations

import logging
import os

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

_LOGGER = logging.getLogger(__name__)

KNOWN_P12_PASSWORDS = [
    b"186e990688070325a1c4b0ce275d2388",
    b"",
    None,
    b"remote",
    b"hisense",
    b"123456",
]

__all__ = [
    "HAS_CRYPTOGRAPHY",
    "KNOWN_P12_PASSWORDS",
    "check_certs_exist",
    "extract_pkcs12_to_pem",
    "get_profile_default_cert_paths",
    "resolve_ca_certificate",
    "resolve_certificates",
]


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

    if search_dirs is None:
        component_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_dirs = [
            "/config/ssl",
            "/ssl",
            "/config/certs",
            "/config",
            os.path.join(component_dir, "ssl"),
            os.path.join(component_dir, "certs"),
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


PROFILE_CERT_CANDIDATES: dict[str, tuple[list[str], list[str], list[str]]] = {
    "modern": (
        ["vidaa_client_v01.pem", "vidaa_client_v01.crt", "vidaa_client_v02.pem", "vidaa_2024_cert.pem", "vidaa2024_cert.pem", "vidaa_client.pem", "hisense.crt", "client_cert.pem", "cert.pem"],
        ["vidaa_client_v01.key", "vidaa_client_v02.key", "vidaa_2024_key.pem", "vidaa2024_key.pem", "vidaa_client.key", "hisense.key", "client_key.pem", "key.pem"],
        ["vidaa_2024_client_mobile_android.p12", "client_mobile_android.p12", "El.p12", "el.p12", "3R.p12", "vidaa_cert.p12", "vidaa.p12"],
    ),
    "middle": (
        ["vidaa_client_v01.pem", "vidaa_client_v01.crt", "vidaa_client_v02.pem", "vidaa_client.pem", "remotenow_2018_cert.pem", "hisense.crt", "client_cert.pem", "cert.pem"],
        ["vidaa_client_v01.key", "vidaa_client_v02.key", "vidaa_client.key", "remotenow_2018_key.pem", "hisense.key", "client_key.pem", "key.pem"],
        ["client_mobile_android.p12", "vidaa_2024_client_mobile_android.p12", "El.p12", "el.p12", "3R.p12", "rcamobile.p12", "hisense.p12"],
    ),
    "remotenow": (
        ["remotenow_2018_cert.pem", "vidaa_client_v01.pem", "vidaa_client_v01.crt", "vidaa_client.pem", "hisense.crt", "client_cert.pem", "cert.pem"],
        ["remotenow_2018_key.pem", "vidaa_client_v01.key", "vidaa_client.key", "hisense.key", "client_key.pem", "key.pem"],
        ["rcamobile.p12", "hisense.p12", "remotenow.p12"],
    ),
    "auto": (
        ["vidaa_client_v01.pem", "vidaa_client_v01.crt", "vidaa_client_v02.pem", "vidaa_client.pem", "hisense.crt", "client_cert.pem", "vidaa_2024_cert.pem", "vidaa2024_cert.pem", "remotenow_2018_cert.pem", "cert.pem"],
        ["vidaa_client_v01.key", "vidaa_client_v02.key", "vidaa_client.key", "hisense.key", "client_key.pem", "vidaa_2024_key.pem", "vidaa2024_key.pem", "remotenow_2018_key.pem", "key.pem"],
        ["client_mobile_android.p12", "vidaa_2024_client_mobile_android.p12", "El.p12", "el.p12", "3R.p12", "vidaa_cert.p12", "vidaa.p12", "rcamobile.p12", "hisense.p12"],
    ),
}


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
    if search_dirs is None:
        component_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_dirs = [
            "/config/ssl",
            "/ssl",
            "/config/certs",
            "/config",
            os.path.join(component_dir, "ssl"),
            os.path.join(component_dir, "certs"),
        ]

    # Handle direct PKCS#12 bundle input
    if certfile and (certfile.lower().endswith(".p12") or certfile.lower().endswith(".pfx")):
        extracted = extract_pkcs12_to_pem(certfile)
        if extracted:
            return extracted

    profile_clean = (auth_profile or "auto").lower()
    if profile_clean in ("modern", "vidaa_2024", "vidaa"):
        profile_key = "modern"
    elif profile_clean in ("middle", "vidaa_15", "vidaa_middle"):
        profile_key = "middle"
    elif profile_clean in ("remotenow", "remotenow_2018", "standard"):
        profile_key = "remotenow"
    else:
        profile_key = "auto"

    cert_names, key_names, p12_names = PROFILE_CERT_CANDIDATES[profile_key]

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
    elif resolved_cert:
        cert_stem = os.path.splitext(resolved_cert)[0]
        for ext in (".key", "_key.pem", ".pem"):
            candidate = cert_stem + ext
            if candidate != resolved_cert and os.path.isfile(candidate):
                resolved_key = candidate
                break

    if not resolved_key:
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

    default_cert = "/config/ssl/hisense.crt"
    default_key = "/config/ssl/hisense.key"

    return resolved_cert or default_cert, resolved_key or default_key


def get_profile_default_cert_paths(
    auth_profile: str,
    config_dir: str = "/config",
) -> tuple[str, str, str, str, str]:
    """Returns (default_cert_path, default_key_path, default_cert_dir, default_cert_name, default_key_name)."""
    default_cert_dir = os.path.join(config_dir, "ssl")

    profile_clean = (auth_profile or "auto").lower()
    if profile_clean in ("modern", "vidaa_2024", "vidaa"):
        default_cert_name = "vidaa_2024_cert.pem"
        default_key_name = "vidaa_2024_key.pem"
    elif profile_clean in ("middle", "vidaa_15", "vidaa_middle"):
        default_cert_name = "vidaa_client_v01.pem"
        default_key_name = "vidaa_client_v01.key"
    elif profile_clean in ("remotenow", "remotenow_2018", "standard"):
        default_cert_name = "remotenow_2018_cert.pem"
        default_key_name = "remotenow_2018_key.pem"
    else:
        default_cert_name = "hisense.crt"
        default_key_name = "hisense.key"

    resolved_cert, resolved_key = resolve_certificates(auth_profile)
    if check_certs_exist(resolved_cert, resolved_key):
        default_cert_path = resolved_cert
        default_key_path = resolved_key
    else:
        default_cert_path = os.path.join(default_cert_dir, default_cert_name)
        default_key_path = os.path.join(default_cert_dir, default_key_name)

    return default_cert_path, default_key_path, default_cert_dir, default_cert_name, default_key_name
