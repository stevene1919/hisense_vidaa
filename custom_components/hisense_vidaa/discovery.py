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

BRAND_MAP: dict[str, str] = {
    "his": "Hisense",
    "tos": "Toshiba",
    "loe": "Loewe",
    "sch": "Schneider",
    "aka": "Akai",
    "bek": "Beko",
    "tel": "Telefunken",
    "bus": "Bush",
}

__all__ = [
    "BRAND_MAP",
    "UPNP_PORTS",
    "DiscoveredTvInfo",
    "format_drift_human",
    "get_arp_mac",
    "get_device_fingerprint",
    "get_tv_timestamp",
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
    is_vidaa = (
        "vidaa_support" in model_desc
        or "transport_protocol" in model_desc
        or "hisense" in manufacturer.lower()
        or "vidaa" in friendly_name.lower()
        or "hisense" in friendly_name.lower()
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
    brand_code = "his"
    for line in model_desc.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k_clean, v_clean = k.strip().lower(), v.strip().lower()
            if k_clean == "brand" and v_clean:
                brand_code = v_clean
            elif k_clean in ("macwifi", "macethernet") and v:
                mac_clean = v.replace(":", "").replace("-", "").replace(".", "").strip()
                if len(mac_clean) == 12:
                    mac_address = ":".join(mac_clean[i:i + 2] for i in range(0, 12, 2)).lower()
                else:
                    mac_address = v.lower()

    if not manufacturer or manufacturer.strip().lower() in ("", "smarttv", "smart tv", "smarttv."):
        manufacturer = BRAND_MAP.get(brand_code, "Hisense")

    if not mac_address:
        raw_mac = get_arp_mac(host)
        if raw_mac:
            mac_address = raw_mac.lower()

    model = upnp.get("modelName") or upnp.get("modelNumber") or "VIDAA TV"
    title = friendly_name if friendly_name and friendly_name != "Renderer" else f"Hisense TV ({host})"
    udn = getattr(discovery_info, "ssdp_udn", None)
    unique_id = mac_address or udn

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

    mac_address = get_arp_mac(host)
    return DiscoveredTvInfo(
        host=host,
        title=f"Hisense TV ({host})",
        model="VIDAA TV",
        manufacturer="Hisense",
        mac_address=mac_address,
        unique_id=mac_address,
        is_vidaa=True,
    )
