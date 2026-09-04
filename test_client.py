#!/usr/bin/env python3
"""
Hisense VIDAA Integration CLI Test Script
Allows direct testing and debugging of authentication, pairing PIN, token refreshes,
and command execution using the exact same HisenseTvClient logic as the Home Assistant integration.
"""

import sys
import os
import time
import json
import asyncio
import logging
import argparse

# Ensure local custom_components/hisense_vidaa directory is in Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from client import HisenseTvClient

DEFAULT_CREDS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")


def load_credentials(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Credentials file '{file_path}' not found. Run 'auth' first or specify credentials.")
        sys.exit(1)
    with open(file_path, "r") as f:
        return json.load(f)


def save_credentials(file_path, creds):
    with open(file_path, "w") as f:
        json.dump(creds, f, indent=4)
    print(f"Credentials successfully saved to '{file_path}'")


async def do_auth(ip, mac, save_path):
    print(f"\n[AUTH] Connecting to Hisense TV at {ip} on port 36669 (TLS)...")
    client = HisenseTvClient(ip=ip, mac=mac)
    try:
        await client.async_start_auth()
        print("\n✅ Initial connection established!")
        print("📺 Look at your TV screen. A 4-digit PIN should now be visible.")
        pin = input("👉 Enter the 4-digit PIN: ").strip()

        print(f"\n[AUTH] Submitting PIN '{pin}' and requesting tokens...")
        token_data = await client.async_submit_pin(pin)

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

        save_credentials(save_path, creds)
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)


async def do_listen(creds, save_path):
    ip = creds.get("ip_address")
    print(f"\n[LISTEN] Connecting to TV at {ip} with stored credentials...")

    client = HisenseTvClient(
        ip=ip,
        mac=creds.get("mac_address"),
        client_id=creds.get("client_id"),
        username=creds.get("username"),
        password=creds.get("password"),
        access_token=creds.get("accesstoken") or creds.get("access_token"),
        access_token_time=int(creds.get("accesstoken_time") or creds.get("access_token_time", 0)),
        access_token_duration=int(creds.get("accesstoken_duration_day") or creds.get("access_token_duration", 2)),
        refresh_token=creds.get("refreshtoken") or creds.get("refresh_token"),
        refresh_token_time=int(creds.get("refreshtoken_time") or creds.get("refresh_token_time", 0)),
        refresh_token_duration=int(creds.get("refreshtoken_duration_day") or creds.get("refresh_token_duration", 30)),
    )

    def on_token_refreshed(c):
        print(f"\n🔄 [TOKEN REFRESHED] New access token: {c.access_token[:15]}...")
        creds["accesstoken"] = c.access_token
        creds["accesstoken_time"] = c.access_token_time
        creds["refreshtoken"] = c.refresh_token
        creds["refreshtoken_time"] = c.refresh_token_time
        save_credentials(save_path, creds)

    client.on_token_refreshed = on_token_refreshed
    client.on_state_update = lambda data: print(f"📡 [STATE] {json.dumps(data)}")
    client.on_volume_update = lambda data: print(f"🔊 [VOLUME] {json.dumps(data)}")
    client.on_sourcelist_update = lambda data: print(f"🔌 [SOURCES] Found {len(data)} inputs")
    client.on_applist_update = lambda data: print(f"📱 [APPS] Found {len(data)} installed apps")
    client.on_disconnected_callback = lambda: print("⚠️ [DISCONNECTED] TV disconnected")

    client.connect_and_run()
    print("Listening for TV events (Press Ctrl+C to stop)...")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        client.disconnect()


