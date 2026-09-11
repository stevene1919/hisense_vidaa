# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks planned features, technical debt, and device registry enhancements for the `hisense_vidaa` custom integration.

---

## 🚀 Planned Enhancements & Roadmap

### 1. Device Registry & Metadata Integration
- [ ] **Dynamic `DeviceInfo` Model & Firmware Binding**:
  - Pipe discovered UPnP/mDNS `model_name` or `model_code` (e.g. `55U7G`, `65U8N`) into `device_info["model"]` instead of static `"VIDAA TV"`.
  - Pipe discovered `firmware_version` into `device_info["sw_version"]` so the exact build shows on Home Assistant's Device info card.
  - Pipe discovered `manufacturer` / `brand` into `device_info["manufacturer"]` (e.g. `Hisense`, `Toshiba`).

### 2. Network, Cloud Endpoints & Connectivity Resilience
- [ ] **Cloud Endpoints & DNS Whitelist Investigation (as noted in README)**:
  - Capture outbound DNS queries and WAN traffic from the TV during initial pairing, PIN validation, and 48-hour token renewal (e.g. using `tcpdump` or AdGuard Home logs on `gw`).
  - Identify specific Hisense / VIDAA cloud endpoints, license validation servers, and NTP time servers required for authentication to succeed.
  - Document network whitelist rules / documentation guide in `docs/` for users with strict IoT VLAN firewalls or ad-blockers (AdGuard Home / Pi-hole).
- [ ] **Deep Sleep / Wi-Fi Disconnect Investigation ([Issue #13](https://github.com/stevene1919/hisense_vidaa/issues/13))**:
  - Investigate behavior when VIDAA OS enters low-power standby and powers down the Wi-Fi module.
  - Test periodic UPnP ping / keep-alive probe to prevent internal clock drift on offline reconnects.
  - Improve NTP recovery alerting when the TV internal clock desynchronizes.

### 3. Media & Control Features
- [ ] **Dynamic App Icon Mapping**: Map known VIDAA application IDs to high-resolution channel/app icons in Home Assistant.
- [ ] **Sound Mode & Picture Mode Controls**: Explore reverse-engineered MQTT topics for TV picture preset and sound output mode selection.
