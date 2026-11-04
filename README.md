# Hisense VIDAA TV Integration for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/hisensevidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)
[![Validate with HACS](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/validate.yml)
[![Lint & Verify](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml/badge.svg)](https://github.com/stevene1919/hisense_vidaa/actions/workflows/lint.yml)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

A native Home Assistant integration for Hisense smart TVs running VIDAA OS.

Connects **directly** to the TV's internal MQTT broker (TLS port `36669`) using client certificates, providing local push updates, media controls, app launching, Wake-on-LAN, and remote control without external bridges or cloud dependencies.

<p align="center">
  <img src="https://raw.githubusercontent.com/stevene1919/hisense_vidaa/main/assets/screenshots/integration_device.png" alt="Hisense VIDAA TV in Home Assistant" width="100%" />
</p>

<p align="center">
  <a href="https://ko-fi.com/stevene_">
    <img src="https://img.shields.io/badge/Support%20this%20Project-Buy%20Me%20A%20Coffee%20on%20Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Buy Me A Coffee on Ko-fi" />
  </a>
</p>

---

## 🧭 Supported Generations & Models

The integration officially supports all smart TV models running VIDAA OS across all generations (pairing via **4-Digit Screen PIN**):

- 📺 **Hisense Modern (2021+)**
  - **Verified Series**: U6G, U7G, U8G, U6K, U7K, U8K, UX, A6G, A6H, A7GQ, A63H, E7HQ, E7K PRO
  - **Firmware Builds**: `Q0704`, `V0000.06`, `U6.1.0`, `U7.0`, `U8.0`
  - **Auth Profile**: `modern` / `auto`

- 📺 **Hisense Standard & Middle (2018–2021)**
  - **Verified Series**: U4G, U5G, H8G, H9G, B7100, B7500, A7100, A7300, A7500
  - **Firmware Builds**: `V0000.01`–`V0000.05`, `U4.0`, `U5.0`
  - **Auth Profile**: `middle` / `remotenow`

- 📺 **Licensed OEM Partner Brands (VIDAA OS Editions)**
  - **Popular Brands**: Toshiba, Loewe, Philips / TPV, Sharp, JVC (and other licensed VIDAA OS partner TVs)
  - **Auth Profile**: `auto` (auto-detects OEM salt with candidate auth cascade)
  - **Brand Detection**: Automatic via SSDP/UPnP, certificate filenames (e.g. `toshiba.crt`, `loewe.pem`, `sharp.pem`), or manual selection in setup/options.

> **Universal VIDAA Platform**: All VIDAA OS televisions share the same internal hardware broker and root certificate authority (`RemoteCA`). The integration automatically identifies partner brands, applies OEM-specific cryptographic salts, and sets the proper manufacturer in Home Assistant's Device Registry. For complete brand lists and cryptographic formulas, see [Protocol & Cryptographic Architecture](docs/protocol_architecture.md).

> [!NOTE]
> **VIDAA OS vs Android TV (No Android Device Required)**:
> This integration is specifically for televisions powered by **VIDAA OS** (a Linux-based embedded OS). It is **not** for Hisense models running Android TV or Google TV (which should use Home Assistant's built-in Android TV Remote integration). **No Android smartphone, tablet, emulator, or running app is required to use this integration.** Home Assistant communicates directly with the TV over your local network.

---

## ✨ Features

- **100% Local LAN Control (`iot_class: local_push`)**: Connects directly to the TV's hardware MQTT broker over your local network with **zero cloud dependencies**, zero external API calls, and full support for isolated IoT VLANs (WAN blocked). All cryptographic authentication logic is implemented in **100% native Python** with zero compiled binary dependencies.
- **Local Push Updates**: Instant feedback for power state, volume, mute, source input, and active app.
- **Media Player Platform**: Full power toggle, volume stepping, input source switcher, dynamic app artwork, deep linking, and configurable media transport controls. Exposes `MediaPlayerDeviceClass.TV` for native Apple HomeKit and iOS Control Center virtual remote integration.
- **Dedicated Remote Platform**: Fast key command dispatching, key aliases (`home`, `menu`, `back`, `ok`, etc.), configurable repeat counts, and inter-key delay options.
- **Picture & Display Adjustments (`number` & `select`)**: Fine-tune Backlight, Brightness, and Contrast slider entities (0–100) and switch Picture Modes (`Standard`, `Cinema Day`, `Cinema Night`, `Dynamic`, `Sports`, `Game`, `Filmmaker Mode`) dynamically.
- **Sound Mode Selector (`select`)**: Switch real-time TV sound equalizer modes (`Standard`, `Theatre`, `Music`, `Speech`, `Late Night`, `Sports`) and audio output routing (`select.{tv}_audio_output`).
- **On-Screen Toast Notifications (`notify`)**: Send customized on-screen toast messages to the TV directly from Home Assistant automations.
- **Subnet Wake-on-LAN**: Reliable, multi-burst WoL magic packet dispatching with configurable subnet broadcasting across dual-NIC and VLAN networks.
- **Tabbed Options Flow**: Beautiful, categorized options menu (General & Power, Sources & Media, Remote Key Timings, SSL Certificates) for adjusting settings without re-pairing.

---

## 🚀 Installation & Setup

### Step 1: Install the Integration Files

You can install the integration either via **HACS** (easiest) or **Manually** (without HACS).

#### Option A: Install via HACS (Recommended)

This integration is available directly in the official **HACS default repository**!

1. **One-Click Install**: Click the button below to open the integration directly in HACS:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

2. *Or search directly in HACS*:
   - Open **HACS** from your Home Assistant sidebar.
   - Search for **Hisense VIDAA TV**.
   - Select the integration and click **Download** in the bottom right corner.

---

#### Option B: Manual Installation

Download the latest [release ZIP](https://github.com/stevene1919/hisense_vidaa/releases/latest) and extract `custom_components/hisense_vidaa` into your Home Assistant `/config/custom_components/` directory.

> [!TIP]
> **Advanced Users & Developers**:
> Looking to clone via Git, track development/beta branches, use Git submodules, or run standalone diagnostics without Home Assistant? See the **[Advanced Installation & Development Guide](docs/installation_advanced.md)**.

---

### Step 2: Place Certificate Files

Copy your client certificate / key (or `.p12` bundle) to `/config/ssl/` (or `/ssl/` / `/config/certs/`).

> [!IMPORTANT]
> **No Android Device or Running Mobile App Required**:
> The only reason Android is ever referenced is because the vendor packages its mutual TLS client certificate inside the publicly distributed VIDAA remote mobile app archive (`.apk`). An APK file is simply a standard ZIP archive—you can extract the `.p12` certificate file on any Windows, macOS, or Linux machine using `unzip` without ever owning or running Android.
>
> For certificate formats, step-by-step extraction commands, filename matrix, and automatic loading, see the **[SSL Certificate Guide](docs/certificates.md)**.

### Step 3: Pair Your TV

1. **Restart Home Assistant** (`Settings` → `System` → `Restart`).
2. Go to **Settings → Devices & Services → Add Integration** and search for **Hisense VIDAA TV**.
3. Enter your TV's IP address and select `Auto Detect (Recommended)`.
4. Enter the 4-digit PIN displayed on your TV screen to complete setup.

> [!TIP]
> **Recommended TV Settings**:
> To ensure your TV remains responsive in standby and avoids losing paired tokens when connected HDMI devices (e.g. Chromecast, Apple TV, PC) sleep, refer to the **[TV Power, Standby & Network Settings Guide](docs/power_and_standby_settings.md)**.

> [!IMPORTANT]
> **Hardware Power Warning (HDMI Streaming Devices)**:
> Never power external HDMI streaming dongles (Chromecast, Fire TV, Roku) from the TV's onboard USB port. The TV's USB port cannot sustain the peak current demands, triggering electrical brownouts during standby transitions that crash the TV mainboard and wipe paired MQTT credentials (`Reauth Required`). Always use the streaming device's supplied mains AC wall adapter. See [Dedicated Power for HDMI Devices](docs/power_and_standby_settings.md#%EF%B8%8F-hardware-requirement-dedicated-power-for-hdmi-streaming-devices-do-not-use-tv-usb).

---

## 📚 Detailed Documentation & Guides

For deep technical details, configuration parameters, and dashboard templates, refer to the dedicated documentation library:

| Guide | Description |
| :--- | :--- |
| ⚙️ **[Configuration & Options Parameters](docs/parameters.md)** | Complete reference for all initial setup fields and Options Flow parameters across all tabs. |
| ⚡ **[TV Power, Standby & Network Settings](docs/power_and_standby_settings.md)** | Model settings (VIDAA U4–U8, 2024+), two-tier standby architecture, and preventing token loss. |
| 📱 **[Lovelace Remote Cards & Dashboards](docs/lovelace_cards.md)** | Australian EN2G30H 12-app remote, Classic FTA, Button Card, and Android TV Card templates. |
| 🛠️ **[Services & Automation Examples](docs/services_and_automations.md)** | Ready-to-use YAML automations for movie modes, picture/sound toggling, and keyboard input. |
| 🔒 **[SSL Certificate Setup](docs/certificates.md)** | Mutual TLS file placement (`/config/ssl/`), filename matrix, and automatic PKCS#12 extraction. |
| 🌐 **[Network & Wake-on-LAN Requirements](docs/network_requirements.md)** | 100% local LAN architecture, UPnP LAN control, IoT VLAN rules, and reliable wired WoL setup. |
| 🧪 **[CLI Testing & Diagnostic Tools](docs/cli_tools.md)** | Standalone [`test_client.py`](test_client.py) and [`debug_tv.py`](debug_tv.py) command-line tool reference. |
| 🔬 **[Protocol & Cryptographic Architecture](docs/protocol_architecture.md)** | Reverse-engineered UPnP LAN control, XOR bitmasks, token lifecycles, and multi-brand ecosystem. |
| 🛠️ **[Advanced Installation & Development](docs/installation_advanced.md)** | Git cloning, branch tracking, Git submodules, standalone venv setup, and air-gapped VLAN installs. |
| 🩺 **[Troubleshooting & Error Reference](docs/troubleshooting.md)** | Diagnostic procedures, error recovery, pairing resets, and action error resolutions. |
| 🗑️ **[Removal & Uninstallation Guide](docs/removal.md)** | Step-by-step device deletion, certificate cleanup, and HACS component uninstallation. |
| 🖼️ **[Screenshots & UI Gallery](docs/screenshots.md)** | Full visual tour of device controls, media player dialogs, source dropdowns, and option menus. |

---

## 🛠️ Diagnostics & Troubleshooting

Standalone CLI tools ([`test_client.py`](test_client.py) and [`debug_tv.py`](debug_tv.py)) are available to test network reachability, verify TLS certificates, probe TV capabilities, and generate pre-formatted report blocks for GitHub issues without running Home Assistant.

> For command arguments, one-line curl runners, and live MQTT streaming, see the **[CLI Testing & Diagnostic Tools Guide](docs/cli_tools.md)** and **[Troubleshooting Reference](docs/troubleshooting.md)**.

---

## ⚡ Integration Actions & Services

The integration exposes dedicated Home Assistant actions for automations, scripts, and dashboard buttons:

- **Remote Navigation & Playback**: `send_key`, `send_key_sequence` (multi-key sequences with delays), and `change_channel` (direct numeric live TV channel tuning).
- **App Launching**: `launch_app` (by name, app ID, or video deep-link URL).
- **Picture & Sound Modes**: `set_picture_setting` and `set_sound_setting` (direct hardware mode changes).
- **Virtual Keyboard**: `send_text_input` (inject search queries into onscreen inputs).

> For copy-paste YAML automation recipes, key tables, and service parameters, see the **[Services & Automations Guide](docs/services_and_automations.md)**.
---

## 🗑️ Removal & Uninstallation

To cleanly remove the Hisense VIDAA TV integration:
1. In Home Assistant, navigate to **Settings → Devices & Services**, locate **Hisense VIDAA TV**, click the three vertical dots (`⋮`), and select **Delete**.
2. Remove the component from **HACS → Integrations** (or delete `/config/custom_components/hisense_vidaa/`), then restart Home Assistant (`Settings` → `System` → `Restart`).

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

This integration is an independent implementation built upon foundational protocol reverse-engineering research and documentation by the open-source smart home community (including `mqtt-hisensetv` and community research into the Hisense RemoteNOW and VIDAA MQTT protocol).
