# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks active pending tasks, investigations, and planned enhancements for the `hisense_vidaa` custom integration.

---

## 🎯 Active Tasks & Investigations

### 1. Firmware `Q0704`+ Live Verification & Telemetry ([Issue #6](https://github.com/stevene1919/hisense_vidaa/issues/6))
- [ ] **Community Verification with 4-Tier Auth Cascade**:
  - Test pairing on TV firmware builds with `transport_protocol` in the Middle tier (3000–3285) and Modern tier ($\ge 3290$) using the automated fallback cascade.
  - Verify whether TVs with full internal paired device storage benefit from clearing paired mobile devices in TV Settings (*Settings → System → Advanced Settings → Mobile App Connection / Paired Devices*).

### 2. Playback State Debounce & Settle Window (Priority 1)
- [ ] **Transient Playback State Filtering**:
  - Filter out sub-second state flickers (e.g. rapid cycling between buffering, idle, paused, and playing when launching streaming apps or transitioning between titles/ads).
  - Provide a smooth, stable media player state in Home Assistant to prevent lighting and media automations from falsely re-triggering during video buffering.
  - Make the debounce duration configurable in integration options.

### 3. Remote Key Command Sequences & Macros (Priority 2)
- [ ] **Multi-Key Sequence Service**:
  - Allow sending a list of remote key commands with configurable delays between each step in a single action.
  - Enable custom shortcuts and automations for navigating nested TV menus, launching picture adjustments, or accessing specific TV features with one click.

### 4. Direct Numerical Channel Tuning (Priority 3)
- [ ] **Direct TV Channel Selector**:
  - Add support for direct live TV channel tuning by channel number (e.g. entering channel 7, 70, or 701 directly).
  - Automatically dispatch the corresponding sequence of numeric keypresses to change channels seamlessly.

### 5. Dynamic App & Source Icon Branding (Priority 4)
- [ ] **Media Dashboard Source Icons**:
  - Automatically match active sources and installed Smart TV apps (Netflix, YouTube, Prime Video, Disney+, Plex, HDMI inputs) with corresponding high-resolution icons in dashboard cards.

### 6. Robust Wake-on-LAN Bursting & Power Recovery (Priority 5)
- [ ] **Multi-Burst Wake-on-LAN Power On**:
  - Configurable UDP packet burst sequences for waking TVs over Wi-Fi when low-power sleep modes drop initial packets.
  - Automatic fast-polling connection recovery after power-on triggers.
