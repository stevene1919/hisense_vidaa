# 📚 Hisense VIDAA Integration Documentation Index

Welcome to the technical documentation library for the **Hisense VIDAA TV Integration for Home Assistant**.

This directory contains in-depth documentation covering installation, networking, SSL certificates, protocol reverse-engineering, custom automations, and UI dashboard cards.

---

## 📖 Documentation Directory

| [**`parameters.md`**](parameters.md) | **Configuration & Options** | Complete reference for all Config Flow and Options Flow parameters (network timings, WoL bursts, certificate provisioning, SSL verification). |
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
1. [**`cli_tools.md`**](cli_tools.md) — Use `test_client.py ping` and `test-ssl` to diagnose connection, network, or authentication issues directly from terminal.
2. [**`protocol_architecture.md`**](protocol_architecture.md) — Understand how the multi-tier auth cascade, UPnP LAN control, token persistence, and MQTT topic routing operate under the hood.
