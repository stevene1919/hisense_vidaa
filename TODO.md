# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks active pending tasks, investigations, and planned enhancements for the `hisense_vidaa` custom integration.

---

## 🎯 Active Tasks & Investigations

### 1. Firmware `Q0704`+ Live Verification & Telemetry ([Issue #6](https://github.com/stevene1919/hisense_vidaa/issues/6))
- [ ] **Community Verification with 4-Tier Auth Cascade**:
  - Test pairing on TV firmware builds with `transport_protocol` in the Middle tier (3000–3285) and Modern tier ($\ge 3290$) using the automated fallback cascade.
  - Verify whether TVs with full internal paired device storage benefit from clearing paired mobile devices in TV Settings (*Settings → System → Advanced Settings → Mobile App Connection / Paired Devices*).
  - Gather diagnostic probe output (`test_client.py probe`) from `Q0704`+ users.

### 2. Network, Cloud Endpoints & Connectivity Resilience
- [ ] **Cloud Endpoints & DNS Whitelist Investigation**:
  - Capture outbound DNS queries and WAN traffic from the TV during initial pairing, PIN validation, and 48-hour token renewal (e.g. using `tcpdump` or AdGuard Home logs on `gw`).
  - Identify specific Hisense / VIDAA cloud endpoints, license validation servers, and NTP time servers required for authentication to succeed.
  - Document network whitelist rules in `docs/network_requirements.md` for users with strict IoT VLAN firewalls or ad-blockers (AdGuard Home / Pi-hole).
- [ ] **Wi-Fi Network "Not Connected" Drop Investigation ([Issue #13](https://github.com/stevene1919/hisense_vidaa/issues/13))**:
  - Investigate why the TV's network state spontaneously dropped to "Not Connected" in TV settings (unrelated to standby/sleep or Wake-on-LAN).
  - Investigate why the TV's internal clock froze at `Mon, 07 Sep 2026 10:24:06 GMT` during the disconnected state and failed to update NTP until manually reconnected.
  - Improve error handling and diagnostic alerting when the TV internal clock desynchronizes from real time.


