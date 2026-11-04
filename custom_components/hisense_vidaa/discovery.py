"""Auto-discovery handlers and network utilities for Hisense VIDAA smart TVs."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import BRAND_CODE_MAP, BRAND_MAP, GENERIC_MANUFACTURERS
from .protocol.ping import ping_tv
from .tv.fingerprint import (
    UPNP_PORTS,
    format_drift_human,
    get_arp_mac,
    get_device_fingerprint,
    get_tv_timestamp,
    probe_upnp_services,
    query_mdns_fingerprint,
    query_upnp_descriptor,
)

_LOGGER = logging.getLogger(__name__)


def normalize_brand_code(brand_or_mfg: str | None) -> str:
    """Normalize any brand string or manufacturer name to its canonical 3-letter VIDAA cryptographic prefix."""
    if not brand_or_mfg:
        return "his"
    cleaned = brand_or_mfg.strip().lower()
    if cleaned in BRAND_CODE_MAP:
        return BRAND_CODE_MAP[cleaned]
    # Check word tokens first to avoid substring false positives (e.g. 'bra' matching 'unrecognized_brand')
    for token in cleaned.replace("-", " ").replace("_", " ").split():
        if token in BRAND_CODE_MAP:
            return BRAND_CODE_MAP[token]
    # Longer brand names (>= 4 chars) can match as substrings (e.g. 'hisense', 'toshiba', 'schneider')
    for key, code in BRAND_CODE_MAP.items():
        if len(key) >= 4 and key in cleaned:
            return code
    # Preserve explicit 3-letter alphanumeric brand code from UPnP (e.g. brand=xyz)
    if len(cleaned) == 3 and cleaned.isalnum():
        return cleaned
    return "his"


__all__ = [
    "BRAND_CODE_MAP",
    "BRAND_MAP",
    "GENERIC_MANUFACTURERS",
    "UPNP_PORTS",
    "DiscoveredTvInfo",
    "format_drift_human",
    "get_arp_mac",
    "get_device_fingerprint",
    "get_tv_timestamp",
    "normalize_brand_code",
    "parse_ssdp_discovery",
    "parse_zeroconf_discovery",
    "ping_tv",
    "probe_upnp_services",
    "query_mdns_fingerprint",
    "query_upnp_descriptor",
]


@dataclass
class DiscoveredTvInfo:
    """Discovered TV metadata from UPnP / SSDP or Zeroconf."""

    host: str
    title: str
    model: str
    manufacturer: str
    mac_address: str | None = None
    unique_id: str | None = None
    is_vidaa: bool = True
    brand: str = "his"


def parse_ssdp_discovery(
    discovery_info: SsdpServiceInfo | Mapping[str, Any] | Any,
) -> DiscoveredTvInfo | None:
    """Parses SSDP discovery info, validating VIDAA compatibility and extracting host, model, MAC, and friendly name."""
    upnp = getattr(discovery_info, "upnp", None) or {}
    model_desc = upnp.get("modelDescription") or ""
    friendly_name = upnp.get("friendlyName", "")
    manufacturer = upnp.get("manufacturer", "")

    # Filter non-VIDAA devices
    mfg_lower = manufacturer.lower()
    fname_lower = friendly_name.lower()
    is_vidaa = (
        "vidaa_support" in model_desc
        or "transport_protocol" in model_desc
        or "brand=" in model_desc
        or "hisense" in mfg_lower
        or "vidaa" in fname_lower
        or "hisense" in fname_lower
        or (
            any(
                k in mfg_lower
                for k in (
                    "toshiba",
                    "loewe",
                    "tpv",
                    "sharp",
                    "philco",
                    "noblex",
                    "vestel",
                    "schneider",
                    "sansei",
                    "sinotec",
                    "brandt",
                    "metz",
                    "leica",
                )
            )
            and any(t in fname_lower for t in ("tv", "renderer", "media", "vidaa"))
        )
    )
    if not is_vidaa:
        return None

    ssdp_headers = getattr(discovery_info, "ssdp_headers", None) or {}
    host = ssdp_headers.get("_host") or getattr(discovery_info, "ssdp_location", None)
    if host and "://" in host:
        host = urlparse(host).hostname

    if not host:
        return None

    mac_address = None
    for line in model_desc.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k.lower() in ("macwifi", "macethernet", "mac", "network_device") and v:
                mac_clean = v.replace(":", "").replace("-", "").replace(".", "").strip()
                if len(mac_clean) == 12:
                    mac_address = ":".join(mac_clean[i:i + 2] for i in range(0, 12, 2)).lower()
                else:
                    mac_address = v.lower()
                break

    if not mac_address:
        raw_mac = get_arp_mac(host)
        if raw_mac:
            mac_address = raw_mac.lower()

    detected_model = None
    for line in model_desc.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k_s, v_s = k.strip().lower(), v.strip()
            if k_s == "model" and v_s:
                detected_model = v_s
                break

    raw_model_name = (upnp.get("modelName") or "").strip()
    model = (
        (raw_model_name if raw_model_name and raw_model_name != "Renderer" else None)
        or (upnp.get("modelNumber") or "").strip()
        or detected_model
        or "VIDAA TV"
    )
    udn = getattr(discovery_info, "ssdp_udn", None)
    unique_id = mac_address or udn

    manufacturer_clean = (manufacturer or "").strip()
    detected_brand_code: str | None = None
    for line in model_desc.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip().lower(), v.strip().lower()
            if k == "brand":
                detected_brand_code = normalize_brand_code(v)
                break

    if manufacturer_clean.lower() in GENERIC_MANUFACTURERS:
        manufacturer = (
            BRAND_MAP.get(detected_brand_code or "", "Hisense")
            if detected_brand_code
            else "Hisense"
        )
    elif not detected_brand_code:
        detected_brand_code = normalize_brand_code(manufacturer_clean)

    brand_code = detected_brand_code or "his"
    title = (
        friendly_name
        if friendly_name and friendly_name != "Renderer"
        else f"{BRAND_MAP.get(brand_code, 'Hisense')} TV ({host})"
    )

    return DiscoveredTvInfo(
        host=host,
        title=title,
        model=model,
        manufacturer=manufacturer or "Hisense",
        mac_address=mac_address,
        unique_id=unique_id,
        is_vidaa=True,
        brand=brand_code,
    )


def parse_zeroconf_discovery(
    discovery_info: ZeroconfServiceInfo | Mapping[str, Any] | Any,
) -> DiscoveredTvInfo | None:
    """Parses Zeroconf / mDNS discovery info."""
    host = getattr(discovery_info, "host", None)
    if not host:
        return None

    properties = getattr(discovery_info, "properties", {}) or {}

    def _get_prop(*keys: str) -> str | None:
        if not isinstance(properties, Mapping):
            return None
        for key in keys:
            for k, v in properties.items():
                k_str = k.decode("utf-8", errors="ignore") if isinstance(k, bytes) else str(k)
                if k_str.lower() == key.lower():
                    if isinstance(v, bytes):
                        return v.decode("utf-8", errors="ignore").strip()
                    return str(v).strip()
        return None

    raw_model = _get_prop("md", "model")
    raw_mfg = _get_prop("manufacturer", "company", "brand")

    brand_code = normalize_brand_code(raw_mfg)
    mfg_clean = (raw_mfg or "").strip()
    if mfg_clean.lower() in GENERIC_MANUFACTURERS or not mfg_clean:
        manufacturer = BRAND_MAP.get(brand_code, "Hisense")
    else:
        manufacturer = BRAND_MAP.get(mfg_clean.lower(), mfg_clean)

    svc_name = getattr(discovery_info, "name", None) or ""
    clean_name = svc_name.split("._")[0].strip() if "._" in svc_name else svc_name.strip()
    if clean_name and clean_name.lower() not in GENERIC_MANUFACTURERS and clean_name.lower() != "smart tv":
        title = clean_name
    else:
        title = f"{manufacturer} TV ({host})"

    model = raw_model or "VIDAA TV"
    mac_address = get_arp_mac(host)

    return DiscoveredTvInfo(
        host=host,
        title=title,
        model=model,
        manufacturer=manufacturer,
        mac_address=mac_address,
        unique_id=mac_address,
        is_vidaa=True,
        brand=brand_code,
    )
