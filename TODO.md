# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks active pending tasks, investigations, and planned enhancements for the `hisense_vidaa` custom integration.

---

## 🎯 Active Tasks & Investigations

### 1. Firmware `Q0704`+ Live Verification & Telemetry ([Issue #6](https://github.com/stevene1919/hisense_vidaa/issues/6))
- [ ] **Community Verification with 4-Tier Auth Cascade**:
  - Test pairing on TV firmware builds with `transport_protocol` in the Middle tier (3000–3285) and Modern tier ($\ge 3290$) using the automated fallback cascade.
  - Verify whether TVs with full internal paired device storage benefit from clearing paired mobile devices in TV Settings (*Settings → System → Advanced Settings → Mobile App Connection / Paired Devices*).
  - Gather diagnostic probe output (`test_client.py probe`) from `Q0704`+ users.



