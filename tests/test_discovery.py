"""Unit tests for discovery and timestamp sync functions."""

import email.utils
from unittest.mock import MagicMock, mock_open, patch

from custom_components.hisense_vidaa.tv.fingerprint import (
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


def test_parse_ssdp_discovery_generic_manufacturer():
    """Test parse_ssdp_discovery sanitizes generic SmartTV manufacturer placeholders using brand codes."""
    from custom_components.hisense_vidaa.protocol.discovery import parse_ssdp_discovery

    discovery_info = MagicMock()
    discovery_info.upnp = {
        "friendlyName": "Toshiba TV",
        "modelName": "58A53FXVT",
        "manufacturer": "SmartTV",
        "modelDescription": "transport_protocol=3290\nbrand=tos\nmacWifi=e85177ec981c",
    }
    discovery_info.ssdp_headers = {"_host": "192.168.50.20"}

    info = parse_ssdp_discovery(discovery_info)
    assert info is not None
    assert info.host == "192.168.50.20"
    assert info.manufacturer == "Toshiba"
    assert info.brand == "tos"
    assert info.model == "58A53FXVT"
    assert info.mac_address == "e8:51:77:ec:98:1c"


def test_normalize_brand_code():
    """Test brand code normalization for all supported OEM brands and edge cases."""
    from custom_components.hisense_vidaa.protocol.discovery import normalize_brand_code

    assert normalize_brand_code("his") == "his"
    assert normalize_brand_code("hisense") == "his"
    assert normalize_brand_code("Hisense") == "his"
    assert normalize_brand_code("tos") == "tos"
    assert normalize_brand_code("Toshiba") == "tos"
    assert normalize_brand_code("loe") == "loe"
    assert normalize_brand_code("Loewe") == "loe"
    assert normalize_brand_code("sch") == "sch"
    assert normalize_brand_code("Schneider") == "sch"
    assert normalize_brand_code("aka") == "aka"
    assert normalize_brand_code("Akai") == "aka"
    assert normalize_brand_code("bek") == "bek"
    assert normalize_brand_code("Beko") == "bek"
    assert normalize_brand_code("tel") == "tel"
    assert normalize_brand_code("Telefunken") == "tel"
    assert normalize_brand_code("bus") == "bus"
    assert normalize_brand_code("Bush") == "bus"
    assert normalize_brand_code("vic") == "vic"
    assert normalize_brand_code("Vizio") == "vic"
    assert normalize_brand_code("tpv") == "tpv"
    assert normalize_brand_code("TPV") == "tpv"
    assert normalize_brand_code("Philips") == "tpv"
    assert normalize_brand_code("aoc") == "tpv"
    assert normalize_brand_code(None) == "his"
    assert normalize_brand_code("") == "his"
    assert normalize_brand_code("unrecognized_brand") == "his"


def test_parse_ssdp_discovery_oem_brands():
    """Test parse_ssdp_discovery correctly extracts and infers OEM brands like Loewe and Beko."""
    from custom_components.hisense_vidaa.protocol.discovery import parse_ssdp_discovery

    # Loewe TV with explicit brand=loe in modelDescription
    loewe_discovery = MagicMock()
    loewe_discovery.upnp = {
        "friendlyName": "Loewe bild i",
        "modelName": "bild i.55 dr+",
        "manufacturer": "Loewe",
        "modelDescription": "vidaa_support=1\nbrand=loe\nmacWifi=001122334455",
    }
    loewe_discovery.ssdp_headers = {"_host": "192.168.50.30"}

    info_loewe = parse_ssdp_discovery(loewe_discovery)
    assert info_loewe is not None
    assert info_loewe.brand == "loe"
    assert info_loewe.manufacturer == "Loewe"
    assert info_loewe.title == "Loewe bild i"

    # Beko TV with manufacturer inference and generic Renderer friendly name
    beko_discovery = MagicMock()
    beko_discovery.upnp = {
        "friendlyName": "Renderer",
        "modelName": "Beko Android/VIDAA",
        "manufacturer": "Beko",
        "modelDescription": "transport_protocol=3290\nmacEthernet=aabbccddeeff",
    }
    beko_discovery.ssdp_headers = {"_host": "192.168.50.40"}

    info_beko = parse_ssdp_discovery(beko_discovery)
    assert info_beko is not None
    assert info_beko.brand == "bek"
    assert info_beko.manufacturer == "Beko"
    assert info_beko.title == "Beko TV (192.168.50.40)"


def test_parse_zeroconf_discovery_with_homekit_properties():
    """Test parse_zeroconf_discovery enriches metadata from HomeKit/AirPlay mDNS properties."""
    from custom_components.hisense_vidaa.protocol.discovery import parse_zeroconf_discovery

    zc_info = MagicMock()
    zc_info.host = "192.168.50.55"
    zc_info.name = "Bedroom Toshiba TV._hap._tcp.local."
    zc_info.properties = {
        b"md": b"55C350",
        b"company": b"Toshiba",
    }

    with patch("custom_components.hisense_vidaa.protocol.discovery.get_arp_mac", return_value="11:22:33:44:55:66"):
        info = parse_zeroconf_discovery(zc_info)

    assert info is not None
    assert info.host == "192.168.50.55"
    assert info.title == "Bedroom Toshiba TV"
    assert info.model == "55C350"
    assert info.manufacturer == "Toshiba"
    assert info.brand == "tos"
    assert info.mac_address == "11:22:33:44:55:66"


def test_parse_zeroconf_discovery_fallback_when_properties_absent():
    """Test parse_zeroconf_discovery gracefully falls back when HomeKit is disabled or properties are empty."""
    from custom_components.hisense_vidaa.protocol.discovery import parse_zeroconf_discovery

    zc_info = MagicMock()
    zc_info.host = "192.168.50.60"
    zc_info.name = "Smart TV._airplay._tcp.local."
    zc_info.properties = {}

    with patch("custom_components.hisense_vidaa.protocol.discovery.get_arp_mac", return_value="aa:bb:cc:dd:ee:ff"):
        info = parse_zeroconf_discovery(zc_info)

    assert info is not None
    assert info.host == "192.168.50.60"
    assert info.title == "Hisense TV (192.168.50.60)"
    assert info.model == "VIDAA TV"
    assert info.manufacturer == "Hisense"
    assert info.brand == "his"
    assert info.mac_address == "aa:bb:cc:dd:ee:ff"


def test_parse_ssdp_discovery_toptro_projector():
    """Test parse_ssdp_discovery detects TOPTRO brand from modelDescription."""
    from custom_components.hisense_vidaa.const import BRAND_CODE_MAP, BRAND_MAP
    from custom_components.hisense_vidaa.protocol.discovery import normalize_brand_code, parse_ssdp_discovery

    assert normalize_brand_code("toptro") == "tpo"
    assert normalize_brand_code("TPO") == "tpo"
    assert BRAND_MAP["tpo"] == "TOPTRO"
    assert BRAND_CODE_MAP["tpo"] == "tpo"

    ssdp_info = MagicMock()
    ssdp_info.ssdp_headers = {"_host": "192.168.50.88"}
    ssdp_info.ssdp_udn = "uuid:toptro-projector-12345"
    ssdp_info.upnp = {
        "friendlyName": "TOPTRO Smart Projector",
        "manufacturer": "smarttv.com",
        "modelName": "X7",
        "modelDescription": (
            "vidaa_support=1\n"
            "transport_protocol=3290\n"
            "brand=tpo\n"
            "macwifi=00:11:22:33:44:55\n"
            "model=X7\n"
        ),
    }

    info = parse_ssdp_discovery(ssdp_info)
    assert info is not None
    assert info.host == "192.168.50.88"
    assert info.title == "TOPTRO Smart Projector"
    assert info.model == "X7"
    assert info.manufacturer == "TOPTRO"
    assert info.brand == "tpo"
    assert info.mac_address == "00:11:22:33:44:55"


