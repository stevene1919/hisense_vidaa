"""Unit tests for crypto and certificate resolution functions."""

import hashlib
import os
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12

from custom_components.hisense_vidaa.crypto import (
    CLIENT_ID_PATTERN,
    XOR_TIMESTAMP_MASK,
    clean_mac,
    extract_pkcs12_to_pem,
    generate_initial_credentials,
    resolve_ca_certificate,
    resolve_certificates,
)


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


def test_generate_initial_credentials_middle():
    """Test credential generation for Middle VIDAA (3000-3285) with XOR mask + Standard salt."""
    mac = "E8:51:77:EC:98:1C"
    ts = 1788778246

    client_id, username, password = generate_initial_credentials(
        mac=mac, timestamp=ts, auth_profile="middle"
    )

    expected_md5 = hashlib.md5(f"{CLIENT_ID_PATTERN}${mac}".encode()).hexdigest().upper()
    assert client_id == f"{mac}$his${expected_md5[:6]}_vidaacommon_001"

    # Middle username uses XOR masked timestamp
    expected_xor = ts ^ XOR_TIMESTAMP_MASK
    assert username == f"his${expected_xor}"
    assert len(password) == 32


def test_generate_initial_credentials_legacy():
    """Test static credential generation for legacy pre-dynamic firmware."""
    mac = "E8:51:77:EC:98:1C"
    client_id, username, password = generate_initial_credentials(
        mac=mac, auth_profile="legacy"
    )

    assert username == "hisenseservice"
    assert password == "multimqttservice"
    assert "vidaacommon_001" in client_id


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


def test_resolve_certificates_versioned(tmp_path):
    """Test resolving versioned certificates such as vidaa_client_v01.pem / key."""
    cert_dir = tmp_path / "ssl"
    cert_dir.mkdir()

    v01_cert = cert_dir / "vidaa_client_v01.pem"
    v01_key = cert_dir / "vidaa_client_v01.key"
    v01_cert.write_text("V01 CERT")
    v01_key.write_text("V01 KEY")

    cert, key = resolve_certificates(auth_profile="auto", search_dirs=[str(cert_dir)])
    assert cert == str(v01_cert)
    assert key == str(v01_key)

    # Test auto matching key alongside explicit certfile
    cert_match, key_match = resolve_certificates(certfile=str(v01_cert), search_dirs=[str(cert_dir)])
    assert cert_match == str(v01_cert)
    assert key_match == str(v01_key)


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


def test_extract_el_pkcs12_and_resolve(tmp_path):
    """Test discovering and extracting El.p12 from VIDAA APK."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    subject = issuer = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "VidaaAppAndroidV01")])
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
        b"VidaaAppAndroidV01",
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(b"186e990688070325a1c4b0ce275d2388"),
    )

    el_file = tmp_path / "El.p12"
    el_file.write_bytes(p12_bytes)

    resolved_cert, resolved_key = resolve_certificates(
        auth_profile="auto", search_dirs=[str(tmp_path)]
    )
    assert os.path.isfile(resolved_cert)
    assert os.path.isfile(resolved_key)
    assert "El_cert.pem" in resolved_cert
    assert "El_key.pem" in resolved_key


def test_resolve_certificates_direct_p12_argument(tmp_path):
    """Test passing a direct .p12 certfile path to resolve_certificates."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    subject = issuer = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "DirectP12")])
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
        b"DirectP12",
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(b"186e990688070325a1c4b0ce275d2388"),
    )

    custom_p12 = tmp_path / "custom_bundle.p12"
    custom_p12.write_bytes(p12_bytes)

    resolved_cert, resolved_key = resolve_certificates(certfile=str(custom_p12))
    assert os.path.isfile(resolved_cert)
    assert os.path.isfile(resolved_key)
    assert "custom_bundle_cert.pem" in resolved_cert
    assert "custom_bundle_key.pem" in resolved_key


def test_profile_cert_candidates_el_p12_membership():
    """Verify El.p12 and el.p12 exist in candidate lists for appropriate profiles."""
    from custom_components.hisense_vidaa.protocol.certs import PROFILE_CERT_CANDIDATES

    for profile in ("modern", "middle", "auto"):
        _, _, p12_names = PROFILE_CERT_CANDIDATES[profile]
        assert "El.p12" in p12_names
        assert "el.p12" in p12_names


def test_get_profile_default_cert_paths(tmp_path):
    """Test get_profile_default_cert_paths for different auth profiles."""
    from custom_components.hisense_vidaa.crypto import get_profile_default_cert_paths

    _cert, _key, cert_dir, cert_name, key_name = get_profile_default_cert_paths(
        "modern", config_dir=str(tmp_path)
    )
    assert cert_name == "vidaa_2024_cert.pem"
    assert key_name == "vidaa_2024_key.pem"
    assert cert_dir == str(tmp_path / "ssl")

    _cert2, _key2, _dir2, cert_name2, key_name2 = get_profile_default_cert_paths(
        "remotenow", config_dir=str(tmp_path)
    )
    assert cert_name2 == "remotenow_2018_cert.pem"
    assert key_name2 == "remotenow_2018_key.pem"



