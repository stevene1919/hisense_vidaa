"""Comprehensive tests for multi-brand VIDAA OS support and readiness.

Verifies:
1. Candidate brand preservation across PIN entry and UPnP device discovery.
2. Automatic regeneration of credentials on HisenseTvClient when brand changes.
3. Multi-brand certificate filename hinting.
4. Normalization of 20+ OEM brands and preservation of explicit 3-letter codes.
5. UPnP descriptor MAC fallbacks ('mac' and 'network_device').
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.vidaa.client import HisenseTvClient
from custom_components.vidaa.config_flow import HisenseVidaaConfigFlow
from custom_components.vidaa.const import BRAND_OPTIONS
from custom_components.vidaa.protocol.certs import detect_brand_from_cert_paths
from custom_components.vidaa.protocol.discovery import normalize_brand_code
from custom_components.vidaa.tv.upnp_desc import parse_upnp_renderer_descriptor


def test_oem_brands_in_brand_options():
    """Verify that all major OEM brands exist in BRAND_OPTIONS selector."""
    option_values = {opt["value"] for opt in BRAND_OPTIONS}
    assert {"his", "tos", "loe", "tpv", "shp", "jvc", "sch", "bek", "ves", "bra", "met", "lei"}.issubset(
        option_values
    )


def test_brand_normalization_and_code_preservation():
    """Test normalization of OEM brands and preservation of arbitrary 3-letter codes."""
    assert normalize_brand_code("Sharp") == "shp"
    assert normalize_brand_code("JVC") == "jvc"
    assert normalize_brand_code("Vestel") == "ves"
    assert normalize_brand_code("Brandt") == "bra"
    assert normalize_brand_code("Noblex") == "nob"
    assert normalize_brand_code("Sansei") == "san"
    assert normalize_brand_code("Philco") == "phi"
    assert normalize_brand_code("RCA") == "rca"
    assert normalize_brand_code("Sinotec") == "sin"
    assert normalize_brand_code("Metz") == "met"
    assert normalize_brand_code("Leica") == "lei"

    # Arbitrary 3-letter alphanumeric code from UPnP brand=xyz is preserved
    assert normalize_brand_code("xyz") == "xyz"
    assert normalize_brand_code("ab1") == "ab1"

    # Generic or unknown long strings fall back to default 'his'
    assert normalize_brand_code("unrecognized_brand") == "his"
    assert normalize_brand_code("smarttv") == "his"
    assert normalize_brand_code("") == "his"
    assert normalize_brand_code(None) == "his"


def test_detect_brand_from_cert_paths():
    """Test detecting OEM brand from custom certificate filenames."""
    assert detect_brand_from_cert_paths("/config/ssl/sharp_vidaa.pem", None) == "shp"
    assert detect_brand_from_cert_paths(None, "/config/ssl/jvc_tv.key") == "jvc"
    assert detect_brand_from_cert_paths("/config/ssl/rcamobile.p12", None) == "rca"
    assert detect_brand_from_cert_paths("/config/ssl/toshiba_regza.crt", None) == "tos"
    assert detect_brand_from_cert_paths("/config/ssl/loewe_stellar.pem", None) == "loe"
    assert detect_brand_from_cert_paths("/config/ssl/tpv_philips.crt", None) == "tpv"
    assert detect_brand_from_cert_paths("/config/ssl/generic_cert.pem", None) is None


def test_upnp_mac_fallbacks():
    """Test UPnP renderer descriptor extracts MAC when using 'mac' or 'network_device'."""
    xml_with_mac = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
      <device>
        <friendlyName>Sharp Aquos VIDAA</friendlyName>
        <modelName>4T-C50EJ2X</modelName>
        <modelDescription>brand=shp
mac=11:22:33:44:55:66
transport_protocol=36669</modelDescription>
      </device>
    </root>"""
    parsed = parse_upnp_renderer_descriptor(xml_with_mac)
    assert parsed["brand"] == "shp"
    assert parsed["mac_wifi"] == "11:22:33:44:55:66"

    xml_with_network_device = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
      <device>
        <friendlyName>JVC Smart TV</friendlyName>
        <modelDescription>brand=jvc
network_device=AA:BB:CC:DD:EE:FF</modelDescription>
      </device>
    </root>"""
    parsed_jvc = parse_upnp_renderer_descriptor(xml_with_network_device)
    assert parsed_jvc["brand"] == "jvc"
    assert parsed_jvc["mac_wifi"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.anyio
async def test_client_regenerates_credentials_on_brand_mismatch():
    """Test HisenseTvClient regenerates credentials and clears tokens when brand mismatches client_id."""
    client = HisenseTvClient(
        ip="192.168.50.25",
        mac="e8:51:77:ec:98:1c",
        client_id="E85177EC981C$his$123456_vidaacommon_001",
        username="his$1700000000",
        password="OLDPASSWORD",
        access_token="old_access_token",
        refresh_token="old_refresh_token",
        brand="tos",
        auth_profile="modern",
    )
    # The client_id had $his$, but brand was configured as 'tos' -> credentials should regenerate
    assert "$tos$" in client.client_id
    assert client.username.startswith("tos$")
    assert client.access_token is None
    assert client.refresh_token is None


@pytest.mark.anyio
async def test_flow_preserves_candidate_brand_when_upnp_lacks_brand(monkeypatch):
    """Test config flow does not overwrite candidate brand with 'his' when UPnP query lacks brand."""
    hass = MagicMock(spec=HomeAssistant)
    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.ip_address = "192.168.50.12"
    flow.brand = "tos"  # Resolved during cascade or cert hinting

    client = MagicMock()
    client.brand = "tos"
    client.async_get_device_fingerprint = AsyncMock(return_value={
        "friendly_name": "Living Room TV",
        "model_code": "55C350",
        # Notice: no 'brand' or 'manufacturer' returned by UPnP
    })
    flow.client = client

    await flow._async_discover_device_name()

    # flow.brand MUST remain 'tos' and NOT be overwritten to 'his'
    assert flow.brand == "tos"
    assert flow.discovered_title == "Living Room TV"
