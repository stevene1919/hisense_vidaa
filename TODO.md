# 📋 VIDAA Smart TV Integration Roadmap & TODO

This document tracks active pending tasks, investigations, and future roadmap items for the `vidaa` integration.

---

## 🚀 v3.5.0 Release & Rebrand Transition Tasks

### 1. GitHub Repository & HACS Rebrand Finalization

- [ ] **GitHub Repository Rename**:
  - Rename repository on GitHub from `stevene1919/hisense_vidaa` $\rightarrow$ `stevene1919/vidaa` (leveraging GitHub's automatic HTTP & Git redirection).
  - Update local Git remotes and submodule paths to point to canonical `stevene1919/vidaa`.
- [ ] **Release Tagging & Publishing**:
  - Create Git tag `v3.5.0` and publish the release on GitHub with attached `vidaa.zip` distribution archive.
  - Review automated release workflow (`.github/workflows/release.yml`) asset creation and hash generation.
- [ ] **HACS Catalog Update**:
  - Submit / update repository metadata in the HACS Default store (`hacs/default`) to reflect the new repository name and `VIDAA Smart TV` branding.
- [ ] **Post-Release Migration Monitoring**:
  - Monitor community feedback on automatic entry migration (`v1` $\rightarrow$ `v2.1`).
  - Verify legacy folder collision repair issue properly alerts users with obsolete `custom_components/hisense_vidaa` folders.

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

### 1. Home Assistant Core Upstream Submission

*The integration currently fulfills 100% of all 54 Integration Quality Scale rules (Bronze, Silver, Gold, Platinum) as tracked in `quality_scale.yaml`.*

- [ ] **Core Submission Readiness**:
  - Monitor stability of native `aiomqtt` engine and multi-brand cascade in production via HACS.
  - Coordinate upstream submission to `home-assistant/core` when appropriate.

---

## ✅ Completed Milestones Summary

For complete details on completed features and technical improvements, refer to the [Changelog](CHANGELOG.md):

* **v3.5.0**:
  - **Universal VIDAA Rebranding (`vidaa`)**: Renamed integration domain to `vidaa` (VIDAA Smart TV), deployed official brand assets and icons, rebranded UI strings and translations, refactored symbols to `Vidaa*` with legacy aliases.
  - **Zero-Breaking-Change Migration**: Built automated config entry migration (v1 -> v2.1), preserving entity registries, unique IDs, and area assignments. Maintained `hisense_vidaa.*` actions, device trigger compatibility, and transitional shim.
  - **HDMI-CEC Input Discovery & Clean Attributes**: Source dropdown and active source sensors discover and display friendly CEC names for all connected inputs (`HDMI 1 (Chromecast)`), allowing direct input selection by device name with clean `raw_source` and `connected_device` attributes.
  - **Streamlined Audio Output Attribute**: Replaced unsupported select/sensor entities with clean `audio_output` attribute (`TV Speakers` or `ARC / eARC`) on the media player entity.
  - **Transport Controls Disabled by Default**: Kept media player cards sleek by defaulting `enable_media_controls` to false, with full user toggle in Options Flow.
  - **Home Launcher Detection & Clock Sync (#58, #59)**: Added `remote_launcher` state tracking for Home screen navigation and offloaded fallback clock sync to thread.
  - **Duplicate IP Discovery Guard**: SSDP / UPnP discovery now checks for existing configured IP addresses and aborts if an entry for that TV already exists.
  - **Virtual Keyboard Input Support**: Extended `remote.send_command` with prefix parsing (`text:<str>`, `type:<str>`, `text:replace:<str>`, `clear_text`) and added CLI text commands to `test_client.py` and `debug_tv.py`.
  - **Web Browser Mouse & Pointer Integration**: Documented browser-specific mouse controls (`mouse_click`, `mouse_up`, `mouse_down`, `zoom_in`, `zoom_out`) and clarified the browser-only cursor scope from APK reverse-engineering.
  - **Removal of Unsupported Notify Platform**: Deprecated speculative `notify` platform and options toggle after companion APK decompilation confirmed notifications are an in-app mobile promotion feed with no TV compositor listener. Pruned legacy entity registry entries on setup.
  - **Media Player UI Controls (#55)**: Restored persistent visibility for previous/next track and channel navigation buttons in the Home Assistant media player card.
  - **Auto Power-On on Source/App Select**: Selecting a source or playing media while the TV is off/standby automatically turns on the TV.
  - **Home Assistant Standards & Attribute Alignment**: Aligned entity titles to HA device prefixing, added native `app_name`/`app_id` properties, pruned redundant hardware attributes from `media_player`, consolidated diagnostic sensors into `sensor.<tv>_session_status`, and filtered physical input sensors.
  - **Incremental Settings Broadcast Preservation**: Preserves menu metadata and option trees when single-item `notify_value_changed` updates arrive from the TV remote.
  - **Comprehensive Documentation Rebrand**: Fully audited and updated all 19 documentation guides, configuration parameter references, network and standby guides, and multilingual READMEs to canonical `vidaa.*` actions and `vidaa.turn_on` triggers.
* **v3.3.0**: Context-aware channel track controls (Previous/Next track steps channels on Live TV, skips tracks on Apps/HDMI), HDMI container false-positive guard (`is_live_tv_source`), channel name matching in `play_media`, user-configurable source filtering in Options Flow (`CONF_SOURCES`), `PluggableAction` turn-on device automations, candidate toast notification probing, and full Serbian translations (294 unit tests).
* **v3.2.0**: Universal VIDAA OEM Multi-Brand Support (Hisense, Toshiba, Loewe, Philips/TPV, Sharp, JVC, and regional partners), candidate OEM brand handshake cascade on `rc: 5`, certificate filename brand detection, post-PIN brand preservation fix, automatic credential regeneration on brand changes, Device Options & Manual IP brand selector, UPnP MAC fallback support, and comprehensive modular test suite (246 unit tests).
* **v3.1.0**: Full architectural migration to native `aiomqtt>=2.3.0` async transport engine, shared `aiohttp.ClientSession` injection, multi-device service ambiguity guards, and 100% IQS rule compliance (`quality_scale.yaml`).
* **v3.0.0**: Live MQTT device registry enrichment, generic UPnP placeholder sanitization, dynamic MDI app/source icons, UPnP LAN control, zero-cost HTTP Date header clock drift detection, and diagnostic sensors.
* **v2.3.0**: Playback settle window / state debounce, multi-key sequence action (`send_key_sequence`), direct channel tuning (`change_channel`), multi-burst Wake-on-LAN, and cold-boot active signal recovery.
