"""UPnP, DLNA, mDNS, and ARP device fingerprinting for Hisense VIDAA TVs."""

from __future__ import annotations

import email.utils
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from .upnp_desc import (
    parse_soap_mute_response,
    parse_soap_transport_info_response,
    parse_soap_volume_response,
    parse_upnp_description_properties,
    parse_upnp_friendly_name,
    parse_upnp_renderer_descriptor,
)

if TYPE_CHECKING:
    from zeroconf import Zeroconf

_LOGGER = logging.getLogger(__name__)

UPNP_PORTS = (38400, 18400)

__all__ = [
    "UPNP_PORTS",
    "format_drift_human",
    "get_arp_mac",
    "get_device_fingerprint",
    "get_tv_timestamp",
    "parse_soap_mute_response",
    "parse_soap_transport_info_response",
    "parse_soap_volume_response",
    "parse_upnp_description_properties",
    "parse_upnp_friendly_name",
    "parse_upnp_renderer_descriptor",
    "probe_upnp_services",
    "query_mdns_fingerprint",
    "query_upnp_descriptor",
]


def probe_upnp_services(ip: str, verbose: bool = True) -> dict[str, Any]:
    """Probes UPnP services (RenderingControl, AVTransport, LanControl) on the target TV."""
    if verbose:
        print(f"\n=======================================================\n  UPnP / DLNA Diagnostic Probe ({ip})\n=======================================================")

    results: dict[str, Any] = {
        "active_port": None,
        "friendly_name": None,
        "volume": None,
        "muted": None,
        "transport_state": None,
        "transport_status": None,
        "lan_control_status": None,
        "lan_control_response": None,
    }

    soap_envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body>"
        '<u:{action} xmlns:u="{service}">'
        "{args}"
        "</u:{action}>"
        "</s:Body>"
        "</s:Envelope>"
    )

    def send_soap(port: int, control_path: str, service: str, action: str, args: str = "") -> tuple[int, str]:
        url = f"http://{ip}:{port}{control_path}"
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service}#{action}"',
            "User-Agent": "HisenseVIDAALanControlClient/1.0",
        }
        body = soap_envelope.format(action=action, service=service, args=args).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status, resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
            return e.code, err_body
        except Exception as e:
            return 0, str(e)

    active_port = None
    for port in UPNP_PORTS:
        url = f"http://{ip}:{port}/MediaServer/rendererdevicedesc.xml"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HisenseVIDAATestClient"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    text = resp.read().decode("utf-8", errors="ignore")
                    friendly = parse_upnp_friendly_name(text) or "Unknown"
                    if verbose:
                        print(f"✅ Found UPnP MediaRenderer on port {port} (Name: {friendly})")
                    active_port = port
                    results["active_port"] = port
                    results["friendly_name"] = friendly
                    break
        except Exception:
            continue

    if not active_port:
        if verbose:
            print(f"❌ No responding UPnP MediaRenderer port found on {ip} (tried {UPNP_PORTS})")
        return results

    # 1. Test RenderingControl GetVolume
    if verbose:
        print("\n--- 1. Testing RenderingControl (Volume & Mute) ---")
    status, resp_xml = send_soap(
        active_port,
        "/upnp/control/mingusrcr",
        "urn:schemas-upnp-org:service:RenderingControl:1",
        "GetVolume",
        "<InstanceID>0</InstanceID><Channel>Master</Channel>",
    )
    if status == 200:
        vol_val = parse_soap_volume_response(resp_xml)
        results["volume"] = vol_val
        if verbose:
            print(f"  [GetVolume] Status: 200 OK -> Current Volume: {vol_val}")
    elif verbose:
        print(f"  [GetVolume] Failed with status {status}: {resp_xml[:100]}")

    # 2. Test RenderingControl GetMute
    if verbose:
        print("\n--- 2. Testing RenderingControl (Volume & Mute) ---")
    status, resp_xml = send_soap(
        active_port,
        "/upnp/control/mingusrcr",
        "urn:schemas-upnp-org:service:RenderingControl:1",
        "GetMute",
        "<InstanceID>0</InstanceID><Channel>Master</Channel>",
    )
    if status == 200:
        is_muted = parse_soap_mute_response(resp_xml)
        results["muted"] = is_muted
        if verbose:
            print(f"  [GetMute]   Status: 200 OK -> Muted: {is_muted}")
    elif verbose:
        print(f"  [GetMute]   Failed with status {status}: {resp_xml[:100]}")

    # 3. Test AVTransport GetTransportInfo
    if verbose:
        print("\n--- 3. Testing AVTransport (Playback State) ---")
    status, resp_xml = send_soap(
        active_port,
        "/upnp/control/mingusavtr",
        "urn:schemas-upnp-org:service:AVTransport:1",
        "GetTransportInfo",
        "<InstanceID>0</InstanceID>",
    )
    if status == 200:
        state_str, st_str = parse_soap_transport_info_response(resp_xml)
        results["transport_state"] = state_str
        results["transport_status"] = st_str
        if verbose:
            print(f"  [GetTransportInfo] Status: 200 OK -> State: {state_str}, Status: {st_str}")
    elif verbose:
        print(f"  [GetTransportInfo] Failed with status {status}: {resp_xml[:100]}")

    # 4. Test HisenseLanControl
    if verbose:
        print("\n--- 3. Testing HisenseLanControl Service ---")
    status, resp_xml = send_soap(
        active_port,
        "/upnp/control/hisense_lan_control",
        "urn:schemas-upnp-org:service:HisenseLanControl:1",
        "LanControlInfo",
        "<OpClass>System</OpClass><OpType>GetStatus</OpType><OpPara></OpPara>",
    )
    results["lan_control_status"] = status
    results["lan_control_response"] = resp_xml
    if verbose:
        if status == 200:
            print(f"  [LanControlInfo] Status: 200 OK -> Response: {resp_xml[:200]}")
        elif status == 404:
            print("  [LanControlInfo] Status: 404 Not Found (Standard behavior on transport_protocol=3160; U6+ specific)")
        else:
            print(f"  [LanControlInfo] Status: {status} -> {resp_xml[:120]}")

    return results


