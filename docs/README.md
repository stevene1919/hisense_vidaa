# 📚 Hisense VIDAA Integration Documentation Index

Welcome to the technical documentation library for the **Hisense VIDAA TV Integration for Home Assistant**.

This directory contains in-depth documentation covering installation, networking, SSL certificates, protocol reverse-engineering, custom automations, and UI dashboard cards.

---

## 📖 Documentation Directory

| [**`parameters.md`**](parameters.md) | **Configuration, Diagnostics & Debugging** | Complete reference for all Config Flow and Options Flow parameters, built-in diagnostic entities, and Home Assistant debug logging/diagnostics procedures. |
| [**`power_and_standby_settings.md`**](power_and_standby_settings.md) | **TV Power & Standby** | Optimal TV settings across VIDAA versions (U4–U8, 2024+), two-tier standby architecture, and preventing volatile token wipes with HDMI sources. |
| [**`protocol_architecture.md`**](protocol_architecture.md) | **Protocol & Cryptography** | Complete technical breakdown of the VIDAA MQTT protocol, UPnP/DLNA LAN control, 64-bit XOR masks, challenge-response pairing, and multi-brand OEM ecosystem. |
| [**`certificates.md`**](certificates.md) | **SSL & Certificates** | Guide for configuring mutual TLS (mTLS), recommended file locations (`/config/ssl/`), file naming conventions, and PKCS#12 (`.p12`/`.pfx`) automatic extraction. |
| [**`network_requirements.md`**](network_requirements.md) | **Networking & Firewall** | Port requirements (`36669`, `38400`, `18400`, `9`), isolated IoT VLAN firewall rules, subnet Wake-on-LAN routing, and mDNS/SSDP discovery prerequisites. |
| [**`services_and_automations.md`**](services_and_automations.md) | **Services & Automations** | Comprehensive reference for integration actions (`send_key`, `launch_app`, `set_picture_setting`, `set_sound_setting`, `send_text_input`) with copy-paste YAML automation recipes. |
| [**`removal.md`**](removal.md) | **Removal & Uninstallation** | Step-by-step uninstallation instructions, device deletion, certificate cleanup, and HACS removal. |
| [**`lovelace_cards.md`**](lovelace_cards.md) | **Dashboard UI Cards** | Lovelace UI dashboard designs, custom TV remote controller cards, and media playback widgets. |
| [**`cli_tools.md`**](cli_tools.md) | **CLI Diagnostics Tool** | Guide for using the standalone `test_client.py` and `debug_tv.py` CLI utilities to test reachability, TLS handshakes, UPnP, and pairing without running Home Assistant. |
| [**`screenshots.md`**](screenshots.md) | **Visual Showcase** | Gallery of integration screenshots, entity platform views, and categorized options menus. |

---

## 🧭 Recommended Reading Paths

### 🚀 Getting Started & Setup
1. [**`certificates.md`**](certificates.md) — Learn where to place client certificates to ensure persistent connections across HACS updates.
2. [**`network_requirements.md`**](network_requirements.md) — Verify that your Home Assistant instance and TV can communicate across ports and VLANs.
3. [**`power_and_standby_settings.md`**](power_and_standby_settings.md) — Configure your TV to prevent auto-standby token wipes when HDMI devices sleep.

### 🎮 Customization & Automations
1. [**`parameters.md`**](parameters.md) — Fine-tune heartbeat intervals, debounce delays, and WoL bursts in the Options Flow.
2. [**`services_and_automations.md`**](services_and_automations.md) — Explore available services, key aliases, and automation patterns for movie modes, sleep timers, and game console input switching.
3. [**`lovelace_cards.md`**](lovelace_cards.md) — Copy pre-built TV remote and media dashboard cards into your Lovelace views.

### 🔬 Troubleshooting & Protocol Internals
1. [**`parameters.md#4-home-assistant-debugging--diagnostics-guide`**](parameters.md#4-home-assistant-debugging--diagnostics-guide) — Enable real-time debug logging via `switch.<tv>_debug_logging` or `logger`, download sanitized HA diagnostics, and trigger repairs.
2. [**`cli_tools.md`**](cli_tools.md) — Use `test_client.py ping`, `upnp`, and `test-ssl` to diagnose connection, network, clock drift, or authentication issues directly from terminal.
3. [**`protocol_architecture.md`**](protocol_architecture.md) — Understand how the multi-tier auth cascade, UPnP LAN control, token persistence, and MQTT topic routing operate under the hood.

---

## 🏆 Integration Quality Scale (Gold Tier) Reference

### 📺 Supported Devices & Brands
The integration supports all Smart TVs running **VIDAA OS** (U4, U5, U6, U7, U8, and 2024+ builds) across Hisense and licensed OEM manufacturers:
- **Hisense** (All Smart TV models)
- **Toshiba** (VIDAA OS models)
- **Loewe** (VIDAA OS models)
- **Schneider**, **Akai**, **Beko**, **Telefunken**, **Bush**

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
- **Re-Authentication Prompt**: Use Home Assistant Repairs or the re-configuration flow to refresh PIN auth when TV tokens are invalidated.