def do_refresh(creds, save_path):
    ip = creds.get("ip_address")
    print(f"\n[REFRESH] Testing synchronous token refresh against TV at {ip}...")

    client = HisenseTvClient(
        ip=ip,
        mac=creds.get("mac_address"),
        client_id=creds.get("client_id"),
        username=creds.get("username"),
        password=creds.get("password"),
        access_token=creds.get("accesstoken") or creds.get("access_token"),
        access_token_time=int(creds.get("accesstoken_time") or creds.get("access_token_time", 0)),
        access_token_duration=int(creds.get("accesstoken_duration_day") or creds.get("access_token_duration", 2)),
        refresh_token=creds.get("refreshtoken") or creds.get("refresh_token"),
        refresh_token_time=int(creds.get("refreshtoken_time") or creds.get("refresh_token_time", 0)),
        refresh_token_duration=int(creds.get("refreshtoken_duration_day") or creds.get("refresh_token_duration", 30)),
    )

    success = client.check_and_refresh_token(force=True)
    if success:
        print("✅ Token refreshed successfully!")
        print(f"  • New Access Token:  {client.access_token}")
        print(f"  • Issued At:         {time.ctime(client.access_token_time)}")
        creds["accesstoken"] = client.access_token
        creds["accesstoken_time"] = client.access_token_time
        creds["refreshtoken"] = client.refresh_token
        creds["refreshtoken_time"] = client.refresh_token_time
        save_credentials(save_path, creds)
    else:
        print("❌ Token refresh failed. Check TV connectivity and broker logs.")


def do_send_key(creds, key_name):
    ip = creds.get("ip_address")
    print(f"\n[KEY] Sending key '{key_name}' to TV at {ip}...")

    client = HisenseTvClient(
        ip=ip,
        mac=creds.get("mac_address"),
        client_id=creds.get("client_id"),
        username=creds.get("username"),
        password=creds.get("password"),
        access_token=creds.get("accesstoken") or creds.get("access_token"),
        access_token_time=int(creds.get("accesstoken_time") or creds.get("access_token_time", 0)),
        access_token_duration=int(creds.get("accesstoken_duration_day") or creds.get("access_token_duration", 2)),
        refresh_token=creds.get("refreshtoken") or creds.get("refresh_token"),
        refresh_token_time=int(creds.get("refreshtoken_time") or creds.get("refresh_token_time", 0)),
        refresh_token_duration=int(creds.get("refreshtoken_duration_day") or creds.get("refresh_token_duration", 30)),
    )

    client.connect_and_run()
    # Wait for connection
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


def main():
    parser = argparse.ArgumentParser(
        description="Hisense VIDAA Integration CLI Test Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Pair with TV and save credentials:
  python3 test_client.py auth --ip 192.168.50.12

  # Listen for real-time status and state updates:
  python3 test_client.py listen

  # Test token refresh:
  python3 test_client.py refresh

  # Send a remote key (e.g. KEY_POWER, KEY_VOLUMEUP, KEY_HOME):
  python3 test_client.py send-key KEY_POWER
"""
    )

    parser.add_argument("action", choices=["auth", "listen", "refresh", "send-key"], help="Action to perform")
    parser.add_argument("key", nargs="?", help="Key to send (for send-key action, e.g. KEY_POWER, KEY_VOLUMEUP)")
    parser.add_argument("--ip", help="IP address of the TV (required for auth, optional override for other commands)")
    parser.add_argument("--mac", help="MAC address of the TV")
    parser.add_argument("--config", default=DEFAULT_CREDS_FILE, help=f"Path to credentials file (default: {DEFAULT_CREDS_FILE})")
    parser.add_argument("-v", "--debug", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.action == "auth":
        if not args.ip:
            print("Error: --ip <IP> is required for 'auth' action.")
            sys.exit(1)
        asyncio.run(do_auth(args.ip, args.mac, args.config))

    elif args.action == "listen":
        creds = load_credentials(args.config)
        if args.ip:
            creds["ip_address"] = args.ip
        asyncio.run(do_listen(creds, args.config))

    elif args.action == "refresh":
        creds = load_credentials(args.config)
        if args.ip:
            creds["ip_address"] = args.ip
        do_refresh(creds, args.config)

    elif args.action == "send-key":
        if not args.key:
            print("Error: Specify key name to send, e.g. python3 test_client.py send-key KEY_POWER")
            sys.exit(1)
        creds = load_credentials(args.config)
        if args.ip:
            creds["ip_address"] = args.ip
        do_send_key(creds, args.key)


if __name__ == "__main__":
    main()