def format_drift_human(offset: int) -> str:
    """Formats a clock drift offset in seconds into a human-readable duration."""
    if offset == 0:
        return "0s"
    abs_off = abs(offset)
    days, rem = divmod(abs_off, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return ("-" if offset < 0 else "+") + " ".join(parts)


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
                parsed_desc = parse_upnp_renderer_descriptor(content)
                for key, val in parsed_desc.items():
                    if val is not None:
                        info[key] = val
            if info["model_name"] or info["friendly_name"]:
                break
        except Exception as e:
            _LOGGER.debug("UPnP device description query failed on port %s: %s", port, e)

    return info


def query_mdns_fingerprint(ip: str, timeout: float = 2.0, zc: Zeroconf | None = None) -> dict[str, Any]:
    """Queries mDNS/Zeroconf records for AirPlay/HomeKit device models."""
    info: dict[str, Any] = {
        "model_code": None,
        "firmware_version": None,
        "serial_number": None,
        "manufacturer": None,
    }

    try:
        from zeroconf import ServiceBrowser

        discovered: dict[str, Any] = {}
        target_ip = ip

        class MDNSListener:
            def add_service(self, zc_inst: Zeroconf, type_: str, name: str) -> None:
                try:
                    s_info = zc_inst.get_service_info(type_, name)
                    if s_info:
                        addrs = [socket.inet_ntoa(a) for a in s_info.addresses]
                        if target_ip in addrs or "Smart TV" in name:
                            discovered[type_] = s_info.properties
                except Exception:
                    pass

            def update_service(self, zc_inst: Zeroconf, type_: str, name: str) -> None:
                pass

            def remove_service(self, zc_inst: Zeroconf, type_: str, name: str) -> None:
                pass

        # Never create a Zeroconf instance here.  Home Assistant 2024.1+ logs a
        # deprecation warning for integrations that instantiate their own Zeroconf
        # instead of using the shared instance provided by
        # ``await homeassistant.components.zeroconf.async_get_instance(hass)``.
        # Callers running inside HA must pass that shared instance via the ``zc``
        # parameter.  When ``zc`` is None (standalone use or unit tests), mDNS
        # discovery is skipped gracefully — UPnP already captures model / firmware.

        if zc is not None:
            browser = ServiceBrowser(zc, ["_airplay._tcp.local.", "_hap._tcp.local."], MDNSListener())
            time.sleep(1.0)
            browser.cancel()

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


def get_device_fingerprint(ip: str, timeout: float = 2.0, zc: Zeroconf | None = None) -> dict[str, Any]:
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
