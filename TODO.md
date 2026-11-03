# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks active pending tasks, investigations, and future roadmap items for the `hisense_vidaa` integration.

---

## 🎯 Active Tasks & Real-World Investigations

### 1. Community Hardware Feedback & 4-Tier Auth Cascade ([Issue #6](https://github.com/stevene1919/hisense_vidaa/issues/6))
- [ ] **Real-World Verification Across Diverse Firmware**:
  - Gather and monitor community feedback on TV firmware builds in the Middle tier (3000–3285) and Modern tier (≥ 3290) using the automated fallback cascade.
  - Test pairing across various international regional models (UK, EU, US, Australia) with isolated VLANs where UPnP/mDNS is blocked.
  - Document whether TVs with full internal paired device memory benefit from clearing paired mobile devices in TV Settings (*Settings → System → Advanced Settings → Mobile App Connection / Paired Devices*).

### 2. Cold AC Power Interruption Empirical Testing
- [ ] **Physical Hardware Behavior Under Abrupt Mains Cut**:
  - Test physical behavior of TV and SoC when mains AC power is abruptly disconnected and restored (simulated blackout / wall switch cut).
  - Observe and document whether the TV restores to Cold Standby (screen off, network stack/broker uninitialized) or returns to active power state.
  - Determine if the TV reboots into Fast Power On (`fake_sleep`) or remains in cold standby until woken by physical remote, chassis button, or IR blaster pulse.
  - Evaluate integration handling, state transitions, reconnect behavior, and token persistence after cold AC boot once network connectivity resumes.

---

## 🗺️ Long-Term Roadmap & Future Enhancements

### 1. Universal VIDAA Rebranding Migration (`hisense_vidaa` → `vidaa`)
*Underlying multi-brand protocol support for Toshiba, Loewe, Philips/TPV, Schneider, etc., is fully active in v3.2.0 under the `hisense_vidaa` domain.*
- [ ] **Full Domain Migration Strategy**:
  - Evaluate future domain migration from `hisense_vidaa` to `vidaa` once partner brand testing matures.
  - Implement `async_migrate_entry` to seamlessly preserve existing entity unique IDs, area assignments, and custom entity customizations without breaking existing setups.
  - Alias legacy action services (`hisense_vidaa.send_key` → `vidaa.send_key`) with deprecation warnings to maintain automation backwards compatibility.
  - Refresh brand assets (`brand/`) with official universal VIDAA OS logos alongside partner sub-badges.

### 2. Home Assistant Core Upstream Submission
*The integration currently fulfills 100% of all 54 Integration Quality Scale rules (Bronze, Silver, Gold, Platinum) as tracked in `quality_scale.yaml`.*
- [ ] **Core Submission Readiness**:
  - Monitor stability of native `aiomqtt` engine and multi-brand cascade in production via HACS.
  - Coordinate upstream submission to `home-assistant/core` when appropriate.

---

## ✅ Completed Milestones Summary

For complete details on completed features and technical improvements, refer to the [Changelog](CHANGELOG.md):

* **v3.2.0**: Universal VIDAA OEM Multi-Brand Support (Toshiba, Loewe, TPV/Philips), candidate OEM brand handshake cascade on `rc: 5`, certificate filename brand detection, Device Options brand selector, and test suite modularization (240 unit tests).
* **v3.1.0**: Full architectural migration to native `aiomqtt>=2.3.0` async transport engine, shared `aiohttp.ClientSession` injection, multi-device service ambiguity guards, and 100% IQS rule compliance (`quality_scale.yaml`).
* **v3.0.0**: Live MQTT device registry enrichment, generic UPnP placeholder sanitization, dynamic MDI app/source icons, UPnP LAN control, zero-cost HTTP Date header clock drift detection, and diagnostic sensors.
* **v2.3.0**: Playback settle window / state debounce, multi-key sequence action (`send_key_sequence`), direct channel tuning (`change_channel`), multi-burst Wake-on-LAN, and cold-boot active signal recovery.
