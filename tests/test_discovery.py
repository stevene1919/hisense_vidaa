"""Unit tests for discovery and timestamp sync functions."""

import email.utils
from unittest.mock import MagicMock, mock_open, patch

from custom_components.hisense_vidaa.discovery import (
    get_arp_mac,
    get_device_fingerprint,
    get_tv_timestamp,
    query_mdns_fingerprint,
)


def test_get_tv_timestamp():
    """Test extracting timestamp from UPnP HTTP Date header."""
    mock_response = MagicMock()
    mock_response.headers = {"Date": "Mon, 07 Sep 2026 10:24:06 GMT"}
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        ts = get_tv_timestamp("192.168.50.12")
        expected_dt = email.utils.parsedate_to_datetime("Mon, 07 Sep 2026 10:24:06 GMT")
        assert ts == int(expected_dt.timestamp())


def test_get_tv_timestamp_network_failure():
    """Test fallback to None when TV HTTP port is unreachable."""
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        ts = get_tv_timestamp("192.168.50.12")
        assert ts is None


def test_get_arp_mac(monkeypatch):
    """Test discovering MAC address via ARP table simulation."""
    mock_arp = (
        "IP address       HW type     Flags       HW address            Mask     Device\n"
        "192.168.50.12    0x1         0x2         e8:51:77:ec:98:1c     *        eth0\n"
    )

    with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open(read_data=mock_arp)):
        mac = get_arp_mac("192.168.50.12")
        assert mac == "e8:51:77:ec:98:1c"


def test_get_device_fingerprint():
    """Test parsing UPnP renderer descriptor XML."""
    sample_xml = """<?xml version="1.0" encoding="utf-8"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
      <device>
        <friendlyName>Living Room TV</friendlyName>
        <modelName>65U8N</modelName>
        <modelNumber>2.0</modelNumber>
        <manufacturer>Hisense</manufacturer>
        <modelDescription>brand=Hisense\nplatform=1\nmacWifi=E85177EC981C\nmacEthernet=E43BC957F14F</modelDescription>
      </device>
    </root>"""

    mock_response = MagicMock()
    mock_response.headers = {"Date": "Fri, 11 Sep 2026 12:00:00 GMT"}
    mock_response.read.return_value = sample_xml.encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        fp = get_device_fingerprint("192.168.50.12")
        assert fp["friendly_name"] == "Living Room TV"
        assert fp["model_name"] == "65U8N"
        assert fp["model_number"] == "2.0"
        assert fp["manufacturer"] == "Hisense"
        assert fp["mac_wifi"] == "E85177EC981C"
        assert fp["mac_ethernet"] == "E43BC957F14F"
        assert fp["platform"] == "1"


def test_get_device_fingerprint_malformed_xml():
    """Test graceful handling of invalid/malformed XML from network."""
    mock_response = MagicMock()
    mock_response.headers = {}
    mock_response.read.return_value = b"<invalid><xml"
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        fp = get_device_fingerprint("192.168.50.12")
        assert fp["friendly_name"] is None
        assert fp["model_name"] is None


def test_query_mdns_fingerprint_no_zeroconf():
    """Test that query_mdns_fingerprint gracefully skips and does not instantiate Zeroconf when zc=None."""
    # When zc is None, the function must not instantiate any Zeroconf object
    # (avoiding the HA deprecation warning) and return an empty fingerprint cleanly.
    info = query_mdns_fingerprint("192.168.50.12", timeout=0.1, zc=None)
    assert info["model_code"] is None
    assert info["firmware_version"] is None
    assert info["serial_number"] is None
    assert info["manufacturer"] is None


def test_normalize_manufacturer_brand():
    """Test manufacturer brand normalization for generic placeholders and brand codes."""
    from custom_components.hisense_vidaa.tv.upnp_desc import normalize_manufacturer_brand

    # Generic placeholders with known brand codes
    assert normalize_manufacturer_brand("his", "SmartTV") == "Hisense"
    assert normalize_manufacturer_brand("hisense", "Smart TV") == "Hisense"
    assert normalize_manufacturer_brand("tos", "smarttv.") == "Toshiba"
    assert normalize_manufacturer_brand("loe", "http://www.smarttv.com") == "Loewe"
    assert normalize_manufacturer_brand("sch", "") == "Schneider"
    assert normalize_manufacturer_brand("bek", None) == "Beko"

    # Generic placeholders with no brand code -> default to Hisense
    assert normalize_manufacturer_brand(None, "SmartTV") == "Hisense"
    assert normalize_manufacturer_brand("", "smart tv") == "Hisense"

    # Non-generic actual manufacturer names preserved
    assert normalize_manufacturer_brand("his", "Toshiba") == "Toshiba"
    assert normalize_manufacturer_brand("loe", "Loewe") == "Loewe"


def test_parse_ssdp_discovery_generic_manufacturer_sanitization():
    """Test parse_ssdp_discovery sanitizes generic SmartTV manufacturer placeholders."""
    from custom_components.hisense_vidaa.discovery import parse_ssdp_discovery

    sample_info = MagicMock()
    sample_info.ssdp_headers = {"_host": "192.168.50.12"}
    sample_info.ssdp_location = "http://192.168.50.12:38400/description.xml"
    sample_info.ssdp_udn = "uuid:12345"
    sample_info.upnp = {
        "friendlyName": "Living Room TV",
        "modelName": "58A53FXVT",
        "manufacturer": "SmartTV",
        "modelDescription": "vidaa_support=1\nbrand=his\nmacWifi=E8:51:77:EC:98:1C\n",
    }

    discovered = parse_ssdp_discovery(sample_info)
    assert discovered is not None
    assert discovered.manufacturer == "Hisense"
    assert discovered.model == "58A53FXVT"
    assert discovered.mac_address == "e8:51:77:ec:98:1c"
