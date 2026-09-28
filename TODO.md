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

### 7. Cold Power Cut & AC Restoration Empirical Testing
- [ ] **Empirical Testing of Cold AC Power Interruption**:
  - Test physical behavior of TV and SoC when mains AC power is abruptly disconnected and restored (simulated blackout / wall switch cut).
  - Observe and document whether the TV restores to Cold Standby (screen off, network stack/broker uninitialized) or returns to active power state.
  - Determine if the TV reboots into Fast Power On (`fake_sleep`) or remains in cold standby until woken by physical remote, chassis button, or IR blaster pulse.
  - Evaluate integration handling, state transitions, reconnect behavior, and token persistence after cold AC boot once network connectivity resumes.
  - Update documentation and integration logic based on empirical findings.

### 8. Google Home HA Integration Compatibility Testing
- [ ] **Home Assistant to Google Assistant Compatibility & Trait Verification**:
  - Set up and test exposure of the TV's `media_player` entity via Home Assistant's Google Assistant integration.
  - Verify mapping and real-time synchronization of Google traits (`OnOff`, `Volume`, `InputSelector`, `TransportControl`, `MediaState`).
  - Validate Google voice command responsiveness for power on/off (`KEY_POWER`), volume level/step adjustment, muting, and HDMI input/app source switching.
  - Test Google Home mobile app UI controls and state accuracy during standby, source transitions, and active playback.
  - Document any edge cases or recommended setup best practices for Google Home users in integration documentation.

