"""UPnP and DLNA XML descriptor parsers for Hisense VIDAA TV."""

from __future__ import annotations

import logging
from typing import Any

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)

UPNP_DEVICE_NS = {"d": "urn:schemas-upnp-org:device-1-0"}

GENERIC_MANUFACTURERS: frozenset[str] = frozenset({
    "",
    "smarttv",
    "smart tv",
    "smarttv.",
    "http://www.smarttv.com",
    "www.smarttv.com",
    "renderer",
    "unknown",
})

BRAND_MAP: dict[str, str] = {
    "his": "Hisense",
    "hisense": "Hisense",
    "tos": "Toshiba",
    "toshiba": "Toshiba",
    "loe": "Loewe",
    "loewe": "Loewe",
    "sch": "Schneider",
    "schneider": "Schneider",
    "aka": "Akai",
    "akai": "Akai",
    "bek": "Beko",
    "beko": "Beko",
    "tel": "Telefunken",
    "telefunken": "Telefunken",
    "bus": "Bush",
    "bush": "Bush",
}


def normalize_manufacturer_brand(
    brand_code: str | None,
    current_manufacturer: str | None = None,
) -> str:
    """Normalizes generic manufacturer placeholders (e.g. SmartTV) or brand codes (e.g. his) to actual brand name."""
    clean_mfg = (current_manufacturer or "").strip().lower()
    if clean_mfg in BRAND_MAP:
        return BRAND_MAP[clean_mfg]
    if current_manufacturer and clean_mfg not in GENERIC_MANUFACTURERS:
        return current_manufacturer.strip()

    if brand_code:
        clean_brand = brand_code.strip().lower()
        if clean_brand in BRAND_MAP:
            return BRAND_MAP[clean_brand]
        for key, val in BRAND_MAP.items():
            if clean_brand.startswith(key):
                return val
        if clean_brand not in GENERIC_MANUFACTURERS:
            return brand_code.strip().title()

    return "Hisense"


__all__ = [
    "BRAND_MAP",
    "GENERIC_MANUFACTURERS",
    "UPNP_DEVICE_NS",
    "normalize_manufacturer_brand",
    "parse_soap_mute_response",
    "parse_soap_transport_info_response",
    "parse_soap_volume_response",
    "parse_upnp_description_properties",
    "parse_upnp_friendly_name",
    "parse_upnp_renderer_descriptor",
]


def parse_upnp_friendly_name(xml_content: str) -> str | None:
    """Parses friendlyName from UPnP device XML string."""
    try:
        root = ET.fromstring(xml_content)
        fn = root.find(".//d:friendlyName", UPNP_DEVICE_NS)
        if fn is not None and fn.text:
            return fn.text.strip()
    except Exception as exc:
        _LOGGER.debug("Failed to parse friendlyName from UPnP XML: %s", exc)
    return None


def parse_upnp_description_properties(desc_text: str) -> dict[str, str]:
    """Parses key-value pairs formatted as 'key=value' inside modelDescription."""
    properties: dict[str, str] = {}
    if not desc_text:
        return properties

    for line in desc_text.strip().splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            properties[key.strip()] = val.strip()
    return properties


def parse_upnp_renderer_descriptor(xml_content: str) -> dict[str, Any]:
    """Parses full UPnP MediaRenderer XML description document into metadata dict."""
    parsed: dict[str, Any] = {
        "friendly_name": None,
        "model_name": None,
        "model_number": None,
        "manufacturer": None,
        "brand": None,
        "platform": None,
        "vidaa_support": None,
        "voice": None,
        "transport_protocol": None,
        "mac_wifi": None,
        "mac_ethernet": None,
        "upnp_raw": None,
    }

    try:
        root = ET.fromstring(xml_content)
        device = root.find("d:device", UPNP_DEVICE_NS)
        if device is None:
            device = root.find(".//d:device", UPNP_DEVICE_NS)

        if device is not None:
            fn = device.find("d:friendlyName", UPNP_DEVICE_NS)
            mn = device.find("d:modelName", UPNP_DEVICE_NS)
            mnum = device.find("d:modelNumber", UPNP_DEVICE_NS)
            mfg = device.find("d:manufacturer", UPNP_DEVICE_NS)
            desc = device.find("d:modelDescription", UPNP_DEVICE_NS)

            if fn is not None and fn.text:
                parsed["friendly_name"] = fn.text.strip()
            if mn is not None and mn.text:
                parsed["model_name"] = mn.text.strip()
            if mnum is not None and mnum.text:
                parsed["model_number"] = mnum.text.strip()
            if mfg is not None and mfg.text:
                parsed["manufacturer"] = mfg.text.strip()

            if desc is not None and desc.text:
                raw_desc = desc.text.strip()
                parsed["upnp_raw"] = raw_desc
                props = parse_upnp_description_properties(raw_desc)
                if "macWifi" in props:
                    parsed["mac_wifi"] = props["macWifi"]
                if "macEthernet" in props:
                    parsed["mac_ethernet"] = props["macEthernet"]
                if "brand" in props:
                    parsed["brand"] = props["brand"]
                if "platform" in props:
                    parsed["platform"] = props["platform"]
                if "vidaa_support" in props:
                    parsed["vidaa_support"] = props["vidaa_support"]
                if "voice" in props:
                    parsed["voice"] = props["voice"]
                if "transport_protocol" in props:
                    parsed["transport_protocol"] = props["transport_protocol"]
    except Exception as exc:
        _LOGGER.debug("Failed to parse UPnP renderer descriptor XML: %s", exc)

    parsed["manufacturer"] = normalize_manufacturer_brand(
        parsed.get("brand"), parsed.get("manufacturer")
    )

    return parsed


def parse_soap_volume_response(resp_xml: str) -> int | None:
    """Parses CurrentVolume integer from SOAP GetVolume response."""
    try:
        root = ET.fromstring(resp_xml)
        vol = root.find(".//CurrentVolume")
        if vol is not None and vol.text:
            return int(vol.text.strip())
    except Exception as exc:
        _LOGGER.debug("Failed to parse SOAP volume: %s", exc)
    return None


def parse_soap_mute_response(resp_xml: str) -> bool:
    """Parses CurrentMute boolean from SOAP GetMute response."""
    try:
        root = ET.fromstring(resp_xml)
        mute = root.find(".//CurrentMute")
        if mute is not None and mute.text:
            return mute.text.strip() == "1"
    except Exception as exc:
        _LOGGER.debug("Failed to parse SOAP mute: %s", exc)
    return False


def parse_soap_transport_info_response(resp_xml: str) -> tuple[str, str]:
    """Parses CurrentTransportState and CurrentTransportStatus from SOAP response."""
    try:
        root = ET.fromstring(resp_xml)
        state = root.find(".//CurrentTransportState")
        st = root.find(".//CurrentTransportStatus")
        state_str = state.text.strip() if state is not None and state.text else "Unknown"
        st_str = st.text.strip() if st is not None and st.text else "Unknown"
        return state_str, st_str
    except Exception as exc:
        _LOGGER.debug("Failed to parse SOAP transport info: %s", exc)
    return "Unknown", "Unknown"

