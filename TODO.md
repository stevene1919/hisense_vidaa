# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks planned features, new platforms, technical debt, and architectural enhancements for the `hisense_vidaa` custom integration.

---

## 🚀 Planned Enhancements & Roadmap

### 1. Device Registry & Metadata Integration
- [x] **Dynamic `DeviceInfo` Model & Firmware Binding**:
  - Pipe discovered UPnP/mDNS `model_name` or `model_code` (e.g. `55U7G`, `65U8N`) into `device_info["model"]` instead of static `"VIDAA TV"`.
  - Pipe discovered `firmware_version` into `device_info["sw_version"]` so the exact build shows on Home Assistant's Device info card.
  - Pipe discovered `manufacturer` / `brand` into `device_info["manufacturer"]` (e.g. `Hisense`, `Toshiba`).

### 2. Auto-Discovery & Dynamic Network Migration (`ssdp` / `zeroconf`)
- [x] **Native Home Assistant SSDP / mDNS Auto-Discovery**:
  - Implement `async_step_ssdp` and `async_step_zeroconf` in `config_flow.py` for 1-click discovery notifications in Home Assistant UI when a new TV is detected.
- [x] **Dynamic IP Address Migration**:
  - Automatically update Config Entry host IP when TV DHCP IP changes by tracking the hardware MAC address via ARP/mDNS without breaking entities.

### 3. Diagnostic & State Sensors (`sensor`, `binary_sensor`, `button`)
- [x] **Diagnostic Sensors (`sensor` / `binary_sensor`)**:
  - `sensor.<tv>_token_expires_in`: Expiration timestamp / time remaining for the 48-hour access token (`device_class: timestamp`, `category: diagnostic`).
  - `sensor.<tv>_auth_profile`: Active authentication profile name (`Modern VIDAA 2.0`, `RemoteNOW Standard`, or `Legacy Static`).
  - `binary_sensor.<tv>_mqtt_connected`: Real-time broker connectivity status (`device_class: connectivity`, `category: diagnostic`).
- [x] **Operational Media Sensors (`sensor`)**:
  - `sensor.<tv>_active_app`: Dedicated sensor reporting currently active foreground app (e.g., `Netflix`, `YouTube`, `Prime Video`, `Live TV`).
  - `sensor.<tv>_active_source`: Currently active physical input (`HDMI 1`, `HDMI 2 (eARC)`, `TV`, etc.).
- [x] **Diagnostic Utility Buttons (`button`)**:
  - `button.<tv>_refresh_token`: Manual trigger to synchronously refresh session tokens and persist to Config Entry (`category: diagnostic`).
  - `button.<tv>_force_reconnect`: Forces immediate MQTT reconnection and subscription re-registration (`category: diagnostic`).
  - `button.<tv>_sync_clock`: Probes UPnP `Date` header to verify and re-align TV clock time.
- [x] **Native HA Diagnostics & Repairs Platforms (`diagnostics.py`, `repairs.py`)**:
  - Downloadable redacted diagnostics json via HA device card.
  - Automatic repair issue creation when client certificates are missing with guided in-UI fix flow.
- [x] **Custom Services (`services.yaml`)**:
  - `hisense_vidaa.send_key`: Fast burst keypresses with configurable repetition and delay.
  - `hisense_vidaa.launch_app`: App launcher by name or direct deep link URL.

### 4. Advanced Remote & Media Controls
- [ ] **Long-Press & Key Hold Support**:
  - Support `hold_secs` or repeated burst keypresses in `remote.send_command` for fast menu scrolling and long-press actions (e.g. holding `KEY_HOME` for app switcher or holding `KEY_POWER` for full shutdown).
- [ ] **App Deep Linking (`media_player.play_media`)**:
  - Support launching specific apps or video URLs directly (e.g. YouTube / Netflix deep links) via VIDAA app launcher topics.
- [ ] **On-Screen Toast Notifications (`notify` platform)**:
  - Explore reverse-engineered VIDAA UI topics to display on-screen text banners (e.g., doorbell/camera alerts).
- [ ] **Sound Mode & Picture Mode Controls**:
  - Explore reverse-engineered MQTT topics for TV picture preset and sound output mode selection.

### 5. Network, Cloud Endpoints & Connectivity Resilience
- [ ] **Cloud Endpoints & DNS Whitelist Investigation (as noted in README)**:
  - Capture outbound DNS queries and WAN traffic from the TV during initial pairing, PIN validation, and 48-hour token renewal (e.g. using `tcpdump` or AdGuard Home logs on `gw`).
  - Identify specific Hisense / VIDAA cloud endpoints, license validation servers, and NTP time servers required for authentication to succeed.
  - Document network whitelist rules / documentation guide in `docs/` for users with strict IoT VLAN firewalls or ad-blockers (AdGuard Home / Pi-hole).
- [ ] **Wi-Fi Network "Not Connected" Drop Investigation ([Issue #13](https://github.com/stevene1919/hisense_vidaa/issues/13))**:
  - Investigate why the TV's network state spontaneously dropped to "Not Connected" in TV settings (unrelated to standby/sleep or Wake-on-LAN).
  - Investigate why the TV's internal clock froze at `Mon, 07 Sep 2026 10:24:06 GMT` during the disconnected state and failed to update NTP until manually reconnected.
  - Improve error handling and diagnostic alerting when the TV internal clock desynchronizes from real time.

### 6. Automated Testing & CI
- [x] **Mock TV MQTT & Unit Test Suite**:
  - Added in-process mock protocol test suite (`tests/test_client_auth.py`, `tests/test_client_state.py`, `tests/test_crypto.py`, `tests/test_discovery.py`, `tests/test_entities.py`, `tests/test_diagnostics.py`, `tests/test_repairs.py`, `tests/test_config_flow.py`) and GitHub Actions test workflow (`.github/workflows/test.yml`).

### 7. Security Hardening & Best Practices
- [x] **Safe XML Parsing with `defusedxml` ([Issue #14](https://github.com/stevene1919/hisense_vidaa/issues/14))**:
  - Import `defusedxml.ElementTree` with fallback to standard `xml.etree.ElementTree` in `discovery.py` to guard against XML entity expansion on UPnP port 38400.
