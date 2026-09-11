#!/usr/bin/env python3
"""Hisense VIDAA TV - Diagnostic and Live Debugging Tool.

Usage:
  python3 debug_tv.py [--ip <IP>] [--monitor] [--dump-state] [--send-key <KEY>] [--launch-app <APP>] [--change-source <SRC>] [--sync-clock]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

# Setup module import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_components", "hisense_vidaa"))

from client import HisenseTvClient
from discovery import get_device_fingerprint, get_tv_timestamp


def setup_logger(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("hisense_debug")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.handlers = [handler]
    return logger


def load_credentials(creds_path: str = "credentials.json") -> dict:
    if os.path.isfile(creds_path):
        try:
            with open(creds_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def print_section(title: str) -> None:
    print(f"\n{'=' * 65}\n  {title}\n{'=' * 65}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hisense VIDAA TV Diagnostic and Live Debugging Tool")
    parser.add_argument("--ip", type=str, default=None, help="TV IP Address (default: from credentials.json or 192.168.50.12)")
    parser.add_argument("--creds", type=str, default="credentials.json", help="Path to credentials.json")
    parser.add_argument("--cert", type=str, default=None, help="Path to client certificate pem")
    parser.add_argument("--key", type=str, default=None, help="Path to client private key pem")
    parser.add_argument("--monitor", action="store_true", help="Continuously monitor and stream live TV MQTT events")
    parser.add_argument("--dump-state", action="store_true", help="Dump all current state, apps, sources, and volume")
    parser.add_argument("--send-key", type=str, default=None, help="Send a keypress command (e.g. KEY_HOME, KEY_VOLUMEUP)")
    parser.add_argument("--launch-app", type=str, default=None, help="Launch an app by name or App ID (e.g. Netflix, YouTube)")
    parser.add_argument("--change-source", type=str, default=None, help="Change active input source (e.g. HDMI1, HDMI2, TV)")
    parser.add_argument("--sync-clock", action="store_true", help="Inspect UPnP Date header and calculate TV clock drift")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()
    _logger = setup_logger(args.verbose)

    # 1. Load credentials
    creds = load_credentials(args.creds)
    tv_ip = args.ip or creds.get("ip_address") or "192.168.50.12"
    mac = creds.get("mac_address")
    client_id = creds.get("client_id")
    username = creds.get("username")
    password = creds.get("password")
    access_token = creds.get("accesstoken")

    print_section("1. Network & Device Discovery Diagnostics")
    print(f"Target TV IP:  {tv_ip}")
    print(f"Credentials:   {'Found (' + args.creds + ')' if client_id else 'None (using discovery credentials)'}")

    # 2. UPnP / mDNS Fingerprint
    print("\nProbing UPnP Device Description & mDNS...")
    try:
        fp = get_device_fingerprint(tv_ip, timeout=2.0)
        print(f"  - Friendly Name:     {fp.get('friendly_name') or 'N/A'}")
        print(f"  - Model Name:        {fp.get('model_name') or 'N/A'}")
        print(f"  - Model Number:      {fp.get('model_number') or 'N/A'}")
        print(f"  - Manufacturer:      {fp.get('manufacturer') or 'N/A'}")
        print(f"  - Platform:          {fp.get('platform') or 'N/A'}")
        print(f"  - Firmware Version:  {fp.get('firmware_version') or 'N/A'}")
        print(f"  - Wi-Fi MAC:         {fp.get('mac_wifi') or 'N/A'}")
        print(f"  - Ethernet MAC:      {fp.get('mac_ethernet') or 'N/A'}")
    except Exception as e:
        print(f"  [!] UPnP discovery error: {e}")

    # 3. TV Clock & NTP Drift
    print("\nProbing TV Hardware Clock (UPnP Port 38400)...")
    tv_ts = get_tv_timestamp(tv_ip, timeout=2.0)
    now_ts = int(time.time())
    if tv_ts:
        drift = tv_ts - now_ts
        tv_dt = datetime.fromtimestamp(tv_ts, tz=UTC)
        print(f"  - TV Timestamp:      {tv_ts} ({tv_dt.strftime('%Y-%m-%d %H:%M:%S UTC')})")
        print(f"  - System Timestamp:  {now_ts} ({datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')})")
        print(f"  - Clock Drift:       {drift:+} seconds ({'Synchronized' if abs(drift) < 60 else 'WARNING: Out of sync!'})")
    else:
        print("  [!] TV Clock query returned no timestamp (Port 38400 unreachable or Date header missing)")

    # 4. Initialize Client & Connect
    print_section("2. MQTT Broker & Real-Time Protocol Diagnostics")
    client = HisenseTvClient(
        ip=tv_ip,
        mac=mac,
        client_id=client_id,
        username=username,
        password=password,
        access_token=access_token,
        certfile=args.cert,
        keyfile=args.key,
        auth_profile="auto",
    )

    state_cache = {"state": {}, "volume": {}, "sources": [], "apps": []}

    def on_state(data: dict) -> None:
        state_cache["state"] = data
        statetype = data.get("statetype")
        source = data.get("sourcename") or data.get("displayname") or data.get("sourceid")
        app = data.get("name") or data.get("appName") or data.get("appId")
        print(f"[EVENT: STATE] Type: {statetype} | Source: {source} | App: {app} | Raw: {data}")

    def on_volume(data: dict) -> None:
        state_cache["volume"] = data
        v_val = data.get("volume_value")
        v_type = "Master" if data.get("volume_type") == 0 else "Mute" if data.get("volume_type") == 2 else f"Type {data.get('volume_type')}"
        print(f"[EVENT: VOLUME] {v_type} -> {v_val} | Raw: {data}")

    def on_sources(data: list) -> None:
        state_cache["sources"] = data
        active = [s.get("sourcename") for s in data if s.get("is_signal") in ("1", 1, True) or s.get("is_active")]
        print(f"[EVENT: SOURCES] Total Sources: {len(data)} | Active Input: {active[0] if active else 'None'}")

    def on_apps(data: list) -> None:
        state_cache["apps"] = data
        print(f"[EVENT: APPS] Total Apps Installed: {len(data)}")

    client.register_state_callback(on_state)
    client.register_volume_callback(on_volume)
    client.register_sourcelist_callback(on_sources)
    client.register_applist_callback(on_apps)
    client.register_connected_callback(lambda: print("[EVENT: MQTT] Successfully connected to TV broker!"))
    client.register_disconnected_callback(lambda: print("[EVENT: MQTT] Disconnected from TV broker!"))

    print(f"Connecting to TV broker at {tv_ip}:36669 (TLS)...")
    try:
        client.connect_and_run()
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        return

    # Wait for connection
    for _ in range(30):
        if client.connected:
            break
        time.sleep(0.1)

    if not client.connected:
        print("[!] Timed out waiting for MQTT connection to establish.")
        client.disconnect()
        return

    # Query initial state
    print("\nQuerying initial TV state, sources, volume, and apps...")
    client.query_initial_state()
    time.sleep(2.0)

    # Handle requested actions
    if args.send_key:
        print(f"\nSending Keypress: '{args.send_key}'...")
        client.send_key(args.send_key)
        time.sleep(0.5)

    if args.launch_app:
        print(f"\nLaunching App: '{args.launch_app}'...")
        matched_app = None
        for a in state_cache["apps"]:
            if (a.get("name") or "").lower() == args.launch_app.lower() or str(a.get("appId")) == args.launch_app:
                matched_app = a
                break
        if matched_app:
            client.launch_app(matched_app["appId"], matched_app.get("name", args.launch_app), matched_app.get("url", ""))
            print(f"  [+] Launched {matched_app.get('name')} (AppId: {matched_app.get('appId')})")
        else:
            print(f"  [-] App '{args.launch_app}' not found in installed apps. Sending raw launch command...")
            client.launch_app(args.launch_app, args.launch_app, "")
        time.sleep(1.0)

    if args.change_source:
        print(f"\nChanging Source: '{args.change_source}'...")
        client.change_source(args.change_source)
        time.sleep(1.0)

    if args.dump_state or not (args.monitor or args.send_key or args.launch_app or args.change_source):
        print_section("3. Current TV State Snapshot")
        print(f"MQTT Connected:      {client.connected}")
        print(f"Auth Profile:        {client.auth_profile}")
        if client.access_token_time and client.access_token_duration:
            exp_dt = datetime.fromtimestamp(client.access_token_time + client.access_token_duration * 86400, tz=UTC)
            print(f"Access Token Expiry: {exp_dt}")
        else:
            print("Access Token Expiry: N/A")

        # Sources
        print(f"\nInstalled Sources ({len(state_cache['sources'])}):")
        for s in state_cache["sources"]:
            active_marker = " [ACTIVE]" if s.get("is_signal") in ("1", 1, True) or s.get("is_active") else ""
            print(f"  - {s.get('sourcename', 'Unknown')} (ID: {s.get('sourceid')}){active_marker}")

        # Apps Summary
        print(f"\nInstalled Apps ({len(state_cache['apps'])}):")
        app_names = [a.get("name") for a in state_cache["apps"] if a.get("name")]
        print("  " + ", ".join(sorted(app_names)[:15]) + ("..." if len(app_names) > 15 else ""))

    if args.monitor:
        print_section("4. Live Event Monitor (Press Ctrl+C to Stop)")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nStopping live monitor...")

    client.disconnect()
    print("\nDiagnostic run complete.")


if __name__ == "__main__":
    main()
