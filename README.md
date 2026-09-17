# Hisense VIDAA TV Integration for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Validate with HACS](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml)
[![Lint & Verify](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

A native Home Assistant integration for Hisense smart TVs running VIDAA OS.

Connects **directly** to the TV's internal MQTT broker (TLS port `36669`) using client certificates, providing local push updates, media controls, app launching, Wake-on-LAN, and remote control without external bridges or cloud dependencies.

<p align="center">
  <img src="assets/screenshots/integration_device.png" alt="Hisense VIDAA TV in Home Assistant" width="100%" />
</p>

---

## 🧭 Supported Generations & Models

The integration automatically detects and supports multiple generations of Hisense smart TVs:

| TV Generation / Firmware | Profile | Auth Model | Pairing Method |
| :--- | :--- | :--- | :--- |
| **Modern VIDAA OS (2024+ / U6+, U7)** | `modern` | **Modern VIDAA 2.0** (`libmqttcrypt` XOR mask) | 4-Digit Screen PIN |
| **Standard VIDAA OS (2018–2023 / U4, U5, U6, P1027)** | `remotenow` | **RemoteNOW Dynamic** (`his$<timestamp>`) | 4-Digit Screen PIN |
| **Legacy Hisense / Older Models (Pre-2022 / U2, U3)** | `legacy` | **Legacy Static** (`hisenseservice`) | Instant Setup (No PIN) |
| **Newer VIDAA OS (U7+ / Q0704+ / App v1.09+)** | `auto` | *Under Active Reverse-Engineering (Issue #6)* | PIN Handshake v3 |

---

## ✨ Features

- **100% Local LAN Control (`iot_class: local_push`)**: Connects directly to the TV's hardware MQTT broker over your local network with **zero cloud dependencies**, zero external API calls, and full support for isolated IoT VLANs (WAN blocked).
- **Local Push Updates**: Instant feedback for power state, volume, mute, source input, and active app.
- **Media Player Platform**: Full power toggle, volume stepping, input source switcher, dynamic app artwork, deep linking, and configurable media transport controls. Exposes `MediaPlayerDeviceClass.TV` for native Apple HomeKit and iOS Control Center virtual remote integration.
- **Dedicated Remote Platform**: Fast key command dispatching, key aliases (`home`, `menu`, `back`, `ok`, etc.), configurable repeat counts, and inter-key delay options.
- **Picture & Display Adjustments (`number` & `select`)**: Fine-tune Backlight, Brightness, and Contrast slider entities (0–100) and switch Picture Modes (`Standard`, `Cinema Day`, `Cinema Night`, `Dynamic`, `Sport`, `Game`, `Filmmaker Mode`, `PC`) dynamically.
- **Sound Mode Selector (`select`)**: Switch real-time TV sound equalizer modes (`Standard`, `Theater`, `Music`, `Speech`, `Late Night`, `Sports`) and audio output routing (`select.{tv}_audio_output`).
- **On-Screen Toast Notifications (`notify`)**: Send customized on-screen toast messages and alert banners directly to the TV screen via `notify.send_message`.
- **Direct Text Input (`send_text_input` service)**: Inject virtual keyboard text directly into on-screen search bars and input fields across apps.
- **Rich Diagnostic Sensors**: Active source (with dynamic HDMI-CEC device naming), active Smart TV app, audio output mode, MQTT connection state, and session status.
- **Network Resilience**: Subnet-directed Wake-on-LAN with dual-MAC fallback (Ethernet + Wi-Fi) for reliable power-on from deep standby, clock synchronization via UPnP, and automatic 30-day token refresh.
- **Flexible SSL Handling**: Automatic in-memory extraction for PKCS#12 bundles (`.p12` / `.pfx`) and support for standard PEM pairs (`.pem`, `.crt`, `.key`) stored in `/config/ssl`.
- **Tabbed Options Flow**: Beautiful, categorized options menu (General & Power, Sources & Media, Remote Key Timings, SSL Certificates) for adjusting settings without re-pairing.

---

## 🚀 Quick Start

### 1. Install via HACS

Click the button below to add this repository directly to your HACS installation:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

*Or manually in HACS:* **HACS** $\rightarrow$ **Integrations** $\rightarrow$ **Custom repositories** $\rightarrow$ Add `https://github.com/stevene1919/hisense_vidaa` (Category: *Integration*).

### 2. Place Certificate Files

Copy your client certificate / key (or `.p12` bundle) to `/config/ssl/` (or `/ssl/` / `/config/certs/`).

> For certificate formats and search paths, see the **[SSL Certificate Guide](docs/certificates.md)**.

### 3. Pair Your TV

1. Restart Home Assistant.
2. Go to **Settings $\rightarrow$ Devices & Services $\rightarrow$ Add Integration** and search for **Hisense VIDAA TV**.
3. Enter your TV's IP address and select `Auto Detect (Recommended)`.
4. Enter the 4-digit PIN displayed on your TV screen to complete setup.

---

## 📚 Detailed Documentation & Guides

For deep technical details, guides, and dashboard templates, refer to the dedicated documentation:

| Document | Description |
| :--- | :--- |
| 📱 **[Lovelace Remote Cards & Dashboards](docs/lovelace_cards.md)** | Pixel-accurate Australian EN2G30H 12-app remote, Classic FTA, Button Card, and Android TV Card templates. |
| 🖼️ **[Screenshots & UI Gallery](docs/screenshots.md)** | Full visual tour of device controls, media player dialogs, source dropdowns, and option flows. |
| 🔒 **[SSL Certificate Setup](docs/certificates.md)** | Certificate filename matrix, PKCS#12 extraction, and root CA verification. |
| 🌐 **[Network & Wake-on-LAN Requirements](docs/network_requirements.md)** | 100% local LAN architecture, static DHCP setup, IoT VLAN configuration, and reliable wired WoL guidelines. |
| 🛠️ **[Services & Automation Examples](docs/services_and_automations.md)** | Full YAML automation examples, picture/sound adjustments, `hisense_vidaa.send_text_input`, and button cards. |
| 🧪 **[CLI Testing & Diagnostic Tools](docs/cli_tools.md)** | Standalone [`test_client.py`](test_client.py) and [`debug_tv.py`](debug_tv.py) command-line utility reference. |
| 🔬 **[Protocol & Cryptographic Architecture](docs/protocol_architecture.md)** | Deep-dive reverse engineering: XOR masks, dynamic hashes, token lifecycles, and MQTT topic dictionary. |

---

## 🛠️ Diagnostics & Troubleshooting

The integration includes diagnostic CLI tools ([`test_client.py`](test_client.py) & [`debug_tv.py`](debug_tv.py)) to test network connectivity, probe TV capabilities, and generate pre-formatted report blocks for GitHub issues.

### Running the Diagnostic Tool

```bash
# Option A: From any PC or server (recommended):
git clone https://github.com/stevene1919/hisense_vidaa.git
cd hisense_vidaa
python3 test_client.py probe --ip <TV_IP>

# Option B: Inside Home Assistant (Terminal / SSH Addon):
cd /config
curl -sSL https://raw.githubusercontent.com/stevene1919/hisense_vidaa/main/test_client.py -o test_client.py
python3 test_client.py probe --ip <TV_IP>
```

### Common Commands

```bash
# Generate a complete diagnostics report with feature probing for GitHub issues:
python3 test_client.py report --ip <TV_IP> --probe

# Probe picture, sound, installed apps, and input sources:
python3 test_client.py probe --ip <TV_IP>

# Quick 3-tier connectivity & firmware detection probe:
python3 test_client.py ping --ip <TV_IP>
```

> See the full **[CLI Testing & Diagnostic Guide](docs/cli_tools.md)** for more commands (`launch-app`, `send-key`, `listen`, `wake`).

---

## 📋 Roadmap & Backlog

See [`TODO.md`](TODO.md) for active development items, planned enhancements, and feature requests.

---

## 🤝 Credits & Acknowledgments

This integration builds upon foundational reverse-engineering research by the open-source smart home community:

* **Nika Gerson Lohman ([@nikagl](https://github.com/nikagl))**: Pioneer of the dynamic RemoteNOW PIN challenge flow and `hisense.py`.
* **[@Krazy998](https://github.com/Krazy998) & Contributors**: MQTT protocol research on `mqtt-hisensetv`.
