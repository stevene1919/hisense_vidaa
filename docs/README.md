# 📚 Hisense VIDAA Integration Documentation Index

Welcome to the technical documentation library for the **Hisense VIDAA TV Integration for Home Assistant**.

This directory contains in-depth documentation covering installation, networking, SSL certificates, protocol reverse-engineering, custom automations, and UI dashboard cards.

---

## 📖 Documentation Directory

| Document | Topic | Description |
| :--- | :--- | :--- |
| [**`quick_start_beginners.md`**](quick_start_beginners.md) | **🔰 Beginner's Quick Start** | 3-minute, zero-jargon setup guide for first-time users (extracting `El.p12`, placement, and pairing). |
| [**`parameters.md`**](parameters.md) | **Configuration, Diagnostics & Debugging** | Complete reference for all Config Flow and Options Flow parameters, built-in diagnostic entities, and Home Assistant debug logging/diagnostics procedures. |
| [**`power_and_standby_settings.md`**](power_and_standby_settings.md) | **TV Power & Standby** | Optimal TV settings across VIDAA versions (U4–U8, 2024+), two-tier standby architecture, and preventing volatile token wipes with HDMI sources. |
| [**`protocol_architecture.md`**](protocol_architecture.md) | **Protocol & Cryptography** | Complete technical breakdown of the VIDAA MQTT protocol, UPnP/DLNA LAN control, 64-bit XOR masks, challenge-response pairing, and multi-brand OEM ecosystem. |
| [**`certificates.md`**](certificates.md) | **SSL & Certificates** | Guide for configuring mutual TLS (mTLS), recommended file locations (`/config/ssl/`), file naming conventions, and PKCS#12 (`.p12`/`.pfx`) automatic extraction. |
| [**`network_requirements.md`**](network_requirements.md) | **Networking & Firewall** | Port requirements (`36669`, `38400`, `18400`, `9`), isolated IoT VLAN firewall rules, subnet Wake-on-LAN routing, and mDNS/SSDP discovery prerequisites. |
| [**`services_and_automations.md`**](services_and_automations.md) | **Services & Automations** | Comprehensive reference for integration actions (`send_key`, `launch_app`, `set_picture_setting`, `set_sound_setting`, `send_text_input`) with copy-paste YAML automation recipes. |
| [**`installation_advanced.md`**](installation_advanced.md) | **Advanced Installation & Lifecycle** | Direct Git cloning, submodules, tracking beta branches, venv setup, air-gapped VLAN installs, and clean uninstallation. |
| [**`lovelace_cards.md`**](lovelace_cards.md) | **Dashboard UI Cards** | Lovelace UI dashboard designs, custom TV remote controller cards, and media playback widgets. |
| [**`cli_tools.md`**](cli_tools.md) | **CLI Diagnostics Tool** | Guide for using the standalone `test_client.py` and `debug_tv.py` CLI utilities to test reachability, TLS handshakes, UPnP, and pairing without running Home Assistant. |
| [**`screenshots.md`**](screenshots.md) | **Visual Showcase** | Gallery of integration screenshots, entity platform views, and categorized options menus. |
| [**`troubleshooting.md`**](troubleshooting.md) | **Troubleshooting & Error Reference** | Action error resolution table, standby wake issues, pairing/token recovery, and network connectivity diagnostics. |

---

## 🧭 Recommended Reading Paths

### 🚀 Getting Started & Setup
1. [**`quick_start_beginners.md`**](quick_start_beginners.md) — 3-minute quick start for beginners (getting `El.p12` and pairing).
2. [**`certificates.md`**](certificates.md) — Advanced certificate reference for custom PEM keypairs and OpenSSL commands.
3. [**`network_requirements.md`**](network_requirements.md) — Verify that your Home Assistant instance and TV can communicate across ports and VLANs.
4. [**`power_and_standby_settings.md`**](power_and_standby_settings.md) — Configure your TV to prevent auto-standby token wipes when HDMI devices sleep.

### 🎮 Customization & Automations
1. [**`parameters.md`**](parameters.md) — Fine-tune heartbeat intervals, debounce delays, and WoL bursts in the Options Flow.
2. [**`services_and_automations.md`**](services_and_automations.md) — Explore available services, key aliases, and automation patterns for movie modes, sleep timers, and game console input switching.
3. [**`lovelace_cards.md`**](lovelace_cards.md) — Copy pre-built TV remote and media dashboard cards into your Lovelace views.

