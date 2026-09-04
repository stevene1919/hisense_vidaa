#!/usr/bin/env python3
"""
Hisense VIDAA Integration CLI Test Script
Allows direct testing and debugging of authentication, pairing PIN, token refreshes,
and command execution using the exact same HisenseTvClient logic as the Home Assistant integration.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

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
    with open(file_path) as f:
        return json.load(f)


def save_credentials(file_path, creds):
    with open(file_path, "w") as f:
        json.dump(creds, f, indent=4)
    print(f"Credentials successfully saved to '{file_path}'")


def do_ping(ip, creds, certfile, keyfile):
    print(f"\n[PING] Probing TV connectivity and MQTT broker at {ip}:36669...")

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
        keyfile=keyfile
    )

    try:
        res = client.ping()
        print("\n📡 Connection Probe Results:")
        print(f"  • [1] TCP Port 36669:    {'✅ OPEN' if res['tcp_port_open'] else '❌ CLOSED / UNREACHABLE'}")
        print(f"  • [2] TLS Handshake:     {'✅ SUCCESS' if res['tls_handshake'] else '❌ FAILED'} ({res.get('tls_version') or 'N/A'}, {res.get('cipher') or 'N/A'})")

        if res.get("mqtt_rc") is not None:
            if res["mqtt_connected"]:
                print("  • [3] MQTT Broker Auth:  ✅ ACCEPTED (rc=0, broker is actively listening and responsive)")
            else:
                print(f"  • [3] MQTT Broker Auth:  ⚠️ {res['mqtt_status']}")
        else:
            print(f"  • [3] MQTT Broker State: ℹ️ {res['mqtt_status']}")

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


def do_test_ssl(ip, certfile, keyfile):
    print(f"\n[SSL] Testing raw TLS connection to Hisense TV at {ip}:36669...")
    client = HisenseTvClient(ip=ip, certfile=certfile, keyfile=keyfile)
    try:
        res = client.test_ssl_connection()
        print("\n✅ TLS Connection Successful!")
        print(f"  • TV Address:    {ip}:36669")
        print(f"  • TLS Version:   {res['tls_version']}")
        print(f"  • Cipher Suite:  {res['cipher']} ({res['bits']} bits)")
        print(f"  • Certificate:   {res['certfile']}")
        print(f"  • Private Key:   {res['keyfile']}")
        print("\n💡 The provided certificate and key negotiate SSL properly with the TV broker.")
    except FileNotFoundError as e:
        print(f"\n❌ Certificate Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TLS Connection Failed: {e}")
        print("\n💡 Hint: Check that the TV is powered ON and that the IP address and certificates are correct.")
        sys.exit(1)


async def do_auth(ip, mac, certfile, keyfile, save_path):
    print(f"\n[AUTH] Connecting to Hisense TV at {ip} on port 36669 (TLS)...")
    client = HisenseTvClient(ip=ip, mac=mac, certfile=certfile, keyfile=keyfile)
    try:
        await client.async_start_auth()
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

        save_credentials(save_path, creds)
    except FileNotFoundError as e:
        print(f"\n❌ Certificate Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        if "timeout" in str(e).lower() or "unreachable" in str(e).lower() or "connection rejected" in str(e).lower():
            print("\n💡 Hint: Ensure your TV is actively powered ON with the remote and connected to your network.")
        sys.exit(1)


async def do_listen(creds, certfile, keyfile, save_path):
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
        certfile=certfile,
        keyfile=keyfile,
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


def do_refresh(creds, certfile, keyfile, save_path):
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
        certfile=certfile,
        keyfile=keyfile,
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


def do_send_key(creds, key_name, certfile, keyfile):
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
        certfile=certfile,
        keyfile=keyfile,
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
  # Quick 3-tier connectivity & MQTT broker listening probe:
  python3 test_client.py ping --ip 192.168.50.12

  # Test raw SSL/TLS certificate connection to TV:
  python3 test_client.py test-ssl --ip 192.168.50.12

  # Test custom certificate files:
  python3 test_client.py test-ssl --ip 192.168.50.12 --cert /path/to/cert.pem --key /path/to/key.pem

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

    parser.add_argument("action", choices=["ping", "test-ssl", "auth", "listen", "refresh", "send-key"], help="Action to perform")
    parser.add_argument("key", nargs="?", help="Key to send (for send-key action, e.g. KEY_POWER, KEY_VOLUMEUP)")
    parser.add_argument("--ip", help="IP address of the TV (required for ping/test-ssl/auth if not in config)")
    parser.add_argument("--mac", help="MAC address of the TV")
    parser.add_argument("--cert", help="Path to custom client certificate file (e.g. cert.pem)")
    parser.add_argument("--key", dest="key_file", help="Path to custom client private key file (e.g. key.pem)")
    parser.add_argument("--config", default=DEFAULT_CREDS_FILE, help=f"Path to credentials file (default: {DEFAULT_CREDS_FILE})")
    parser.add_argument("-v", "--debug", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if args.action == "ping":
        creds = None
        if os.path.exists(args.config):
            try:
                with open(args.config) as f:
                    creds = json.load(f)
            except Exception:
                pass
        ip = args.ip or (creds.get("ip_address") if creds else None)
        if not ip:
            print("Error: --ip <IP> is required for 'ping' action (or valid credentials.json).")
            sys.exit(1)
        do_ping(ip, creds, args.cert, args.key_file)

    elif args.action == "test-ssl":
        if not args.ip:
            print("Error: --ip <IP> is required for 'test-ssl' action.")
            sys.exit(1)
        do_test_ssl(args.ip, args.cert, args.key_file)

    elif args.action == "auth":
        if not args.ip:
            print("Error: --ip <IP> is required for 'auth' action.")
            sys.exit(1)
        asyncio.run(do_auth(args.ip, args.mac, args.cert, args.key_file, args.config))

    elif args.action == "listen":
        creds = load_credentials(args.config)
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        asyncio.run(do_listen(creds, args.cert, args.key_file, args.config))

    elif args.action == "refresh":
        creds = load_credentials(args.config)
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        do_refresh(creds, args.cert, args.key_file, args.config)

    elif args.action == "send-key":
        if not args.key:
            print("Error: Specify key name to send, e.g. python3 test_client.py send-key KEY_POWER")
            sys.exit(1)
        creds = load_credentials(args.config)
        ip = args.ip or creds.get("ip_address")
        creds["ip_address"] = ip
        do_send_key(creds, args.key, args.cert, args.key_file)


if __name__ == "__main__":
    main()
