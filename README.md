# Hisense VIDAA TV Integration for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Validate with HACS](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml)
[![Lint & Verify](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

A custom Home Assistant integration for Hisense TVs running modern VIDAA OS.

This integration connects **directly** to the TV's internal MQTT broker (SSL port `36669`) using client certificates, without requiring external Mosquitto bridges or system-level configuration.

## 🧭 Supported Authentication Profiles

This integration automatically detects and natively supports all generations of Hisense smart TVs:

| TV Generation / Firmware | Auth Profile | Authentication Model | Pairing Method |
| :--- | :--- | :--- | :--- |
| **Modern VIDAA OS (2024+ / U7, U8, Q0704+)** | `modern` | **Modern VIDAA 2.0** (`libmqttcrypt` XOR mask) | 4-Digit Screen PIN (`actions/vidaa_app_connect`) |
| **Standard VIDAA OS (2018–2023 / U4, U5, U6)** | `remotenow` | **RemoteNOW Dynamic** (`his$<timestamp>`) | 4-Digit Screen PIN (`actions/vidaa_app_connect`) |
| **Legacy Hisense / Older VIDAA (Pre-2022)** | `legacy` | **Legacy Static** (`hisenseservice`) | Instant Setup (No PIN / Static Credentials) |

> [!TIP]
> **Auto-Detection (`auto`)**: The integration automatically probes your TV's MQTT broker capabilities during setup and selects the optimal authentication handshake for your specific firmware.
>
> You can also run the built-in diagnostic probe from the command line:
> ```bash
> python3 test_client.py ping --ip <YOUR_TV_IP>
> ```

---

## ✨ Features

- **Multi-Generation Authentication**: Native support for Modern VIDAA 2.0 (XOR hashing), Standard RemoteNOW dynamic pairing, and Legacy Static credentials (`hisenseservice`).
- **Flexible Certificate Formats & Auto-Extraction**: Native support for split PEM pairs (`.pem`, `.crt`, `.key`) and direct PKCS#12 keystore archives (`.p12`, `.pfx` e.g. `client_mobile_android.p12`, `rcamobile.p12`) with automatic key/cert extraction.
- **Optional Root CA Validation**: Configurable root CA verification (`ca_cert` / `remote_ca.pem`) with `CERT_NONE` default matching official VIDAA app behavior.
- **Direct Secure Connection**: Native SSL communication directly to port `36669` with TLS bypass support for unencrypted brokers and automatic fallback routing.
- **Security Hardened**: Protected against XML Entity Expansion (Billion Laughs) and DTD injection using `defusedxml` parsers during UPnP/DLNA discovery.
- **Automatic TV Clock Synchronization**: Extracts HTTP `Date` headers from the TV's internal UPnP/DLNA services on candidate ports (`38400` and `18400`) to prevent hash mismatches during clock drift.
- **Native Reauthentication & Reconfigure**: Full UI support for Home Assistant re-auth notifications, reconfigure actions, and automated PIN sanitization.
- **Accurate State & Standby Handling**: Entities cleanly report `state = "off"` (with `available = True`) during standby, keeping UI power toggles and automations fully functional.
- **Subnet-Aware Wake-on-LAN**: Broadcasts magic packets to both the target `/24` subnet directed broadcast and `255.255.255.255` for reliable cross-VLAN wake-up.
- **Dedicated Remote Entity (`remote`)**:
  - Full remote control platform (`remote.<tv_name>`).
  - Key alias resolution (`up`, `down`, `home`, `menu`, `back`, `ok_long`, `mute_long`, `audio_only`, `screen_off`, `netflix`, `youtube`, etc.).
  - Direct command dispatching with `hold_secs` duration, repeat, and delay controls.
- **Media Player Entity (`media_player`)**:
  - Power toggle and standby control.
  - Volume adjustment, stepping, and mute toggle.
  - Configurable media transport controls (`PLAY`, `PAUSE`, `STOP`, `NEXT_TRACK`, `PREVIOUS_TRACK`, `PLAY_MEDIA`) — toggle via options (works natively in streaming apps and via HDMI-CEC on connected devices).
  - Deep link URI schemes (`netflix://`, `youtube://`, `https://...`) and numeric / decimal channel tuning (e.g. `"70"`, `"7.1"` sending `KEY_CHANNELDOT`).
  - Active HDMI-CEC connected device tracking (`connected_device`) and Live TV channel metadata (`channel_name`, `channel_number`).
  - Unified input source selector with configurable app inclusions (HDMI, TV, AV, Netflix, YouTube, Plex, etc.).
  - Dynamic app CDN artwork in the media player card for the currently active app.
  - Instant local push updates for volume and power state across multiple firmware topic variants.
- **Sensors & Diagnostic Entities**:
  - **Active Source sensor** (`sensor.{tv}_active_source`): tracks current physical input or app with available/connected sources and HDMI-CEC device name as attributes.
  - **Active App sensor** (`sensor.{tv}_active_app`): tracks the running Smart TV app with installed app list as attributes.
  - **Audio Output sensor** (`sensor.{tv}_audio_output`): detects whether audio is outputting through `"TV Speakers"`, external receiver (`"ARC / eARC"`), or is muted.
  - **MQTT Connected binary sensor** (`binary_sensor.{tv}_mqtt_connected`): real-time broker connectivity state.
  - Auth profile, token expiry, and other diagnostic sensors.
  - **Sync Clock button** (`button.{tv}_sync_clock`): manual TV clock synchronization via UPnP/DLNA.
  - Refresh token and force reconnect diagnostic buttons.
  - Native Home Assistant Diagnostics integration (`diagnostics.py`) with sensitive token and IP/MAC redaction.
  - In-UI Repairs issue when certificates are missing or unreadable.
- **Full Options Flow**:
  - Configure device behavior via **Settings → Devices & Services → Configure** without re-pairing.
  - Toggle: dedicated remote entity, Wake-on-LAN, Smart TV app listing in sources, **media transport controls**, and SSL mode.
- **HACS & CI Compliant**:
  - Fully structured for HACS with `hacs.json` and `integration_type: "device"`.
  - Dual CI validation pipelines (`hassfest` + `hacs/action`) for Home Assistant standards compliance.
- **Zero-Duplication CLI Tools**: Two standalone diagnostic scripts sharing 100% backend logic with the integration:
  - [`test_client.py`](test_client.py) — auth probe, pairing, firmware detection, app launcher, WoL, and GitHub issue report generation.
  - [`debug_tv.py`](debug_tv.py) — live state dump, real-time MQTT event monitoring, keypress/app/source control, and clock drift inspection.

---

## 📱 Lovelace Remote Cards & Dashboard Examples

<p align="center">
  <img src="assets/screenshots/ha_australian_remote.png" alt="Hisense Australian Remote Card" width="320" />
</p>

Ready-to-use Lovelace dashboard remote configurations are available in the [`examples/`](examples/) directory. For full setup instructions and requirements, see the **[Lovelace Remote Cards & Dashboard Guide](docs/lovelace_cards.md)**.

- **[Australian Physical Remote (EN2G30H)](examples/lovelace-australian-remote-card.yaml)** — Pixel-accurate 12-app remote recreation (`custom:button-card`) with Netflix, YouTube, Stan, Kayo, Binge, ABC iview, SBS On Demand, 9Now, 10 play, Foxtel, 7plus, and Prime Video.
- **[Classic Free-to-Air Remote](examples/lovelace-classic-remote-card.yaml)** — Traditional TV remote layout designed for broadcast TV without streaming app clutter.
- **[Standard Modular Button Card Remote](examples/lovelace-button-card-remote.yaml)** — Modular vertical stack layout using standard `custom:button-card`.
- **[Android TV Card Profile](examples/lovelace-android-tv-card.yaml)** — Pre-configured profile for `custom:android-tv-card`.
- **[Classic TV Card Profile](examples/lovelace-tv-card.yaml)** — Compact profile for `custom:tv-card`.

---

## 🖥️ Device Registry & UI Overview

### Device Page & Controls
<p align="center">
  <img src="assets/screenshots/integration_device.png" alt="Hisense VIDAA Device Page in Home Assistant" width="100%" />
</p>

### Media Player & Source Selection
<p align="center">
  <img src="assets/screenshots/media_play_entity.png" alt="Media Player Dialog" width="48%" />
  &nbsp;
  <img src="assets/screenshots/media_play_entity_sources.png" alt="Source List Dropdown" width="48%" />
</p>

### Integration & Options
<p align="center">
  <img src="assets/screenshots/integration.png" alt="Integration Card" width="58%" />
  &nbsp;
  <img src="assets/screenshots/configuration_options.png" alt="Configuration Options" width="38%" />
</p>

---

## 🌐 Network Requirements & Best Practices

> [!IMPORTANT]
> **Internet Connectivity Required**: The TV **must have active internet connectivity and unblocked DNS resolution** for pairing, token exchange, and token refresh to succeed.
> 
> If the TV is isolated on an offline IoT VLAN or blocked by network-level ad blockers / firewalls (e.g., AdGuard Home, Pi-hole), VIDAA OS will refuse to complete the pairing handshake or refresh tokens. Ensure the TV has outbound WAN access during pairing and token renewal.

### 📌 Recommended Network Setup

1. **Static DHCP Reservation (Fixed IP)**:
   - It is strongly recommended to set a **static DHCP reservation** on your router/gateway for the TV's MAC address.
   - While the integration supports dynamic IP migration via hardware MAC tracking, a fixed IP guarantees uninterrupted MQTT broker communication, avoids reconnect delays during lease renewals, and prevents connection drops across TV power cycles.

2. **Wired Ethernet for Reliable Wake-on-LAN (WoL)**:
   - For dependable Wake-on-LAN (powering the TV on from standby), connect the TV via a **wired Ethernet cable** rather than Wi-Fi whenever possible.
   - Many Hisense / VIDAA TV models power down the Wi-Fi radio entirely in deep standby / eco mode to save power, whereas the Ethernet controller remains in low-power listening state for magic packets.
   - Ensure Wake-on-LAN is enabled in your TV menu (**Settings → Network / System → Advanced Settings → Wake on LAN / Power on by Apps**), and toggle **Enable Wake-on-LAN** in the integration options (**Settings → Devices & Services → Configure**).

---

## 🔒 SSL Certificate Setup

VIDAA OS requires a client SSL certificate and private key to communicate with port `36669`. Certificates are excluded from this repository and must be provided locally.

Place your certificate files into `/config/custom_components/hisense_vidaa/certs/` (or `/config/certs/`, `/config/ssl/`, `/ssl/`). The integration natively supports extracted `.pem` / `.crt` / `.key` files as well as direct PKCS#12 bundles (`.p12` / `.pfx`):

<details>
<summary><b>📋 Certificate Filename Matrix & Search Paths</b></summary>

| Format / Profile | Firmware / Generation | Certificate / Bundle Filename | Private Key Filename |
| :--- | :--- | :--- | :--- |
| **PKCS#12 Bundle (Auto-Extracted)** | Any Modern VIDAA / RemoteNOW | `client_mobile_android.p12` or `rcamobile.p12` | *(Bundled in .p12)* |
| **VIDAA 2.0 (Modern PEM)** | VIDAA U7 / U8 / OS 7.x+ (`Q0704`+) | `vidaa_2024_cert.pem` or `vidaa_client.pem` | `vidaa_2024_key.pem` or `vidaa_client.key` |
| **RemoteNOW (Standard PEM)** | VIDAA U4 / U5 / U6 (2018–2023) | `remotenow_2018_cert.pem` or `hisense.crt` | `remotenow_2018_key.pem` or `hisense.key` |
| **Generic / Custom PEM** | Standard fallback for any profile | `cert.pem` | `key.pem` |
| **Optional Root CA** | Optional TLS server verification | `remote_ca.pem` or `RemoteCA.crt` | *(Public root CA)* |

</details>

---

## 🔬 Under the Hood: VIDAA Protocol & Architecture

The Hisense VIDAA smart TV hosts an internal MQTT broker on TLS port `36669` using a challenge-response authentication handshake with dynamic salted MD5/XOR hashing and session token auto-renewal.

For the full cryptographic specification, sequence diagram, and MQTT topic dictionary, see **[VIDAA Protocol & Cryptographic Architecture](docs/protocol_architecture.md)**.

<details>
<summary><b>📐 Protocol Flow & Authentication Formulas Summary</b></summary>

```mermaid
sequenceDiagram
    autonumber
    participant HA as Home Assistant (Client)
    participant TV as Hisense VIDAA TV (:36669)
    
    Note over HA,TV: 1. TLS v1.2 Handshake (Client Cert & Key)
    HA->>TV: Connect MQTT (Dynamic Username + Salt Hash)
    TV-->>HA: CONNACK (rc: 0)
    
    Note over HA,TV: 2. Challenge-Response PIN Handshake
    HA->>TV: Publish actions/vidaa_app_connect
    TV-->>HA: Display 4-digit PIN & challenge
    HA->>TV: Submit PIN {"authNum": <PIN>}
    TV-->>HA: PIN Accepted (result: 1)
    
    Note over HA,TV: 3. Session Token Issuance
    HA->>TV: Request Token (platform_service/data/gettoken)
    TV-->>HA: Tokens (Access [48h], Refresh [30d])
    
    Note over HA,TV: 4. Runtime Operations & Auto-Renew
    HA->>TV: Runtime Commands (sendkey, launchapp, changesource)
    TV-->>HA: Push State Broadcasts (volumechange, state)
```

- **Modern VIDAA 2.0 (`Q0704`+)**: 64-bit XOR timestamp mask (`0x5689ab4102ef1908`) + modern salt `h!i@s#$v%i^d&a*a`.
- **RemoteNOW Standard (`P1027` and older)**: Unix timestamp + salt `h*i&s%e!r^v0i1c9`.
- **Legacy Static (Pre-2022)**: Static credentials (`hisenseservice` / `multimqttservice`).
- **Token Auto-Renewal**: 48h access tokens automatically renewed in background using 30-day refresh tokens.

</details>

---

## 🏗 Codebase Architecture

The integration is built around modular, single-responsibility components:

| Module | Responsibility |
| :--- | :--- |
| [`crypto.py`](custom_components/hisense_vidaa/crypto.py) | Dynamic authentication hashing, salt matrices, XOR timestamp generation, and certificate path resolution. |
| [`discovery.py`](custom_components/hisense_vidaa/discovery.py) | UPnP/SSDP XML device descriptor parser and mDNS Zeroconf network discovery helpers. |
| [`const.py`](custom_components/hisense_vidaa/const.py) | Centralized constants, key aliases, and authentication profile definitions. |
| [`client.py`](custom_components/hisense_vidaa/client.py) | Core asynchronous MQTT client lifecycle, challenge-response handshake, and event dispatching. |

---

## 🧪 Testing & Diagnostics

The integration ships with two standalone CLI tools that share 100% backend logic with the Home Assistant integration:

- **[`test_client.py`](test_client.py)** — Auth probe, pairing, firmware detection, WoL, and GitHub issue report generation.
- **[`debug_tv.py`](debug_tv.py)** — Live state dump, real-time MQTT event monitoring, keypress/app/source control, and clock drift inspection.

For complete documentation and command options, see the **[CLI Tools Reference Guide](docs/cli_tools.md)**.

<details>
<summary><b>💻 Quick CLI Command Reference</b></summary>

```bash
# 1. Generate GitHub Issue Diagnostic Report
python3 test_client.py report --ip <TV_IP>

# 2. Diagnostic Probe & Firmware Detection
python3 test_client.py ping --ip <TV_IP>

# 3. Test Raw SSL/TLS Connection
python3 test_client.py test-ssl --ip <TV_IP>

# 4. Pair TV and Retrieve Tokens
python3 test_client.py auth --ip <TV_IP>

# 5. Live State Dump (via debug_tv.py)
python3 debug_tv.py --dump-state

# 6. Monitor Real-Time MQTT Events
python3 debug_tv.py --monitor

# 7. Send Keypress or Launch App
python3 debug_tv.py --send-key KEY_HOME
python3 debug_tv.py --launch-app Netflix
```

</details>

---

## ⚙️ Installation & Home Assistant Setup

### Method 1: HACS (Recommended)

1. Click the button below to add this repository directly to HACS:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

   *Or manually in HACS:*
   - Go to **HACS** -> **Integrations**.
   - Click the three dots in the top right -> **Custom repositories**.
   - Add `https://github.com/stevene1919/hisense_vidaa` with Category **Integration**.
   - Search for **Hisense VIDAA TV** and click **Download**.

2. Place your certificate files (`vidaa_2024_cert.pem` / `remotenow_2018_cert.pem` or `cert.pem`) into `/config/custom_components/hisense_vidaa/certs/` (or `/config/certs/` / `/config/ssl/`).
3. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release from the [Releases](https://github.com/stevene1919/hisense_vidaa/releases) page.
2. Copy the `custom_components/hisense_vidaa/` folder to your Home Assistant `/config/custom_components/` directory.
3. Place certificate files inside `/config/custom_components/hisense_vidaa/certs/`.
4. Restart Home Assistant.

---

### Pairing & Configuration

1. In Home Assistant, go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **Hisense VIDAA TV**.
3. Enter the TV's IP address and select your **Authentication / Certificate Profile** (default: `Auto Detect (Recommended)`).
4. A 4-digit PIN code will appear on the TV screen — enter it into the prompt to complete setup.

---

## 🛠️ Custom Services & Example Automations

<details>
<summary><b>📋 Example Service Calls & Automations (YAML)</b></summary>

### 1. `hisense_vidaa.launch_app`
Launch an installed Smart TV application by name or direct URL:
```yaml
action: hisense_vidaa.launch_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "Netflix" # e.g., Netflix, YouTube, Prime Video, Plex, Disney+
```

### 2. `hisense_vidaa.send_key`
Send fast single or repeated key commands:
```yaml
action: hisense_vidaa.send_key
target:
  entity_id: remote.living_room_tv_remote
data:
  key: "home"
  repeat: 1
  delay: 0.2
```

### 3. Native Remote Key Sequences (`remote.send_command`)
```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_tv_remote
data:
  command:
    - home
    - right
    - right
    - ok
  delay_secs: 0.3
```

### 4. Smart TV App Launcher Buttons
```yaml
type: horizontal-stack
cards:
  - type: button
    name: Netflix
    icon: mdi:netflix
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_tv
      data:
        app: Netflix
  - type: button
    name: YouTube
    icon: mdi:youtube
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_tv
      data:
        app: YouTube
  - type: button
    name: Prime Video
    icon: mdi:movie-open
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_tv
      data:
        app: Prime Video
```

</details>

---

## 🔗 Legacy Firmware Alternatives & Related Projects

If your TV accepts static credentials or you are running older Hisense hardware:

* **[sehaas/ha_hisense_tv](https://github.com/sehaas/ha_hisense_tv)**: Home Assistant custom component for older firmware supporting static MQTT credentials.
* **[Krazy998/mqtt-hisensetv](https://github.com/Krazy998/mqtt-hisensetv/)**: Docker MQTT broker bridge and utilities for legacy models.

---

## 📋 Roadmap & Planned Features

See [`TODO.md`](TODO.md) for the active development backlog, planned features (e.g., dynamic model/firmware binding in device info), and network resilience investigations.

---

## Credits & Acknowledgments

This native integration adapts foundational reverse-engineering discoveries from the open-source community:

* **Nika Gerson Lohman ([@nikagl](https://github.com/nikagl))**: For creating the original `hisense.py` script architecture and proving the RemoteNOW-style dynamic PIN authentication flow.
* **[@Krazy998](https://github.com/Krazy998) & Contributors**: For collaborative research on the `mqtt-hisensetv` project decoding VIDAA OS MQTT communication.
