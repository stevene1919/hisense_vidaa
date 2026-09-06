"""Device discovery and fingerprinting utilities for Hisense VIDAA TV."""

import logging
import socket
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

_LOGGER = logging.getLogger(__name__)


def get_device_fingerprint(ip: str, timeout: float = 2.0) -> dict[str, Any]:
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
    }

    # 1. Query UPnP / DLNA descriptor on port 38400
    try:
        url = f"http://{ip}:38400/MediaServer/rendererdevicedesc.xml"
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
    except Exception as e:
        _LOGGER.debug("UPnP device description query failed: %s", e)

    # 2. Query mDNS / Zeroconf if available
    try:
        from zeroconf import ServiceBrowser, Zeroconf

        discovered = {}
        target_ip = ip

        class MDNSListener:
            def add_service(self, zc, type_, name):
                try:
                    s_info = zc.get_service_info(type_, name)
                    if s_info:
                        addrs = [socket.inet_ntoa(a) for a in s_info.addresses]
                        if target_ip in addrs or "Smart TV" in name:
                            discovered[type_] = s_info.properties
                except Exception:
                    pass

            def update_service(self, zc, type_, name):
                pass

            def remove_service(self, zc, type_, name):
                pass

        zc = Zeroconf()
        ServiceBrowser(zc, ["_airplay._tcp.local.", "_hap._tcp.local."], MDNSListener())
        time.sleep(1.0)
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
        if company_bytes and not info["manufacturer"]:
            info["manufacturer"] = company_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        _LOGGER.debug("mDNS device discovery skipped: %s", e)

    return info
