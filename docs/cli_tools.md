# 🧪 Standalone CLI Testing & Diagnostic Tools

The integration includes two standalone Python CLI utilities that share 100% of the backend logic with the Home Assistant integration (`client.py`, `crypto.py`, `discovery.py`). These tools require no mocking and communicate directly with real TVs.

---

## 🔬 `test_client.py` — Auth Probe & Pairing Tool

[`test_client.py`](../test_client.py) focuses on **initial discovery, SSL validation, authentication, and diagnostic reporting**.

### 1. Generate GitHub Issue Diagnostic Report (`report`)
Generates a sanitized Markdown diagnostics block detailing hardware info, firmware version, and multi-tier authentication support ready to paste into GitHub issues:
```bash
python3 test_client.py report --ip <TV_IP>
```

### 2. Diagnostic Probe & Firmware Detection (`ping`)
Tests TCP port reachability, TLS handshake, broker response, and multi-tier auth capabilities:
```bash
python3 test_client.py ping --ip <TV_IP>

# Test specific authentication profile:
python3 test_client.py ping --ip <TV_IP> --profile modern
```

### 3. Test Raw SSL/TLS Connection (`test-ssl`)
Verifies TLS cipher negotiation and certificate validity without pairing:
```bash
python3 test_client.py test-ssl --ip <TV_IP>
python3 test_client.py test-ssl --ip <TV_IP> --profile modern
python3 test_client.py test-ssl --ip <TV_IP> --cert /path/to/cert.pem --key /path/to/key.pem
```

### 4. Interactive PIN Pairing (`auth`)
Initiates the challenge handshake, displays the on-screen 4-digit PIN on the TV, and saves the issued tokens to `credentials.json`:
```bash
python3 test_client.py auth --ip <TV_IP>
python3 test_client.py auth --ip <TV_IP> --profile modern
```

### 5. Test Token Renewal (`refresh`)
Tests renewal of the 2-day access token using the 30-day refresh token:
```bash
python3 test_client.py refresh
```

### 6. Listen to Real-Time TV Events (`listen`)
Subscribes to live state changes, volume updates, source list, and app list:
```bash
python3 test_client.py listen
```

### 7. Send Remote Key Command (`send-key`)
Dispatches a single key command:
```bash
python3 test_client.py send-key KEY_VOLUMEUP
python3 test_client.py send-key KEY_POWER
```

### 8. Wake-on-LAN Broadcast (`wake`)
Broadcasts a subnet-directed magic packet:
```bash
python3 test_client.py wake --mac E8:51:77:EC:98:1C
```

---

## 🛠️ `debug_tv.py` — Live Runtime Debugger

[`debug_tv.py`](../debug_tv.py) focuses on **live state inspection, real-time event monitoring, and manual command dispatching**. It automatically loads existing credentials from `credentials.json`.

```bash
# Dump current state, sources, apps, and volume:
python3 debug_tv.py --dump-state

# Continuously stream live MQTT events from the TV:
python3 debug_tv.py --monitor

# Send a remote keypress:
python3 debug_tv.py --send-key KEY_HOME
python3 debug_tv.py --send-key KEY_VOLUMEUP

# Launch an app by name or App ID:
python3 debug_tv.py --launch-app Netflix
python3 debug_tv.py --launch-app "Disney+"

# Switch input source:
python3 debug_tv.py --change-source HDMI1
python3 debug_tv.py --change-source TV

# Inspect UPnP Date header and calculate TV clock drift:
python3 debug_tv.py --sync-clock

# Override TV IP:
python3 debug_tv.py --ip 192.168.50.12 --monitor

# Verbose debug logging:
python3 debug_tv.py --dump-state -v
```

> [!TIP]
> Running `python3 debug_tv.py` with no arguments produces a complete state dump (`--dump-state`).
