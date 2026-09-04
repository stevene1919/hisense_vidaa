# Hisense VIDAA TV Integration for Home Assistant

A custom Home Assistant integration for Hisense TVs running modern VIDAA OS.

This integration connects **directly** to the TV's internal MQTT broker (SSL port `36669`) using client certificates, without requiring external Mosquitto bridges or system-level configuration.

## 🧭 Which Integration Should You Use?

Hisense changed the MQTT authentication model across firmware revisions:

| TV Firmware / Model | MQTT Authentication Model | Recommended Integration |
| :--- | :--- | :--- |
| **Modern VIDAA OS (VIDAA U5, U6, U7, 2022+)** | **Dynamic PIN Pairing** (`actions/vidaa_app_connect`) | **👉 This Integration (`hisense_vidaa`)** |
| **Legacy Hisense / Older VIDAA (Pre-2022)** | **Static Credentials** (`hisenseservice` / `multimqttservice`) | [alexmohr/ha_hisense_tv](https://github.com/alexmohr/ha_hisense_tv) or [sehaas/hisensetv](https://github.com/sehaas/hisensetv) |

> [!TIP]
> Not sure which firmware your TV has? Run the built-in diagnostic probe:
> ```bash
> python3 test_client.py ping --ip <YOUR_TV_IP>
> ```
> The tool will automatically test if your TV accepts legacy static logins or enforces modern dynamic pairing and recommend the right integration.

---

## ✨ Features

- **Direct Secure Connection**: Native SSL communication directly to port `36669`.
- **Dynamic PIN Pairing**: Automated challenge-response pairing flow in the Home Assistant UI.
- **Standby Power Control**: Power on/off the TV using secure MQTT keys.
- **Media Player Entity**:
  - Power toggle and standby control.
  - Volume adjustment, stepping, and mute toggle.
  - Unified input source selector (HDMI, TV, AV inputs, and installed VIDAA apps).
  - Instant local push updates for volume and power state.
- **Robust Connection Handlers**:
  - Non-blocking startup ensures Home Assistant boots cleanly even when the TV is powered off.
  - Mutex locks and rate limits to prevent background thread storms during network disconnects.
  - Automatic background token refresh when 2-day session tokens expire.
  - Refreshed tokens are dynamically persisted to Config Entry to survive restarts.
- **Zero-Duplication CLI Diagnostic Tool**: Built-in test suite (`test_client.py`) sharing 100% of its backend logic with the Home Assistant integration code.

---

## 🌐 Important Network Requirement

> [!IMPORTANT]
> **Internet Connectivity Required**: The TV **must have active internet connectivity and unblocked DNS resolution** for pairing, token exchange, and token refresh to succeed.
> 
> If the TV is isolated on an offline IoT VLAN or blocked by network-level ad blockers / firewalls (e.g., AdGuard Home, Pi-hole), VIDAA OS will refuse to complete the pairing handshake or refresh tokens. We are investigating the exact cloud endpoints and domains required so specific whitelist rules can be documented in the future, but in the meantime, ensure the TV has outbound WAN access.

---

## 🔒 SSL Certificate Setup

VIDAA OS requires a client SSL certificate and private key to communicate with port `36669`. Certificates are excluded from this repository and must be provided locally.

1. Create a `certs/` directory inside `custom_components/hisense_vidaa/` (or place them in `/config/certs/` / `/config/ssl/`).
2. Place your certificate and private key files:
   ```text
   custom_components/hisense_vidaa/certs/cert.pem
   custom_components/hisense_vidaa/certs/key.pem
   ```

---

## 🧪 Testing & Diagnostics (`test_client.py`)

The integration includes a standalone CLI test utility [`test_client.py`](test_client.py) that imports and executes the exact same [`HisenseTvClient`](client.py) logic used by Home Assistant.

### 1. Diagnostic Probe & Firmware Detection (`ping`)
Tests TCP port reachability, TLS handshake, broker response, and suggests which integration style your TV firmware requires:
```bash
python3 test_client.py ping --ip <TV_IP>
```

### 2. Test Raw SSL/TLS Connection & Cert Validity (`test-ssl`)
Verifies TLS cipher negotiation and certificate validity with the TV without initiating pairing:
```bash
# Using default certs/ folder:
python3 test_client.py test-ssl --ip <TV_IP>

# Using custom certificate locations:
python3 test_client.py test-ssl --ip <TV_IP> --cert /path/to/cert.pem --key /path/to/key.pem
```

### 3. Test Pairing & Retrieve Tokens (`auth`)
Initiates the challenge handshake, prompts for the 4-digit TV on-screen PIN, and saves tokens to `credentials.json`:
```bash
python3 test_client.py auth --ip <TV_IP>
```

### 4. Test Token Refresh (`refresh`)
Tests synchronous renewal of the 2-day access token using the 30-day refresh token:
```bash
python3 test_client.py refresh
```

### 5. Listen to Real-Time TV Events (`listen`)
Subscribes to live state changes, volume updates, source list, and app list:
```bash
python3 test_client.py listen
```

### 6. Send Remote Control Keys (`send-key`)
Dispatches a keypress directly to the TV:
```bash
python3 test_client.py send-key KEY_VOLUMEUP
python3 test_client.py send-key KEY_POWER
```

---

## ⚙️ Installation & Home Assistant Setup

1. Copy the `hisense_vidaa` directory to your Home Assistant `custom_components/` directory (e.g. `/config/custom_components/hisense_vidaa`).
2. Place `cert.pem` and `key.pem` inside `custom_components/hisense_vidaa/certs/`.
3. Restart Home Assistant.
4. Go to **Settings -> Devices & Services -> Add Integration** and search for **Hisense VIDAA TV**.
5. Enter the TV's IP address (the hardware MAC address is automatically discovered via ARP and linked to Home Assistant).
6. Enter the 4-digit PIN code displayed on the TV screen to complete the setup.

> [!IMPORTANT]
> **Network Requirement**: VIDAA OS requires DNS / internet access on the TV during initial pairing to validate authentication tokens. Ensure the TV is not blocked from internet/DNS access on your local gateway.

---

## 🔗 Legacy Firmware Alternatives & Related Projects

If your TV accepts static credentials or you are running older Hisense hardware:

* **[alexmohr/ha_hisense_tv](https://github.com/alexmohr/ha_hisense_tv)**: Home Assistant custom component for older firmware supporting static MQTT credentials.
* **[sehaas/hisensetv](https://github.com/sehaas/hisensetv)**: Python library and command-line tool for older static-credential Hisense TVs.
* **[Krazy998/mqtt-hisensetv](https://github.com/Krazy998/mqtt-hisensetv)**: Docker MQTT broker bridge for legacy models.

---

## Credits & Acknowledgments

This native integration adapts foundational reverse-engineering discoveries from the open-source community:

* **Nika Gerson Lohman ([@nikagl](https://github.com/nikagl))**: For creating the original `hisense.py` script architecture and proving the RemoteNOW-style dynamic PIN authentication flow.
* **[@Krazy998](https://github.com/Krazy998) & Contributors**: For collaborative research on the `mqtt-hisensetv` project decoding VIDAA OS MQTT communication.
