#!/usr/bin/env python3
"""Hisense VIDAA Integration CLI Test Script.

Allows direct testing and debugging of authentication, pairing PIN, token refreshes,
feature probing, and command execution using the exact same HisenseTvClient logic as the Home Assistant integration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time

# Ensure script directory or HA config is in Python path for package resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMP_DIR = os.path.join(SCRIPT_DIR, "custom_components", "hisense_vidaa")
HA_CONFIG_DIR = "/config"
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if os.path.isdir(HA_CONFIG_DIR) and HA_CONFIG_DIR not in sys.path:
    sys.path.insert(0, HA_CONFIG_DIR)

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.discovery import get_arp_mac
from custom_components.hisense_vidaa.tv.probe import (
    create_client_from_creds,
    generate_markdown_report,
    load_credentials_file,
    probe_tv_features,
    save_credentials_file,
)

DEFAULT_CREDS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")


def do_ping(ip: str, creds: dict, certfile: str | None, keyfile: str | None, profile: str = "auto", ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    print(f"\n[PING] Probing TV connectivity and MQTT broker at {ip}:36669 (Profile: {profile})...")

    access_token = None
    client_id = None
    username = None
    if creds:
        access_token = creds.get("accesstoken") or creds.get("access_token")
        client_id = creds.get("client_id")
        username = creds.get("username")

    client = HisenseTvClient(
        ip=ip,
        client_id=client_id,
        username=username,
        access_token=access_token,
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        auth_profile=profile,
        verify_ssl=verify_ssl,
    )

    try:
        res = client.ping()
        dev = res.get("device_info") or {}
        auth_probe = res.get("auth_probe") or {}

        print("\n📡 Connection Probe Results:")
        print(f"  • [1] TCP Port 36669:         {'✅ OPEN' if res['tcp_port_open'] else '❌ CLOSED / UNREACHABLE'}")
        print(f"  • [2] TLS Handshake:          {'✅ SUCCESS' if res['tls_handshake'] else '❌ FAILED'} ({res.get('tls_version') or 'N/A'}, {res.get('cipher') or 'N/A'})")

        if res.get("mqtt_rc") is not None:
            if res["mqtt_connected"]:
                print("  • [3] Stored Credentials:     ✅ ACCEPTED (rc=0, broker is actively listening and responsive)")
            else:
                print(f"  • [3] Stored Credentials:     ⚠️ {res['mqtt_status']}")
        else:
            print(f"  • [3] Stored Credentials:     ℹ️ {res['mqtt_status']}")

        print("\n🔐 Initial Pairing Auth Compatibility:")
        std = auth_probe.get("standard_dynamic", {})
        modern = auth_probe.get("modern_dynamic", {})
        legacy = auth_probe.get("legacy_static", {})

        std_p_str = "✅ ACCEPTED (rc=0)" if std.get("supported") else f"❌ REJECTED (rc={std.get('rc')})"
        mod_p_str = "✅ ACCEPTED (rc=0)" if modern.get("supported") else f"❌ REJECTED (rc={modern.get('rc')})"
        leg_p_str = "✅ ACCEPTED (rc=0)" if legacy.get("supported") else f"❌ REJECTED (rc={legacy.get('rc')})"

        print(f"  • Standard Dynamic Auth:      {std_p_str}")
        print(f"  • Modern XOR Dynamic Auth:    {mod_p_str}")
        print(f"  • Legacy Static Auth:         {leg_p_str}")

        if dev.get("model_code") or dev.get("model_name") or dev.get("friendly_name"):
            mfg = dev.get("manufacturer") or dev.get("brand") or "Hisense"
            model = dev.get("model_code") or dev.get("model_name") or dev.get("friendly_name")
            print(f"\n📺 Discovered TV Profile: {mfg} {model}")
            if dev.get("firmware_version"):
                print(f"  • Firmware Build:             {dev['firmware_version']}")
            if dev.get("platform"):
                print(f"  • Platform Indicator:         Platform {dev['platform']}")

        arp_mac = get_arp_mac(ip)
        if arp_mac:
            print(f"  • Discovered MAC (ARP):       {arp_mac}")
        if dev.get("mac_wifi"):
            print(f"  • Wi-Fi MAC (UPnP):           {dev['mac_wifi']}")
        if dev.get("mac_ethernet"):
            print(f"  • Ethernet MAC (UPnP):        {dev['mac_ethernet']}")

        if res.get("auth_recommendation"):
            print("\n💡 Firmware Compatibility & Integration Recommendation:")
            print(f"  • {res['auth_recommendation']}")

        if res.get("error"):
            print(f"\n⚠️ Notice: {res['error']}")
    except FileNotFoundError as e:
        print(f"\n❌ Certificate Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Probe Failed: {e}")
        sys.exit(1)


def do_probe(ip: str, creds: dict, certfile: str | None, keyfile: str | None, profile: str = "auto", ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    print(f"\n🔍 [PROBE] Probing TV features and menu capabilities at {ip}:36669...\n")
    client = create_client_from_creds(creds, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl, auth_profile=profile) if creds else HisenseTvClient(
        ip=ip, certfile=certfile, keyfile=keyfile, ca_cert=ca_cert, auth_profile=profile, verify_ssl=verify_ssl
    )

    probe_res = probe_tv_features(client, wait_time=2.5)
    if not probe_res.connected:
        print("❌ Could not connect to TV MQTT broker. Ensure TV is powered on and paired.")
        return

    print("=" * 70)
    print("📋 TV Feature Capabilities & Settings Tree:")
    print("=" * 70 + "\n")

    print("### 🖼️ Picture Settings & Modes")
    if probe_res.picture_settings:
        for item in probe_res.picture_settings:
            opts = f" (Options: {', '.join(item.options)})" if item.options else ""
            val = f" [Current: {item.menu_value}]" if item.menu_value is not None else ""
            print(f"- **{item.menu_name}** (ID: `{item.menu_id}`, Type: `{item.menu_type}`){val}{opts}")
    else:
        print("- No dynamic picture menu data returned (Static defaults active)")

    print("\n### 🔊 Sound Settings & Modes")
    if probe_res.sound_settings:
        for item in probe_res.sound_settings:
            opts = f" (Options: {', '.join(item.options)})" if item.options else ""
            val = f" [Current: {item.menu_value}]" if item.menu_value is not None else ""
            print(f"- **{item.menu_name}** (ID: `{item.menu_id}`, Type: `{item.menu_type}`){val}{opts}")
    else:
        print("- No dynamic sound menu data returned (Static defaults active)")

    print(f"\n### 🔌 Input Sources ({len(probe_res.sources)} detected)")
    for s in probe_res.sources:
        active = " [ACTIVE]" if s.get("is_signal") in ("1", 1, True) or s.get("is_active") else ""
        print(f"- `{s.get('sourceid')}`: **{s.get('sourcename', 'Unknown')}**{active}")

    print(f"\n### 📱 Installed Smart TV Applications ({len(probe_res.apps)} detected)")
    for a in probe_res.apps[:20]:
        print(f"- **{a.get('name') or a.get('appName', 'Unknown')}** (`appId`: `{a.get('appId')}`)")
    if len(probe_res.apps) > 20:
        print(f"- ... and {len(probe_res.apps) - 20} more apps")

    print("\n" + "=" * 70)


def do_report(ip: str, mac: str | None, creds: dict, certfile: str | None, keyfile: str | None, profile: str = "auto", ca_cert: str | None = None, verify_ssl: bool = False, probe: bool = False) -> None:
    print(f"\n🔍 [REPORT] Collecting diagnostics and generating GitHub issue report for {ip}...\n")

    access_token = None
    client_id = None
    username = None
    if creds:
        access_token = creds.get("accesstoken") or creds.get("access_token")
        client_id = creds.get("client_id")
        username = creds.get("username")

    client = HisenseTvClient(
        ip=ip,
        mac=mac,
        client_id=client_id,
        username=username,
        access_token=access_token,
        certfile=certfile,
        keyfile=keyfile,
        ca_cert=ca_cert,
        auth_profile="auto",
        verify_ssl=verify_ssl,
    )

    try:
        ping_res = client.ping(timeout=3.0)
        version = "Unknown"
        manifest_path = os.path.join(COMP_DIR, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    version = json.load(f).get("version", "Unknown")
            except Exception:
                pass

        probe_res = None
        if probe and ping_res.get("tcp_port_open") and (creds or client.auth_profile == "legacy"):
            probe_client = create_client_from_creds(creds, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl, auth_profile=profile) if creds else client
            probe_res = probe_tv_features(probe_client, wait_time=2.0)

        report_md = generate_markdown_report(
            ip=ip,
            ping_result=ping_res,
            probe_result=probe_res,
            mac=mac,
            version=version,
        )

        print("=" * 70)
        print("📋 Copy & Paste the Markdown below into your GitHub Issue report:")
        print("=" * 70 + "\n")
        print(report_md)
        print("\n" + "=" * 70)
    except FileNotFoundError as e:
        print(f"\n❌ Certificate Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Report Generation Failed: {e}")
        sys.exit(1)


def do_test_ssl(ip: str, certfile: str | None, keyfile: str | None, profile: str = "auto", ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    print(f"\n[SSL] Testing raw TLS connection to Hisense TV at {ip}:36669 (Profile: {profile})...")
    client = HisenseTvClient(ip=ip, certfile=certfile, keyfile=keyfile, ca_cert=ca_cert, auth_profile=profile, verify_ssl=verify_ssl)
    try:
        res = client.test_ssl_connection()
        print("\n✅ TLS Connection Successful!")
        print(f"  • TV Address:    {ip}:36669")
        print(f"  • TLS Version:   {res['tls_version']}")
        print(f"  • Cipher Suite:  {res['cipher']} ({res['bits']} bits)")
        print(f"  • Certificate:   {res['certfile']}")
        print(f"  • Private Key:   {res['keyfile']}")
        if res.get("ca_cert"):
            print(f"  • Root CA:       {res['ca_cert']}")
    except FileNotFoundError as e:
        print(f"\n❌ Certificate Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TLS Connection Failed: {e}")
        sys.exit(1)


async def do_auth(ip: str, mac: str | None, certfile: str | None, keyfile: str | None, save_path: str, profile: str = "auto", ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    if not mac:
        mac = get_arp_mac(ip)
        if mac:
            print(f"🔍 Auto-discovered Hardware MAC via ARP: {mac}")
    print(f"\n[AUTH] Connecting to Hisense TV at {ip} on port 36669 (TLS, Profile: {profile})...")
    client = HisenseTvClient(ip=ip, mac=mac, certfile=certfile, keyfile=keyfile, ca_cert=ca_cert, auth_profile=profile, verify_ssl=verify_ssl)
    try:
        await client.async_start_auth()

        if profile == "legacy" or client.auth_profile == "legacy":
            print("\n✅ Legacy static credentials active (no PIN required)!")
            creds = {
                "ip_address": ip,
                "mac_address": mac,
                "auth_profile": "legacy",
                "client_id": client.client_id,
                "username": client.username,
                "password": client.password,
                "accesstoken": client.access_token,
                "accesstoken_time": 0,
                "accesstoken_duration_day": 0,
                "refreshtoken": None,
                "refreshtoken_time": 0,
                "refreshtoken_duration_day": 0,
            }
            save_credentials_file(save_path, creds)
            return

        print("\n✅ Initial connection established!")
        print("📺 Look at your TV screen. A 4-digit PIN should now be visible.")
        pin = input("👉 Enter the 4-digit PIN: ").strip()

        print(f"\n[AUTH] Submitting PIN '{pin}' and requesting tokens...")
        await client.async_submit_pin(pin)

        creds = {
            "ip_address": ip,
            "mac_address": mac,
            "client_id": client.client_id,
            "username": client.username,
            "password": client.password,
            "accesstoken": client.access_token,
            "accesstoken_time": client.access_token_time,
            "accesstoken_duration_day": client.access_token_duration,
            "refreshtoken": client.refresh_token,
            "refreshtoken_time": client.refresh_token_time,
            "refreshtoken_duration_day": client.refresh_token_duration,
        }

        print("\n🎉 Authentication successful!")
        print(f"  • Client ID:     {client.client_id}")
        print(f"  • Username:      {client.username}")
        print(f"  • Access Token:  {client.access_token[:15]}... ({client.access_token_duration} days)")
        print(f"  • Refresh Token: {client.refresh_token[:15]}... ({client.refresh_token_duration} days)")

        save_credentials_file(save_path, creds)
    except FileNotFoundError as e:
        print(f"\n❌ Certificate Error: {e}")
        print("  💡 Tip: Ensure your client certificate (.pem/.crt) and private key (.key) are placed in ssl/ or specified via --cert / --key.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        err_str = str(e).lower()
        if "code 5" in err_str or "not authorized" in err_str:
            print("\n💡 Diagnosis (MQTT RC 5):")
            print("  • The TV broker rejected the initial credentials during pairing.")
            print("  • If your TV is running a newer firmware build (e.g. VIDAA U7+ / Q0704+),")
            print("    it may require a newer authentication signature currently under development.")
            print("  • Run the diagnostic report to capture TV details:")
            print(f"    python3 test_client.py report --ip {ip} --probe")
        elif "timed out" in err_str:
            print("\n💡 Diagnosis (Timeout):")
            print("  • The TV did not respond to the PIN handshake request in time.")
            print("  • Ensure the TV screen is turned ON and connected to the same local network subnet.")
        sys.exit(1)


async def do_listen(creds: dict, certfile: str | None, keyfile: str | None, save_path: str, ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    ip = creds.get("ip_address")
    print(f"\n[LISTEN] Connecting to TV at {ip} with stored credentials...")

    client = create_client_from_creds(creds, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl)

    def on_token_refreshed(c: HisenseTvClient) -> None:
        print(f"\n🔄 [TOKEN REFRESHED] New access token: {c.access_token[:15]}...")
        creds["accesstoken"] = c.access_token
        creds["accesstoken_time"] = c.access_token_time
        creds["refreshtoken"] = c.refresh_token
        creds["refreshtoken_time"] = c.refresh_token_time
        save_credentials_file(save_path, creds)

    client.register_token_refreshed_callback(on_token_refreshed)
    client.register_state_callback(lambda data: print(f"📡 [STATE] {json.dumps(data)}"))
    client.register_volume_callback(lambda data: print(f"🔊 [VOLUME] {json.dumps(data)}"))
    client.register_picture_callback(lambda data: print(f"🖼️ [PICTURE] {json.dumps(data)}"))
    client.register_sound_callback(lambda data: print(f"🎵 [SOUND] {json.dumps(data)}"))
    client.register_sourcelist_callback(lambda data: print(f"🔌 [SOURCES] Found {len(data)} inputs"))
    client.register_applist_callback(lambda data: print(f"📱 [APPS] Found {len(data)} installed apps"))
    client.register_disconnected_callback(lambda: print("⚠️ [DISCONNECTED] TV disconnected"))

    client.connect_and_run()
    print("Listening for TV events (Press Ctrl+C to stop)...")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        client.disconnect()


def do_refresh(creds: dict, certfile: str | None, keyfile: str | None, save_path: str, ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    ip = creds.get("ip_address")
    print(f"\n[REFRESH] Testing synchronous token refresh against TV at {ip}...")

    client = create_client_from_creds(creds, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl)
    success = client.check_and_refresh_token(force=True)
    if success:
        print("✅ Token refreshed successfully!")
        print(f"  • New Access Token:  {client.access_token}")
        print(f"  • Issued At:         {time.ctime(client.access_token_time)}")
        creds["accesstoken"] = client.access_token
        creds["accesstoken_time"] = client.access_token_time
        creds["refreshtoken"] = client.refresh_token
        creds["refreshtoken_time"] = client.refresh_token_time
        save_credentials_file(save_path, creds)
    else:
        print("❌ Token refresh failed. Check TV connectivity and broker logs.")


def do_send_key(creds: dict, key_name: str, certfile: str | None, keyfile: str | None, ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    ip = creds.get("ip_address")
    print(f"\n[KEY] Sending key '{key_name}' to TV at {ip}...")

    client = create_client_from_creds(creds, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl)
    client.connect_and_run()
    for _ in range(30):
        if client.connected:
            break
        time.sleep(0.1)

    if client.connected:
        client.send_key(key_name)
        print(f"✅ Sent '{key_name}' successfully.")
        time.sleep(0.5)
    else:
        print("❌ Could not connect to TV to send key.")

    client.disconnect()


def do_launch_app(creds: dict, app_name: str, app_id: str | None = None, app_url: str | None = None, certfile: str | None = None, keyfile: str | None = None, ca_cert: str | None = None, verify_ssl: bool = False) -> None:
    ip = creds.get("ip_address")
    print(f"\n[APP] Launching application '{app_name or app_id}' on TV at {ip}...")

    client = create_client_from_creds(creds, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl)
    client.connect_and_run()
    for _ in range(30):
        if client.connected:
            break
        time.sleep(0.1)

    if client.connected:
        client.launch_app(app_id=app_id or "", app_name=app_name or "", url=app_url or "")
        print(f"✅ Sent launch command for '{app_name or app_id}' (url: {app_url or 'default'}).")
        time.sleep(0.5)
    else:
        print("❌ Could not connect to TV to launch app.")

    client.disconnect()


def do_wake(ip: str, mac: str) -> None:
    print(f"\n[WOL] Sending Wake-on-LAN magic packet to {mac} (Target IP: {ip})...")
    success = HisenseTvClient.send_wake_on_lan(mac=mac, ip=ip)
    if success:
        print(f"✅ Wake-on-LAN magic packet successfully broadcast for MAC {mac}.")
    else:
        print(f"❌ Failed to send Wake-on-LAN packet for MAC {mac}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hisense VIDAA Integration CLI Test Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Generate Markdown diagnostics report for GitHub issues:
  python3 test_client.py report --ip 192.168.50.12 --probe

  # Probe picture/sound menu capabilities and dynamic options:
  python3 test_client.py probe --ip 192.168.50.12

  # Quick 3-tier connectivity & MQTT broker listening probe:
  python3 test_client.py ping --ip 192.168.50.12

  # Test raw SSL/TLS certificate connection to TV:
  python3 test_client.py test-ssl --ip 192.168.50.12

  # Pair with TV and save credentials:
  python3 test_client.py auth --ip 192.168.50.12

  # Listen for real-time status and state updates:
  python3 test_client.py listen

  # Send a remote key (e.g. KEY_POWER, KEY_VOLUMEUP, KEY_HOME, KEY_AUDIO):
  python3 test_client.py send-key KEY_POWER

  # Launch an app on the TV:
  python3 test_client.py launch-app "Netflix"

  # Send Wake-on-LAN magic packet:
  python3 test_client.py wake --mac E8:51:77:EC:98:1C --ip 192.168.50.12
""",
    )

    parser.add_argument(
        "action",
        choices=["ping", "report", "probe", "probe-features", "test-ssl", "auth", "listen", "refresh", "send-key", "launch-app", "wake"],
        help="Action to perform",
    )
    parser.add_argument("key", nargs="?", help="Key name (for send-key) or App name (for launch-app)")
    parser.add_argument("--ip", help="IP address of the TV (required for ping/report/probe/test-ssl/auth/wake if not in config)")
    parser.add_argument("--mac", help="MAC address of the TV")
    parser.add_argument("--profile", choices=["auto", "modern", "remotenow", "legacy", "vidaa_2024", "remotenow_2018"], default="auto", help="Authentication profile and cert selector (default: auto)")
    parser.add_argument("--cert", help="Path to custom client certificate file (e.g. cert.pem)")
    parser.add_argument("--key", dest="key_file", help="Path to custom client private key file (e.g. key.pem)")
    parser.add_argument("--p12", help="Path to PKCS#12 certificate archive (e.g. client_mobile_android.p12)")
    parser.add_argument("--ca", "--ca-cert", dest="ca_cert", help="Path to custom root CA certificate (e.g. remote_ca.pem)")
    parser.add_argument("--verify-ssl", action="store_true", help="Enable strict TLS server certificate verification")
    parser.add_argument("--probe", action="store_true", help="Include active feature & menu tree probing in markdown report")
    parser.add_argument("--app-id", help="App ID for launch-app action")
    parser.add_argument("--url", help="Deep link URL for launch-app action (e.g. netflix://)")
    parser.add_argument("--config", default=DEFAULT_CREDS_FILE, help=f"Path to credentials file (default: {DEFAULT_CREDS_FILE})")
    parser.add_argument("-v", "--debug", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    cert_path = args.p12 or args.cert
    creds = load_credentials_file(args.config)

    if args.action == "ping":
        ip = args.ip or (creds.get("ip_address") if creds else None)
        if not ip:
            print("Error: --ip <IP> is required for 'ping' action (or valid credentials.json).")
            sys.exit(1)
        do_ping(ip, creds, cert_path, args.key_file, profile=args.profile, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl)

    elif args.action in ("probe", "probe-features"):
        ip = args.ip or (creds.get("ip_address") if creds else None)
        if not ip:
            print("Error: --ip <IP> is required for 'probe' action (or valid credentials.json).")
            sys.exit(1)
        do_probe(ip, creds, cert_path, args.key_file, profile=args.profile, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl)

    elif args.action == "report":
        ip = args.ip or (creds.get("ip_address") if creds else None)
        if not ip:
            print("Error: --ip <IP> is required for 'report' action (or valid credentials.json).")
            sys.exit(1)
        do_report(ip, args.mac, creds, cert_path, args.key_file, profile=args.profile, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl, probe=args.probe)

    elif args.action == "test-ssl":
        if not args.ip:
            print("Error: --ip <IP> is required for 'test-ssl' action.")
            sys.exit(1)
        do_test_ssl(args.ip, cert_path, args.key_file, profile=args.profile, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl)

    elif args.action == "auth":
        if not args.ip:
            print("Error: --ip <IP> is required for 'auth' action.")
            sys.exit(1)
        asyncio.run(do_auth(args.ip, args.mac, cert_path, args.key_file, args.config, profile=args.profile, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl))

    elif args.action == "listen":
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        asyncio.run(do_listen(creds, cert_path, args.key_file, args.config, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl))

    elif args.action == "refresh":
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        do_refresh(creds, cert_path, args.key_file, args.config, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl)

    elif args.action == "send-key":
        if not args.key:
            print("Error: Specify key name to send, e.g. python3 test_client.py send-key KEY_POWER")
            sys.exit(1)
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        do_send_key(creds, args.key, cert_path, args.key_file, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl)

    elif args.action == "launch-app":
        app_name = args.key
        if not app_name and not args.app_id:
            print("Error: Specify app name or --app-id to launch, e.g. python3 test_client.py launch-app 'Netflix'")
            sys.exit(1)
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        do_launch_app(creds, app_name, app_id=args.app_id, app_url=args.url, certfile=cert_path, keyfile=args.key_file, ca_cert=args.ca_cert, verify_ssl=args.verify_ssl)

    elif args.action == "wake":
        ip = args.ip or creds.get("ip_address")
        mac = args.mac or creds.get("mac_address")
        if not mac and ip:
            mac = get_arp_mac(ip)
        if not mac:
            print("Error: --mac <MAC> (or valid IP with ARP cache entry) is required for 'wake' action.")
            sys.exit(1)
        do_wake(ip, mac)


if __name__ == "__main__":
    main()