### 🔬 Troubleshooting & Protocol Internals
1. [**`parameters.md#4-home-assistant-debugging--diagnostics-guide`**](parameters.md#4-home-assistant-debugging--diagnostics-guide) — Enable real-time debug logging via `switch.<tv>_debug_logging` or `logger`, download sanitized HA diagnostics, and trigger repairs.
2. [**`cli_tools.md`**](cli_tools.md) — Use `test_client.py ping`, `upnp`, and `test-ssl` to diagnose connection, network, clock drift, or authentication issues directly from terminal.
3. [**`protocol_architecture.md`**](protocol_architecture.md) — Understand how the multi-tier auth cascade, UPnP LAN control, token persistence, and MQTT topic routing operate under the hood.

---

## 🏆 Integration Quality Scale

### 📺 Supported Devices & Brands
The integration officially supports **Hisense Smart TVs** running **VIDAA OS** (U4, U5, U6, U7, U8, and 2024+ builds), as well as all licensed **OEM partner smart TVs and projectors** operating on the VIDAA OS platform:
- **Televisions**: Hisense, Toshiba, Loewe (and We. by Loewe), TPV Technology (Philips & AOC), Sharp, JVC, Schneider, Akai, Beko, Telefunken, Bush, Vizio, Philco, Noblex, Sansei, RCA, Sinotec, Vestel, Brandt, Metz, Leica (Cine 1 Laser TV), Pioneer, Panasonic, and Seiki.
- **Smart Projectors**: TOPTRO portable smart projectors running VIDAA OS (e.g. FreeStyle series).
- **Zero-Configuration Auto-Detection**: Brand profiles default to **Auto Detect (Recommended)**, probing UPnP port `38400` / `18400` to automatically extract and resolve OEM branding from device descriptors, or matching certificate file hints without manual user configuration.

### ⚡ Data Update Model (Local Push)
This integration operates as a **pure local-push integration** (`should_poll = False`). It establishes a persistent local TLS connection over MQTT (port `36669`) directly to the television's internal broker. All state changes (power, volume, mute, source input, active app, TV channel, picture/sound modes) are received as real-time push events without network polling.

### 🎮 Supported Platforms & Entities
- **Media Player** (`media_player.<tv_name>`): Power, volume, mute, input source, app launcher, playback state, channel tuning, and sound mode.
- **Remote** (`remote.<tv_name>`): Send remote keys, directional navigation, volume, numbers, media playback.
- **Sensors & Binary Sensors** (`sensor.<tv_name>_*`, `binary_sensor.<tv_name>_*`): Clock drift, session status, connectivity, power.
- **Buttons, Switches, Selects, Numbers**: On-demand clock sync, force reconnect, trigger re-pairing, picture/sound settings adjustment, debug logging toggle.

### 💡 Real-World Use Cases & Automations
- **Home Theater Cinema Mode**: Automatically dim ambient lights when video playback starts (`state: playing`) on streaming apps (Netflix, Prime Video).
- **Auto HDMI Switcher**: Automatically switch receiver or audio output when switching to game consoles (HDMI 1/2) vs TV broadcast.
- **Sleep Timer & Night Mode**: Trigger bedtime automations to lower TV volume after 10 PM or switch picture mode to Night/Warm color profile.

### ⚠️ Known Limitations
- **Wi-Fi WoL Packet Dropping**: Waking TVs over Wi-Fi when in deep cold standby may require configuring Wake-on-LAN packet burst sequences in options.
- **Local Network Requirement**: Home Assistant and TV must reside on reachable local subnets (port 36669 TCP and port 38400 UDP).

### 🛠️ Troubleshooting Guide
- **Pairing PIN Failures**: Disconnect any running mobile app (RemoteNow/VIDAA app) before pairing.
- **Certificate Errors**: Place client certificate files in `/config/ssl/` or `/config/certs/` as detailed in [`certificates.md`](certificates.md).
- **Re-Authentication Prompt / Frequent Token Loss**: Verify that external streaming dongles (Chromecast, Fire TV, Roku) are powered by their dedicated wall AC adapter rather than the TV's USB port (which triggers brownouts and wipes RAM on standby), and ensure **Auto Standby with No Signal** is disabled in TV settings. Use Home Assistant Repairs or the re-configuration flow to refresh PIN auth if tokens are invalidated.
