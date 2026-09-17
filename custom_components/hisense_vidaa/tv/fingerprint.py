"""UPnP, DLNA, mDNS, and ARP device fingerprinting for Hisense VIDAA TVs."""

from __future__ import annotations

import email.utils
import logging
import os
import socket
import time
import urllib.request
from typing import Any

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)

UPNP_PORTS = (38400, 18400)

__all__ = [
    "UPNP_PORTS",
    "get_arp_mac",
    "get_device_fingerprint",
    "get_tv_timestamp",
    "query_mdns_fingerprint",
    "query_upnp_descriptor",
]


def get_tv_timestamp(ip: str, timeout: float = 2.0) -> int | None:
    """Fetches the live timestamp from the TV's UPnP HTTP Date header."""
    for port in UPNP_PORTS:
        try:
            url = f"http://{ip}:{port}/MediaServer/rendererdevicedesc.xml"
            req = urllib.request.Request(url, headers={"User-Agent": "HisenseVIDAAClient"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                date_str = response.headers.get("Date")
                if date_str:
                    dt = email.utils.parsedate_to_datetime(date_str)
                    return int(dt.timestamp())
        except Exception as e:
            _LOGGER.debug("Could not fetch TV clock from HTTP Date header on port %s: %s", port, e)
    return None


def get_arp_mac(ip: str) -> str | None:
    """Discovers hardware MAC address via getmac or Linux ARP table."""
    try:
        from getmac import get_mac_address

        mac = get_mac_address(ip=ip)
        if mac:
            return mac.lower()
    except Exception:
        pass

    try:
        if os.path.exists("/proc/net/arp"):
            with open("/proc/net/arp") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[0] == ip:
                        mac = parts[3]
                        if mac != "00:00:00:00:00:00":
                            return mac.lower()
    except Exception:
        pass

    return None


def query_upnp_descriptor(ip: str, timeout: float = 2.0) -> dict[str, Any]:
    """Queries UPnP/DLNA XML descriptors across candidate ports (38400, 18400)."""
    info: dict[str, Any] = {
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
        "tv_timestamp": None,
    }

    for port in UPNP_PORTS:
        try:
            if not info["tv_timestamp"]:
                info["tv_timestamp"] = get_tv_timestamp(ip, timeout=timeout)
            url = f"http://{ip}:{port}/MediaServer/rendererdevicedesc.xml"
            req = urllib.request.Request(url, headers={"User-Agent": "HisenseVIDAATestClient"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8", errors="ignore")
                root = ET.fromstring(content)
                ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                device = root.find("d:device", ns)
                if device is not None:
                    fn = device.find("d:friendlyName", ns)
                    mn = device.find("d:modelName", ns)
                    mnum = device.find("d:modelNumber", ns)
                    mfg = device.find("d:manufacturer", ns)
                    desc = device.find("d:modelDescription", ns)

                    if fn is not None:
                        info["friendly_name"] = fn.text
                    if mn is not None:
                        info["model_name"] = mn.text
                    if mnum is not None:
                        info["model_number"] = mnum.text
                    if mfg is not None:
                        info["manufacturer"] = mfg.text

                    if desc is not None and desc.text:
                        info["upnp_raw"] = desc.text.strip()
                        for line in desc.text.strip().splitlines():
                            if "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip()
                                if k == "macWifi":
                                    info["mac_wifi"] = v
                                elif k == "macEthernet":
                                    info["mac_ethernet"] = v
                                elif k == "brand":
                                    info["brand"] = v
                                elif k == "platform":
                                    info["platform"] = v
                                elif k == "vidaa_support":
                                    info["vidaa_support"] = v
                                elif k == "voice":
                                    info["voice"] = v
                                elif k == "transport_protocol":
                                    info["transport_protocol"] = v
            if info["model_name"] or info["friendly_name"]:
                break
        except Exception as e:
            _LOGGER.debug("UPnP device description query failed on port %s: %s", port, e)

    return info


def query_mdns_fingerprint(ip: str, timeout: float = 2.0, zc: Any = None) -> dict[str, Any]:
    """Queries mDNS/Zeroconf records for AirPlay/HomeKit device models."""
    info: dict[str, Any] = {
        "model_code": None,
        "firmware_version": None,
        "serial_number": None,
        "manufacturer": None,
    }

    try:
        from zeroconf import ServiceBrowser, Zeroconf

        discovered: dict[str, Any] = {}
        target_ip = ip

        class MDNSListener:
            def add_service(self, zc_inst: Any, type_: str, name: str) -> None:
                try:
                    s_info = zc_inst.get_service_info(type_, name)
                    if s_info:
                        addrs = [socket.inet_ntoa(a) for a in s_info.addresses]
                        if target_ip in addrs or "Smart TV" in name:
                            discovered[type_] = s_info.properties
                except Exception:
                    pass

            def update_service(self, zc_inst: Any, type_: str, name: str) -> None:
                pass

            def remove_service(self, zc_inst: Any, type_: str, name: str) -> None:
                pass

        should_close_zc = False
        if zc is None:
            try:
                import asyncio
                asyncio.get_running_loop()
                zc = None
            except RuntimeError:
                try:
                    zc = Zeroconf()
                    should_close_zc = True
                except Exception:
                    zc = None

        if zc is not None:
            browser = ServiceBrowser(zc, ["_airplay._tcp.local.", "_hap._tcp.local."], MDNSListener())
            time.sleep(1.0)
            browser.cancel()
            if should_close_zc:
                zc.close()

        airplay = discovered.get("_airplay._tcp.local.", {})
        hap = discovered.get("_hap._tcp.local.", {})

        model_bytes = airplay.get(b"model") or hap.get(b"md")
        fv_bytes = airplay.get(b"fv")
        serial_bytes = airplay.get(b"serialNumber")
        company_bytes = airplay.get(b"company") or airplay.get(b"manufacturer")

        if model_bytes:
            info["model_code"] = model_bytes.decode("utf-8", errors="ignore")
        if fv_bytes:
            info["firmware_version"] = fv_bytes.decode("utf-8", errors="ignore")
        if serial_bytes:
            info["serial_number"] = serial_bytes.decode("utf-8", errors="ignore")
        if company_bytes:
            info["manufacturer"] = company_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        _LOGGER.debug("mDNS device discovery skipped: %s", e)

    return info


def get_device_fingerprint(ip: str, timeout: float = 2.0, zc: Any = None) -> dict[str, Any]:
    """Fetches UPnP, DLNA, and mDNS device metadata for model and capability identification."""
    info = {
        "friendly_name": None,
        "model_name": None,
        "model_number": None,
        "model_code": None,
        "manufacturer": None,
        "brand": None,
        "platform": None,
        "vidaa_support": None,
        "voice": None,
        "transport_protocol": None,
        "mac_wifi": None,
        "mac_ethernet": None,
        "firmware_version": None,
        "serial_number": None,
        "upnp_raw": None,
        "tv_timestamp": None,
    }

    upnp_info = query_upnp_descriptor(ip=ip, timeout=timeout)
    for k, v in upnp_info.items():
        if v is not None:
            info[k] = v

    mdns_info = query_mdns_fingerprint(ip=ip, timeout=timeout, zc=zc)
    if mdns_info.get("model_code"):
        info["model_code"] = mdns_info["model_code"]
    if mdns_info.get("firmware_version"):
        info["firmware_version"] = mdns_info["firmware_version"]
    if mdns_info.get("serial_number"):
        info["serial_number"] = mdns_info["serial_number"]
    if mdns_info.get("manufacturer") and not info.get("manufacturer"):
        info["manufacturer"] = mdns_info["manufacturer"]

    return info
