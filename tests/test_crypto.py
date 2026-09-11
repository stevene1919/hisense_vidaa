"""Unit tests for crypto and certificate resolution functions."""

import hashlib
import os
from datetime import UTC, datetime, timedelta

from crypto import (
    CLIENT_ID_PATTERN,
    XOR_TIMESTAMP_MASK,
    clean_mac,
    extract_pkcs12_to_pem,
    generate_initial_credentials,
    resolve_ca_certificate,
    resolve_certificates,
)
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12


def test_clean_mac():
    """Test standardizing MAC addresses with different delimiters."""
    assert clean_mac("e8:51:77:ec:98:1c") == "E8:51:77:EC:98:1C"
    assert clean_mac("e8-51-77-ec-98-1c") == "E8:51:77:EC:98:1C"
    assert clean_mac("e85177ec981c") == "E8:51:77:EC:98:1C"

    # Random MAC generation on None or invalid
    rnd = clean_mac(None)
    assert len(rnd) == 17
    assert len(rnd.split(":")) == 6


def test_generate_initial_credentials_standard():
    """Test credential generation for standard RemoteNOW profile."""
    mac = "E8:51:77:EC:98:1C"
    ts = 1788778246

    client_id, username, password = generate_initial_credentials(
        mac=mac, timestamp=ts, auth_profile="remotenow"
    )

    # Validate Client ID format: <MAC>$his$<6-char MD5>_vidaacommon_001
    expected_md5 = hashlib.md5(f"{CLIENT_ID_PATTERN}${mac}".encode()).hexdigest().upper()
    assert client_id == f"{mac}$his${expected_md5[:6]}_vidaacommon_001"

    # Standard username uses plain timestamp
    assert username == f"his${ts}"

    # Verify password hash format
    assert len(password) == 32
    assert password.isupper()


def test_generate_initial_credentials_modern():
    """Test credential generation for Modern VIDAA 2.0 with XOR timestamp mask."""
    mac = "E8:51:77:EC:98:1C"
    ts = 1788778246

    client_id, username, password = generate_initial_credentials(
        mac=mac, timestamp=ts, auth_profile="modern"
    )

    expected_md5 = hashlib.md5(f"{CLIENT_ID_PATTERN}${mac}".encode()).hexdigest().upper()
    assert client_id == f"{mac}$his${expected_md5[:6]}_vidaacommon_001"

    # Modern username uses XOR masked timestamp
    expected_xor = ts ^ XOR_TIMESTAMP_MASK
    assert username == f"his${expected_xor}"
    assert len(password) == 32


def test_resolve_certificates(tmp_path):
    """Test resolving certificates across directory hierarchies."""
    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()

    cert_file = cert_dir / "vidaa_2024_cert.pem"
    key_file = cert_dir / "vidaa_2024_key.pem"
    cert_file.write_text("CERT DATA")
    key_file.write_text("KEY DATA")

    cert, key = resolve_certificates(auth_profile="modern", search_dirs=[str(cert_dir)])
    assert cert == str(cert_file)
    assert key == str(key_file)


def test_extract_pkcs12_and_resolve(tmp_path):
    """Test generating a PKCS#12 bundle, extracting to PEM, and auto-resolving."""
    # Generate synthetic key and cert
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    subject = issuer = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "TestCert")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    p12_bytes = pkcs12.serialize_key_and_certificates(
        b"TestCert",
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(b"186e990688070325a1c4b0ce275d2388"),
    )

    p12_file = tmp_path / "client_mobile_android.p12"
    p12_file.write_bytes(p12_bytes)

    # Test extract_pkcs12_to_pem directly
    extracted = extract_pkcs12_to_pem(str(p12_file), dest_dir=str(tmp_path))
    assert extracted is not None
    cert_path, key_path = extracted
    assert os.path.isfile(cert_path)
    assert os.path.isfile(key_path)

    # Test resolve_certificates finding the .p12 archive
    resolved_cert, resolved_key = resolve_certificates(
        auth_profile="modern", search_dirs=[str(tmp_path)]
    )
    assert os.path.isfile(resolved_cert)
    assert os.path.isfile(resolved_key)


def test_resolve_ca_certificate(tmp_path):
    """Test resolving optional CA certificate for server verification."""
    ca_dir = tmp_path / "ca_certs"
    ca_dir.mkdir()

    ca_file = ca_dir / "remote_ca.pem"
    ca_file.write_text("CA CERT DATA")

    # Found in search dirs
    found_ca = resolve_ca_certificate(search_dirs=[str(ca_dir)])
    assert found_ca == str(ca_file)

    # Explicit ca_path
    assert resolve_ca_certificate(ca_path=str(ca_file)) == str(ca_file)
    assert resolve_ca_certificate(ca_path="/nonexistent/path.pem") is None
