"""Unit tests for discovery and timestamp sync functions."""

import email.utils
from unittest.mock import MagicMock, mock_open, patch

from discovery import get_arp_mac, get_device_fingerprint, get_tv_timestamp


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
