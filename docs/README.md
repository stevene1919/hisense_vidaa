# 📚 Hisense VIDAA Integration Documentation Index

Welcome to the technical documentation library for the **Hisense VIDAA TV Integration for Home Assistant**.

This directory contains in-depth documentation covering installation, networking, SSL certificates, protocol reverse-engineering, custom automations, and UI dashboard cards.

---

## 📖 Documentation Directory

| Document | Topic | Description |
| :--- | :--- | :--- |
| [**`protocol_architecture.md`**](protocol_architecture.md) | **Protocol & Cryptography** | Complete technical breakdown of the VIDAA MQTT protocol, MD5 hash formulas, 64-bit XOR masks, challenge-response pairing sequence, topic matrices, and firmware quirks. |
| [**`certificates.md`**](certificates.md) | **SSL & Certificates** | Guide for configuring mutual TLS (mTLS), recommended file locations (`/config/ssl/`), file naming conventions, and PKCS#12 (`.p12`/`.pfx`) automatic extraction. |
| [**`network_requirements.md`**](network_requirements.md) | **Networking & Firewall** | Port requirements (`36669`, `38400`, `18400`, `9`), isolated IoT VLAN firewall rules, subnet Wake-on-LAN routing, and mDNS/SSDP discovery prerequisites. |
| [**`services_and_automations.md`**](services_and_automations.md) | **Services & Automations** | Comprehensive reference for integration actions (`send_key`, `launch_app`, `set_picture_setting`, `set_sound_setting`, `send_text_input`) with copy-paste YAML automation recipes. |
| [**`lovelace_cards.md`**](lovelace_cards.md) | **Dashboard UI Cards** | Lovelace UI dashboard designs, custom TV remote controller cards, and media playback widgets. |
| [**`cli_tools.md`**](cli_tools.md) | **CLI Diagnostics Tool** | Guide for using the standalone `test_client.py` CLI utility to test network reachability, TLS handshakes, UPnP timestamps, and pairing without running Home Assistant. |
| [**`screenshots.md`**](screenshots.md) | **Visual Showcase** | Gallery of integration screenshots, entity platform views, and categorized options menus. |

---

## 🧭 Recommended Reading Paths

### 🚀 Getting Started & Setup
1. [**`certificates.md`**](certificates.md) — Learn where to place client certificates to ensure persistent connections across HACS updates.
2. [**`network_requirements.md`**](network_requirements.md) — Verify that your Home Assistant instance and TV can communicate across ports and VLANs.

### 🎮 Customization & Automations
1. [**`services_and_automations.md`**](services_and_automations.md) — Explore available services, key aliases, and automation patterns for movie modes, sleep timers, and game console input switching.
2. [**`lovelace_cards.md`**](lovelace_cards.md) — Copy pre-built TV remote and media dashboard cards into your Lovelace views.

### 🔬 Troubleshooting & Protocol Internals
1. [**`cli_tools.md`**](cli_tools.md) — Use `test_client.py ping` and `test-ssl` to diagnose connection, network, or authentication issues directly from terminal.
2. [**`protocol_architecture.md`**](protocol_architecture.md) — Understand how the four-tier auth cascade, token persistence, and MQTT topic routing operate under the hood.
