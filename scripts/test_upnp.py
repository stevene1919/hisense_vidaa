#!/usr/bin/env python3
"""Standalone CLI test tool for Hisense VIDAA UPnP LAN Control and DLNA services.

Probes the TV's UPnP HTTP stack (port 38400 / 18400) to query live volume, mute,
transport info, and test LanControlInfo availability using standard library only.
"""

from __future__ import annotations

import argparse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_TV_IP = "192.168.50.12"
CANDIDATE_PORTS = (38400, 18400)

SOAP_ENVELOPE = (
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


def send_soap(
    ip: str,
    port: int,
    control_path: str,
    service: str,
    action: str,
    args: str = "",
    timeout: float = 2.0,
) -> tuple[int, str]:
    """Sends a UPnP SOAP action and returns status code and response body."""
    url = f"http://{ip}:{port}{control_path}"
    headers = {
        "Content-Type": 'text/xml; charset="utf-8"',
        "SOAPAction": f'"{service}#{action}"',
        "User-Agent": "HisenseVIDAALanControlClient/1.0",
    }
    body = SOAP_ENVELOPE.format(action=action, service=service, args=args).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore") if e.fp else ""
        return e.code, err_body
    except Exception as e:
        return 0, str(e)


def probe_upnp(ip: str) -> None:
    """Probes UPnP services and actions on the target TV."""
    print("\n=======================================================")
    print("📡 Hisense VIDAA UPnP LAN Control Diagnostic Tool")
    print(f"Target: {ip}")
    print("=======================================================\n")

    active_port = None
    for port in CANDIDATE_PORTS:
        url = f"http://{ip}:{port}/MediaServer/rendererdevicedesc.xml"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HisenseVIDAATestClient"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    text = resp.read().decode("utf-8", errors="ignore")
                    root = ET.fromstring(text)
                    ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                    fn = root.find(".//d:friendlyName", ns)
                    friendly = fn.text if fn is not None else "Unknown"
                    print(f"✅ Found UPnP MediaRenderer on port {port} (Name: {friendly})")
                    active_port = port
                    break
        except Exception:
            continue

    if not active_port:
        print(f"❌ No responding UPnP MediaRenderer port found on {ip} (tried {CANDIDATE_PORTS})")
        return

    # 1. Test RenderingControl GetVolume
    print("\n--- 1. Testing RenderingControl (Volume & Mute) ---")
    status, resp_xml = send_soap(
        ip,
        active_port,
        "/upnp/control/mingusrcr",
        "urn:schemas-upnp-org:service:RenderingControl:1",
        "GetVolume",
        "<InstanceID>0</InstanceID><Channel>Master</Channel>",
    )
    if status == 200:
        try:
            root = ET.fromstring(resp_xml)
            vol = root.find(".//CurrentVolume")
            vol_str = vol.text if vol is not None else "Unknown"
            print(f"  [GetVolume] Status: 200 OK -> Current Volume: {vol_str}")
        except Exception as e:
            print(f"  [GetVolume] Status: 200 OK (XML parse error: {e})")
    else:
        print(f"  [GetVolume] Failed with status {status}: {resp_xml[:100]}")

    # 2. Test RenderingControl GetMute
    status, resp_xml = send_soap(
        ip,
        active_port,
        "/upnp/control/mingusrcr",
        "urn:schemas-upnp-org:service:RenderingControl:1",
        "GetMute",
        "<InstanceID>0</InstanceID><Channel>Master</Channel>",
    )
    if status == 200:
        try:
            root = ET.fromstring(resp_xml)
            mute = root.find(".//CurrentMute")
            is_muted = mute.text == "1" if mute is not None else False
            print(f"  [GetMute]   Status: 200 OK -> Muted: {is_muted}")
        except Exception as e:
            print(f"  [GetMute]   Status: 200 OK (XML parse error: {e})")
    else:
        print(f"  [GetMute]   Failed with status {status}: {resp_xml[:100]}")

    # 3. Test AVTransport GetTransportInfo
    print("\n--- 2. Testing AVTransport (Playback State) ---")
    status, resp_xml = send_soap(
        ip,
        active_port,
        "/upnp/control/mingusavtr",
        "urn:schemas-upnp-org:service:AVTransport:1",
        "GetTransportInfo",
        "<InstanceID>0</InstanceID>",
    )
    if status == 200:
        try:
            root = ET.fromstring(resp_xml)
            state = root.find(".//CurrentTransportState")
            st = root.find(".//CurrentTransportStatus")
            state_str = state.text if state is not None else "Unknown"
            st_str = st.text if st is not None else "Unknown"
            print(f"  [GetTransportInfo] Status: 200 OK -> State: {state_str}, Status: {st_str}")
        except Exception as e:
            print(f"  [GetTransportInfo] Status: 200 OK (XML parse error: {e})")
    else:
        print(f"  [GetTransportInfo] Failed with status {status}: {resp_xml[:100]}")

    # 4. Test HisenseLanControl (Proprietary service)
    print("\n--- 3. Testing HisenseLanControl Service ---")
    status, resp_xml = send_soap(
        ip,
        active_port,
        "/upnp/control/hisense_lan_control",
        "urn:schemas-upnp-org:service:HisenseLanControl:1",
        "LanControlInfo",
        "<OpClass>System</OpClass><OpType>GetStatus</OpType><OpPara></OpPara>",
    )
    if status == 200:
        print(f"  [LanControlInfo] Status: 200 OK -> Response: {resp_xml[:200]}")
    elif status == 404:
        print("  [LanControlInfo] Status: 404 Not Found (Standard behavior on transport_protocol=3160; U6+ specific)")
    else:
        print(f"  [LanControlInfo] Status: {status} -> {resp_xml[:120]}")

    print("\n=======================================================")
    print("✅ Diagnostic run completed!")
    print("=======================================================\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Hisense VIDAA UPnP LAN Control services")
    parser.add_argument("--ip", default=DEFAULT_TV_IP, help=f"TV IP address (default: {DEFAULT_TV_IP})")
    args = parser.parse_args()
    probe_upnp(args.ip)


if __name__ == "__main__":
    main()
