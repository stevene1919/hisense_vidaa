# Hisense VIDAA TV Integration for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/hisensevidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)
[![Validate with HACS](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml)
[![Lint & Verify](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

A native Home Assistant integration for Hisense smart TVs running VIDAA OS.

Connects **directly** to the TV's internal MQTT broker (TLS port `36669`) using client certificates, providing local push updates, media controls, app launching, Wake-on-LAN, and remote control without external bridges or cloud dependencies.

<p align="center">
  <img src="assets/screenshots/integration_device.png" alt="Hisense VIDAA TV in Home Assistant" width="100%" />
</p>

<p align="center">
  <a href="https://ko-fi.com/stevene_">
    <img src="https://img.shields.io/badge/Support%20this%20Project-Buy%20Me%20A%20Coffee%20on%20Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Buy Me A Coffee on Ko-fi" />
  </a>
</p>

---

## 🧭 Supported Generations & Models

The integration automatically detects and supports multiple generations of Hisense and licensed OEM smart TVs:

| TV Generation / Firmware | Profile | Pairing Method | Description |
| :--- | :--- | :--- | :--- |
| **Modern VIDAA OS (2024+ / U6+, U7, U8, UX)** | `modern` | 4-Digit Screen PIN | Modern VIDAA 2.0 with dynamic challenge handshake |
| **Middle VIDAA OS (VIDAA 1.5 / U5, early U6)** | `middle` | 4-Digit Screen PIN | Middle VIDAA transition firmware with dynamic pairing |
| **Standard VIDAA OS (2018–2023 / U4, U5)** | `remotenow` | 4-Digit Screen PIN | RemoteNOW dynamic PIN protocol |
| **Legacy Models (Pre-2022 / U2, U3)** | `legacy` | Instant Setup (No PIN) | Static service credential mode |
| **Auto Detection (All Generations & OEMs)** | `auto` | Automatic | UPnP transport probe with automatic multi-tier fallback |

> For complete cryptographic formulas, XOR masks, and OEM brand identifiers (Toshiba, Loewe, etc.), see [Protocol & Cryptographic Architecture](docs/protocol_architecture.md).

---

## ✨ Features

- **100% Local LAN Control (`iot_class: local_push`)**: Connects directly to the TV's hardware MQTT broker over your local network with **zero cloud dependencies**, zero external API calls, and full support for isolated IoT VLANs (WAN blocked). All cryptographic authentication logic is implemented in **100% native Python** with zero compiled binary dependencies.
- **Local Push Updates**: Instant feedback for power state, volume, mute, source input, and active app.
- **Media Player Platform**: Full power toggle, volume stepping, input source switcher, dynamic app artwork, deep linking, and configurable media transport controls. Exposes `MediaPlayerDeviceClass.TV` for native Apple HomeKit and iOS Control Center virtual remote integration.
- **Dedicated Remote Platform**: Fast key command dispatching, key aliases (`home`, `menu`, `back`, `ok`, etc.), configurable repeat counts, and inter-key delay options.
- **Picture & Display Adjustments (`number` & `select`)**: Fine-tune Backlight, Brightness, and Contrast slider entities (0–100) and switch Picture Modes (`Standard`, `Cinema Day`, `Cinema Night`, `Dynamic`, `Sports`, `Game`, `Filmmaker Mode`) dynamically.
- **Sound Mode Selector (`select`)**: Switch real-time TV sound equalizer modes (`Standard`, `Theatre`, `Music`, `Speech`, `Late Night`, `Sports`) and audio output routing (`select.{tv}_audio_output`).
- **On-Screen Toast Notifications (`notify`)**: Send customized on-screen toast messages and alert banners directly to the TV screen via `notify.send_message`.
- **Direct Text Input (`send_text_input` service)**: Inject virtual keyboard text directly into on-screen search bars and input fields across apps.
- **Rich Diagnostic Sensors & Utility Buttons**: Active source (with dynamic HDMI-CEC device naming), active Smart TV app, audio output mode, MQTT connection state, and session status, along with dedicated diagnostic buttons for forcing reconnection, probing picture/sound capabilities, UPnP clock sync, and triggering manual re-pairing.
- **Network Resilience**: Subnet-directed Wake-on-LAN with dual-MAC fallback (Ethernet + Wi-Fi) for reliable power-on from deep standby, clock synchronization via UPnP, and automatic 30-day token refresh.
- **Flexible SSL Handling**: Automatic in-memory extraction for PKCS#12 bundles (`.p12` / `.pfx`) and support for standard PEM pairs (`.pem`, `.crt`, `.key`) stored in `/config/ssl`.
- **Tabbed Options Flow**: Beautiful, categorized options menu (General & Power, Sources & Media, Remote Key Timings, SSL Certificates) for adjusting settings without re-pairing.

---

## 🚀 Installation & Setup

### Step 1: Install the Integration Files

You can install the integration either via **HACS** (easiest) or **Manually** (without HACS).

#### Option A: Install via HACS (Recommended)

Click the button below to add this repository directly to your HACS installation:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

*Or manually in HACS:* **HACS** $\rightarrow$ **Integrations** $\rightarrow$ **Custom repositories** $\rightarrow$ Add `https://github.com/stevene1919/hisense_vidaa` (Category: *Integration*).

---

#### Option B: Manual Installation

Download the latest [release ZIP](https://github.com/stevene1919/hisense_vidaa/releases/latest) and extract `custom_components/hisense_vidaa` into your Home Assistant `/config/custom_components/` directory.

---

### Step 2: Place Certificate Files

Copy your client certificate / key (or `.p12` bundle) to `/config/ssl/` (or `/ssl/` / `/config/certs/`).

> For certificate formats, filename matrix, and automatic extraction, see the **[SSL Certificate Guide](docs/certificates.md)**.

### Step 3: Pair Your TV

1. **Restart Home Assistant** (`Settings` $\rightarrow$ `System` $\rightarrow$ `Restart`).
2. Go to **Settings $\rightarrow$ Devices & Services $\rightarrow$ Add Integration** and search for **Hisense VIDAA TV**.
3. Enter your TV's IP address and select `Auto Detect (Recommended)`.
4. Enter the 4-digit PIN displayed on your TV screen to complete setup.

> [!TIP]
> **Recommended TV Settings**:
> To ensure your TV remains responsive in standby and avoids losing paired tokens when connected HDMI devices (e.g. Chromecast, Apple TV, PC) sleep, refer to the **[TV Power, Standby & Network Settings Guide](docs/power_and_standby_settings.md)**.

---

## 📚 Detailed Documentation & Guides

For deep technical details, configuration parameters, and dashboard templates, refer to the dedicated documentation library:

| Document | Topic | Description |
| :--- | :--- | :--- |
| ⚙️ **[Configuration & Options Parameters](docs/parameters.md)** | **Parameters** | Complete reference for all initial setup fields and Options Flow parameters across all tabs. |
| ⚡ **[TV Power, Standby & Network Settings](docs/power_and_standby_settings.md)** | **Power & Standby** | Model settings (VIDAA U4–U8, 2024+), two-tier standby architecture, and preventing token loss. |
| 📱 **[Lovelace Remote Cards & Dashboards](docs/lovelace_cards.md)** | **UI Cards** | Australian EN2G30H 12-app remote, Classic FTA, Button Card, and Android TV Card templates. |
| 🛠️ **[Services & Automation Examples](docs/services_and_automations.md)** | **Automations** | Ready-to-use YAML automations for movie modes, picture/sound toggling, and keyboard input. |
| 🔒 **[SSL Certificate Setup](docs/certificates.md)** | **Certificates** | Mutual TLS file placement (`/config/ssl/`), filename matrix, and automatic PKCS#12 extraction. |
| 🌐 **[Network & Wake-on-LAN Requirements](docs/network_requirements.md)** | **Networking** | 100% local LAN architecture, UPnP LAN control, IoT VLAN rules, and reliable wired WoL setup. |
| 🧪 **[CLI Testing & Diagnostic Tools](docs/cli_tools.md)** | **CLI Utilities** | Standalone [`test_client.py`](test_client.py) and [`debug_tv.py`](debug_tv.py) command-line tool reference. |
| 🔬 **[Protocol & Cryptographic Architecture](docs/protocol_architecture.md)** | **Architecture** | Reverse-engineered UPnP LAN control, XOR bitmasks, token lifecycles, and multi-brand ecosystem. |
| 🗑️ **[Removal & Uninstallation Guide](docs/removal.md)** | **Uninstallation** | Step-by-step device deletion, certificate cleanup, and HACS component uninstallation. |
| 🖼️ **[Screenshots & UI Gallery](docs/screenshots.md)** | **Showcase** | Full visual tour of device controls, media player dialogs, source dropdowns, and option menus. |

---

## 🛠️ Diagnostics & Troubleshooting

The integration includes standalone CLI diagnostic utilities ([`test_client.py`](test_client.py) and [`debug_tv.py`](debug_tv.py)) to test network connectivity, probe dynamic TV capabilities, verify TLS certificates, and generate pre-formatted report blocks for GitHub issues without running Home Assistant.

```bash
# Quick feature and capability probe:
python3 test_client.py probe --ip <TV_IP>

# Generate a complete sanitized report for GitHub issues:
python3 test_client.py report --ip <TV_IP> --probe
```

> For one-line curl runners, live MQTT event streaming, and full command arguments, see the **[CLI Testing & Diagnostic Tools Guide](docs/cli_tools.md)**.

---

## ⚡ Integration Actions & Services

The integration provides custom Home Assistant actions for advanced automation and remote control:

| Action | Description | Key Parameters |
| :--- | :--- | :--- |
| `hisense_vidaa.send_key` | Sends navigation, playback, and numerical remote key commands. | `key`, `repeat`, `delay` |
| `hisense_vidaa.launch_app` | Launches installed smart TV applications by display name, app ID, and optional video deep-link URL. | `app`, `app_id`, `app_name`, `url` |
| `hisense_vidaa.set_picture_setting` | Direct hardware adjustment of TV picture mode settings. | `menu_id`, `menu_value` |
| `hisense_vidaa.set_sound_setting` | Direct hardware adjustment of TV sound and equalizer settings. | `menu_id`, `menu_value` |
| `hisense_vidaa.send_text_input` | Sends text strings directly to active onscreen search boxes. | `text`, `action` |

> For complete YAML examples, input validation, and service schema details, see the **[Services & Automations Guide](docs/services_and_automations.md)**.

---

## 🗑️ Removal & Uninstallation

To cleanly remove the Hisense VIDAA TV integration:
1. In Home Assistant, navigate to **Settings $\rightarrow$ Devices & Services**, locate **Hisense VIDAA TV**, click the three vertical dots (`⋮`), and select **Delete**.
2. Remove the component from **HACS $\rightarrow$ Integrations** (or delete `/config/custom_components/hisense_vidaa/`), then restart Home Assistant (`Settings` $\rightarrow$ `System` $\rightarrow$ `Restart`).

> For detailed certificate cleanup and multi-device removal steps, see the dedicated **[Removal & Uninstallation Guide](docs/removal.md)**.

---

## 📋 Roadmap & Backlog

See [`TODO.md`](TODO.md) for active development items, planned enhancements, and feature requests.

---

## ☕ Support the Project

If this integration makes your smart home better or saved you hours of troubleshooting, consider supporting continued reverse-engineering, maintenance, and new features:

<p align="center">
  <a href="https://ko-fi.com/stevene_" target="_blank">
    <img src="https://storage.ko-fi.com/cdn/kofi3.png?v=3" height="44" style="border:0px;height:44px;" alt="Buy Me A Coffee at ko-fi.com" />
  </a>
</p>

---

## 🤝 Credits & Acknowledgments

This integration builds upon foundational reverse-engineering research by the open-source smart home community:

* **Nika Gerson Lohman ([@nikagl](https://github.com/nikagl))**: Pioneer of the dynamic RemoteNOW PIN challenge flow and `hisense.py`.
* **[@Krazy998](https://github.com/Krazy998) & Contributors**: MQTT protocol research on `mqtt-hisensetv`.
