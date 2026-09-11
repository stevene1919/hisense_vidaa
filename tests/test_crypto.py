"""Unit tests for crypto and certificate resolution functions."""

import hashlib

from crypto import (
    CLIENT_ID_PATTERN,
    XOR_TIMESTAMP_MASK,
    clean_mac,
    generate_initial_credentials,
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
