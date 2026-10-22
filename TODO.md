# 📋 Hisense VIDAA Integration Roadmap & TODO

This document tracks active pending tasks, investigations, and planned enhancements for the `hisense_vidaa` custom integration.

---

## 🎯 Active Tasks & Investigations

### 1. Firmware `Q0704`+ Live Verification & Telemetry ([Issue #6](https://github.com/stevene1919/hisense_vidaa/issues/6))

- [x] **Connection & Re-Auth Conflict Resolution**:
  - Automatically disconnect running background MQTT client before initiating interactive PIN pairing flow to eliminate socket collisions during reauth.
  - Explicitly recognize MQTT v5 Connack reason codes `134` (Bad user name or password) and `135` (Not authorized) to immediately trigger repair issue / reauth rather than spinning in exponential reconnect loops.
  - Eliminated erroneous boot-up pairing prompts by removing premature `gettvstate` queries during early setup and debouncing startup status queries.
- [ ] **Community Verification with 4-Tier Auth Cascade**:
  - Test pairing on TV firmware builds with `transport_protocol` in the Middle tier (3000–3285) and Modern tier ($\ge 3290$) using the automated fallback cascade.
  - Verify whether TVs with full internal paired device storage benefit from clearing paired mobile devices in TV Settings (*Settings → System → Advanced Settings → Mobile App Connection / Paired Devices*).

### 2. Playback State Debounce & Settle Window

- [x] **Transient Playback State Filtering**:
  - Filter out sub-second state flickers (e.g. rapid cycling between buffering, idle, paused, and playing when launching streaming apps or transitioning between titles/ads).
  - Provide a smooth, stable media player state in Home Assistant to prevent lighting and media automations from falsely re-triggering during video buffering.
  - Make the debounce duration configurable in integration options (`playback_debounce` with default 0.5s).

### 3. Remote Key Command Sequences & Macros

- [x] **Multi-Key Sequence Service (`hisense_vidaa.send_key_sequence`)**:
  - Allow sending a list of remote key commands with configurable delays between each step in a single action.
  - Enable custom shortcuts and automations for navigating nested TV menus, launching picture adjustments, or accessing specific TV features with one click.
  - Supports sequence lists or comma-delimited strings with schema validation and error wrapping.

### 4. Direct Numerical Channel Tuning

- [x] **Direct TV Channel Selector (`hisense_vidaa.change_channel`)**:
  - Add support for direct live TV channel tuning by channel number (e.g. entering channel 7, 70, or 701 directly).
  - Automatically dispatch the corresponding sequence of numeric keypresses to change channels seamlessly with optional `confirm: true` (`KEY_OK`).

### 5. Dynamic App & Source Icon Branding

- [ ] **Media Dashboard Source Icons**:
  - Automatically match active sources and installed Smart TV apps (Netflix, YouTube, Prime Video, Disney+, Plex, HDMI inputs) with corresponding high-resolution icons in dashboard cards.

### 6. Robust Wake-on-LAN Bursting & Power Recovery

- [x] **Multi-Burst Wake-on-LAN Power On**:
  - Configurable UDP packet burst sequences for waking TVs over Wi-Fi when low-power sleep modes drop initial packets.
  - Automatic fast-polling connection recovery after power-on triggers.

### 7. Cold Power Cut & AC Restoration Empirical Testing

- [x] **Cold-Boot Active Signal Recovery (`media_player.py`, `tv/media.py`)**:
  - Implemented `is_signal == 1` evaluation in incoming sourcelist telemetry to promptly transition media player state to `ON` when the TV boots from cold standby onto an active HDMI input or TV tuner before full UI state telemetry is broadcast.
  - Added unit test coverage for cold-boot signal recovery across disconnected and standby states.
- [ ] **Empirical Testing of Cold AC Power Interruption**:
  - Test physical behavior of TV and SoC when mains AC power is abruptly disconnected and restored (simulated blackout / wall switch cut).
  - Observe and document whether the TV restores to Cold Standby (screen off, network stack/broker uninitialized) or returns to active power state.
  - Determine if the TV reboots into Fast Power On (`fake_sleep`) or remains in cold standby until woken by physical remote, chassis button, or IR blaster pulse.
  - Evaluate integration handling, state transitions, reconnect behavior, and token persistence after cold AC boot once network connectivity resumes.
  - Update documentation and integration logic based on empirical findings.

### 8. Google Home HA Integration Compatibility Testing

- [x] **Home Assistant to Google Assistant Compatibility & Trait Verification**:
  - Set up and test exposure of the TV's `media_player` entity via Home Assistant's Google Assistant integration.
  - Verify mapping and real-time synchronization of Google traits (`OnOff`, `Volume`, `InputSelector`, `TransportControl`, `MediaState`).
  - Validate Google voice command responsiveness for power on/off (`KEY_POWER`), volume level/step adjustment, muting, and HDMI input/app source switching.
  - Test Google Home mobile app UI controls and state accuracy during standby, source transitions, and active playback.
  - Document any edge cases or recommended setup best practices for Google Home users in integration documentation.

### 9. Diagnostics Redaction & Sensitive Data Audit

- [x] **Diagnostics Payload Sanitization Verification (`diagnostics.py`)**:
  - Audit exported diagnostic payload to verify that client certificates, private key paths, refresh tokens, access tokens, and MAC addresses are 100% masked before export.
  - Expanded `TO_REDACT` set with `ssl_cert`, `ssl_key`, `p12_path`, `p12_password`, `client_cert_path`, `client_key_path`.
  - Ensure compatibility with official Home Assistant diagnostics download format and sanitization standards.

### 10. Multi-Language Localization & Translation Support

- [x] **Popular European & Regional Language Support (`translations/`)**:
  - Add native translated string dictionaries for high-adoption Hisense VIDAA smart TV markets:
    - **Spanish (`es.json`)**: Spain & Latin America.
    - **German (`de.json`)**: Germany, Austria, Switzerland.
    - **French (`fr.json`)**: France, Belgium, Canada.
    - **Italian (`it.json`)**: Italy.
    - **Portuguese (`pt.json` / `pt-BR.json`)**: Brazil & Portugal.
  - Maintain 100% key parity with master `strings.json` across config flows, options flows, entity states, repairs, and exception descriptions.
  - Evaluate setting up a free open-source Crowdin project for ongoing community localization.

### 11. Rebranding as Universal VIDAA Integration & Multi-Brand Architecture

- [ ] **Multi-Brand VIDAA OS Pairing & Authentication (`crypto.py`, `client.py`, `flow_discovery.py`)**:
  - Parameterize the brand identifier across the pairing handshake instead of hardcoding `"his"`:
    - **Client ID**: Format as `{mac}${brand}${hash[:6]}_vidaacommon_{suffix}` in `crypto.py`.
    - **Username**: Format as `{brand}${timestamp}` or `{brand}${timestamp ^ XOR_TIMESTAMP_MASK}`.
    - **Password Hash**: Generate using `{brand}{cross_sum_digit}{salt}`.
  - Propagate `brand` into `HisenseTvClient` and store `self.brand` (defaulting to `"his"`).
  - Extract and persist `brand` in `flow_discovery.py` from SSDP/UPnP discovery XML metadata (`device_info.get("brand")`), falling back to `"his"` for manual entry.
  - Enable seamless pairing for OEM television brands running licensed VIDAA OS (e.g. Toshiba, Loewe, Schneider, Akai, Beko, Telefunken, Bush).

- [x] **Namespace & Ecosystem Conflict Analysis**:
  - Investigated potential domain conflicts with existing community custom integrations (`warrenrees/ha_vidaatv` which targets `vidaa` / `vidaatv`, and `vidaa4ha`).
  - Evaluated HACS default registry and domain uniqueness: decided on preserving `hisense_vidaa` internal domain with friendly rebrand to avoid breaking existing entity IDs, HACS tracking, and automations.
- [x] **Multi-Brand Architecture Documentation (`docs/protocol_architecture.md`)**:
  - Reverse-engineered and documented OEM VIDAA implementations across brands (Toshiba, Loewe, Schneider, Akai, Beko, Telefunken, Bush).
- [ ] **Integration Rebranding Strategy Implementation (`hisense_vidaa` → `vidaa`)**:
  - **Objective**: Transition branding from Hisense-specific to the universal OS name (**VIDAA Smart TV**) to natively welcome all licensed television manufacturers under one integration.
  - **Backwards Compatibility & Migration Path**:
    - If migrating domain: implement `async_migrate_entry` to preserve entity unique IDs, area assignments, and custom entity customizations.
    - Alias legacy action services (e.g., forward `hisense_vidaa.send_key` calls to `vidaa.send_key` with a deprecation warning) to avoid breaking user automations.
    - Dynamically set `DeviceInfo(manufacturer=...)` from discovery XML (`"Hisense"`, `"Toshiba"`, `"Loewe"`, etc.) instead of hardcoded `"Hisense"`.
  - **Brand Assets & Translation Refresh**:
    - Update `brand/` icons and logos to feature the official VIDAA OS branding alongside OEM sub-logos.
    - Update documentation, repository metadata, and HACS category descriptions.

### 12. UPnP / DLNA LAN Control Subsystem

- [x] **Asynchronous UPnP Client (`protocol/upnp.py`)**:
  - Implemented `HisenseUpnpClient` supporting default port `38400` with fallback to `18400`.
  - Added `RenderingControl:1` SOAP actions for instantaneous, unauthenticated volume and mute control (`GetVolume`, `SetVolume`, `GetMute`, `SetMute`) directly on the hardware amplifier without MQTT/TLS overhead.
  - Added `AVTransport:1` SOAP actions for media transport status and playback tracking (`GetTransportInfo`, `Play`, `Pause`, `Stop`).
  - Added reverse-engineered proprietary `LanControlInfo:1` service (`GetLanControlInfo`, `SetLanControlInfo`).
  - Implemented non-blocking async capability probing (`async_probe()`) to detect active services without blocking the event loop.

### 13. Zero-Cost Clock Drift Detection & Hardware RTC Mitigation

- [x] **HTTP `Date` Header Clock Synchronization**:
  - Extracted TV system time from standard RFC 7231 `Date:` HTTP headers in UPnP responses.
  - Automatically calculates host-to-TV clock offset without generating external NTP traffic, securing dynamic MQTT username hashing across networks.
- [x] **Diagnostic Sensor Hardening (`sensors_diagnostic.py`)**:
  - Guarded `HisenseVidaaClockDriftSensor` against `None` offsets (`if offset is None: return None`) to avoid `TypeError` on early boot.
  - Added human-readable drift attributes and dynamic icons (`mdi:clock-check-outline` vs `mdi:clock-alert-outline`).
- [x] **Network NTP DNAT Port Redirection Documentation (`docs/network_requirements.md`)**:
  - Documented router-level NTP redirection rules (`UDP 123` via OpenWrt UCI, nftables, iptables, OPNsense) to prevent clock drift on televisions lacking hardware RTC batteries when placed on isolated IoT VLANs without internet access.

### 14. CLI Diagnostics & Shared Probing Parity

- [x] **Consolidated UPnP Diagnostics in Core CLI Tools**:
  - Re-exported shared `probe_upnp_services(ip, verbose)` from `tv/fingerprint.py` and `discovery.py`.
  - Added `test_client.py upnp` action and integrated hardware clock & drift reporting in `test_client.py ping`.
  - Added `--probe-upnp` flag and clock synchronization reporting to `debug_tv.py`.
  - Removed redundant standalone `scripts/test_upnp.py` and pruned from `.gitignore`.

### 15. Home Assistant Debugging & Diagnostics Guide

- [x] **Comprehensive HA Debug Documentation (`docs/parameters.md`, `docs/README.md`)**:
  - Documented all diagnostic entities: `button.sync_clock`, `button.force_reconnect`, `button.trigger_re_pairing`, `sensor.clock_drift`, `sensor.session_status`, `switch.debug_logging`.
  - Added step-by-step instructions for 4 debugging methods: on-the-fly via entity switch, UI integration menu, `configuration.yaml` `logger:`, and `logger.set_level` action.
  - Documented official sanitized diagnostics bundle download, privacy masks, and repairs flow.

### 16. Device Registry Metadata & Manufacturer Branding Normalization (`discovery.py`, `entity.py`, `client.py`)

- [x] **Sanitize Generic Manufacturer Placeholders in Discovery (`discovery.py`)**:
  - Many Hisense VIDAA televisions hardcode `<manufacturer>SmartTV</manufacturer>` and `<manufacturerURL>http://www.smarttv.com</manufacturerURL>` in their embedded UPnP DLNA MediaRenderer descriptor (`/MediaServer/rendererdevicedesc.xml`), causing Home Assistant to display `58A5FX by SmartTV` in the device card.
  - In `parse_ssdp_discovery`, detect generic placeholder manufacturers (`"SmartTV"`, `"Smart TV"`, or empty strings) and cross-reference the `#CAP#` block's `brand` attribute (e.g. `brand=his` -> `"Hisense"`, `brand=tos` -> `"Toshiba"`, `brand=loe` -> `"Loewe"`) to assign the true manufacturer brand.
- [x] **Live MQTT Device Registry Enrichment (`entity.py`, `client.py`, `coordinator.py`)**:
  - Dynamically populate `model`, `manufacturer`, and `sw_version` in `DeviceInfo` using live telemetry received over MQTT from `platform_service/data/getdeviceinfo` (`model_name`, `tv_version`) and `platform_service/data/gettvinfo` (`brand`, `uVersion`), rather than relying exclusively on static config entry data.
  - Call Home Assistant's `async_update_device` upon receiving the first `getdeviceinfo` payload to enrich the device registry with the TV's official firmware build (e.g. `V0000.06.30T.N0921` / `U6.1.0`) and exact model number (`58A53FXVT`).


---

## 🏆 Home Assistant Integration Quality Scale Tracking

Tracking adherence to the official [HA Integration Quality Scale rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules) as of **October 2026** (`manifest.json` declares `"quality_scale": "gold"`).

> **Note on tier shuffles:** The IQS rules have been updated since the initial tracking below was written. Notably: `test-coverage` moved from Gold → Silver, `diagnostics` and `entity-category` moved from Silver/Bronze → Gold, and `entity-category` and `entity-disabled-by-default` are now Gold. Several new rules were added at Bronze (`action-setup`, `config-flow-test-coverage`, `dependency-transparency`, `docs-*`, `entity-event-setup`, `runtime-data`, `test-before-configure`, `unique-config-entry`) and Gold (`dynamic-devices`, `stale-devices`, `entity-device-class`, `docs-*`). Platinum adds `async-dependency` and `inject-websession`.

---

### 🥉 Bronze Tier — Status: ✅ 100% complete

| Rule                                                                                                                                              | Status   | Notes                                                                                                          |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| [`action-setup`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup)                                     | ✅ Done   | Services registered in `async_setup` via `services.py`                                                         |
| [`appropriate-polling`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling)                       | ✅ Exempt | `should_poll = False`; pure local push via MQTT                                                                |
| [`brands`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/brands)                                                 | ✅ Done   | Brand assets in `brand/` directory                                                                             |
| [`common-modules`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/common-modules)                                 | ✅ Done   | Standard entity platforms + shared `entity.py`, `const.py`, `coordinator` pattern                              |
| [`config-flow`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow)                                       | ✅ Done   | Full UI config flow in `config_flow.py`                                                                        |
| [`config-flow-test-coverage`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage)           | ✅ Done   | `tests/test_config_flow.py` covers full config flow paths                                                      |
| [`dependency-transparency`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dependency-transparency)               | ✅ Done   | `requirements` pinned in `manifest.json` (`defusedxml`, `paho-mqtt`, `cryptography`)                           |
| [`docs-actions`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-actions)                                     | ✅ Done   | Documented in `README.md` and dedicated [`docs/services_and_automations.md`](docs/services_and_automations.md) |
| [`docs-triggers`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-triggers)                                   | ✅ Exempt | Integration provides no custom triggers; standard entity triggers via HA                                       |
| [`docs-conditions`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-conditions)                               | ✅ Exempt | Integration provides no custom conditions                                                                      |
| [`docs-high-level-description`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-high-level-description)       | ✅ Done   | README.md and docs site provide high-level brand/product description                                           |
| [`docs-installation-instructions`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-installation-instructions) | ✅ Done   | README.md has step-by-step HACS + manual install instructions                                                  |
| [`docs-removal-instructions`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-removal-instructions)           | ✅ Done   | Documented in `README.md` and dedicated [`docs/removal.md`](docs/removal.md)                                   |
| [`entity-event-setup`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-event-setup)                         | ✅ Done   | MQTT subscriptions registered in `async_added_to_hass`, unsubscribed in `async_will_remove_from_hass`          |
| [`entity-unique-id`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unique-id)                             | ✅ Done   | All entities have stable unique IDs derived from MAC + entry ID                                                |
| [`has-entity-name`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name)                               | ✅ Done   | `_attr_has_entity_name = True` implemented across all platforms                                                |
| [`runtime-data`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data)                                     | ✅ Done   | Fully migrated to `HisenseVidaaConfigEntry` & `entry.runtime_data` dataclass                                   |
| [`test-before-configure`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-configure)                   | ✅ Done   | Connection test + PIN validation in config flow before entry creation                                          |
| [`test-before-setup`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup)                           | ✅ Done   | Connection verified in `async_setup_entry` before platforms loaded                                             |
| [`unique-config-entry`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry)                       | ✅ Done   | Unique ID set to MAC; duplicate detected via `_async_abort_entries_match`                                      |

**Bronze status:** 100% complete (declared in `quality_scale.yaml`).

---

### 🥈 Silver Tier — Status: ✅ Complete (manifest retained at Bronze)

> **Quality Scale Declaration:** While all functional, architectural, exception-handling, and documentation requirements of Silver Tier have been fully implemented below, `manifest.json` intentionally remains pinned to `"quality_scale": "bronze"` (as the integration has not yet undergone official Home Assistant Core certification).

| Rule                                                                                                                                            | Status | Notes                                                                                                                                      |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [`action-exceptions`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-exceptions)                         | ✅ Done | All custom action calls in `services.py` are wrapped to catch underlying errors and raise `HomeAssistantError` instead of raw exceptions. |
| [`config-entry-unloading`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading)               | ✅ Done | Clean unload lifecycle in `async_unload_entry`.                                                                                            |
| [`docs-configuration-parameters`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-configuration-parameters) | ✅ Done | Options flow parameters documented with defaults, ranges, and use cases in [`docs/parameters.md`](docs/parameters.md).                    |
| [`docs-installation-parameters`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-installation-parameters)   | ✅ Done | Config flow fields (IP, port, TLS modes, cert provisioning) documented in [`docs/parameters.md`](docs/parameters.md).                     |
| [`entity-unavailable`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-unavailable)                       | ✅ Done | Entities marked unavailable on MQTT disconnect / connection loss.                                                                         |
| [`integration-owner`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/integration-owner)                         | ✅ Done | `"codeowners": ["@stevene1919"]` in `manifest.json`.                                                                                      |
| [`log-when-unavailable`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/log-when-unavailable)                   | ✅ Done | Exponential backoff reconnect logs; logs once on disconnect, once on restore.                                                             |
| [`parallel-updates`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates)                           | ✅ Done | `PARALLEL_UPDATES = 0` declared in all platform modules.                                                                                  |
| [`reauthentication-flow`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow)                 | ✅ Done | Interactive re-pairing flow + Repairs issue integration.                                                                                  |
| [`test-coverage`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-coverage)                                 | ✅ Done | Comprehensive test suite of 206 unit tests passing (77% overall code coverage across all modules).                                        |

**Silver Tier Summary:** All action-exceptions, configuration/installation documentation, and test verifications completed.

---

### 🥇 Gold Tier — Status: ✅ 100% complete

| Rule                                                                                                                                      | Status   | Notes                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------ |
| [`devices`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/devices)                                       | ✅ Done   | Full Device Registry binding with MAC, manufacturer, model, SW version                                 |
| [`diagnostics`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics)                               | ✅ Done   | Sanitized diagnostics in `diagnostics.py`                                                              |
| [`discovery`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery)                                   | ✅ Done   | SSDP + Zeroconf auto-discovery                                                                         |
| [`discovery-update-info`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/discovery-update-info)           | ✅ Done   | SSDP/ARP dynamic MAC tracking updates IP in config entry                                               |
| [`docs-data-update`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-data-update)                     | ✅ Done   | Documented local-push via MQTT (no polling) in docs                                                    |
| [`docs-examples`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-examples)                           | ✅ Done   | Added automation YAML recipes in `docs/services_and_automations.md`                                    |
| [`docs-known-limitations`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-known-limitations)         | ✅ Done   | Documented known limitations in `docs/parameters.md`                                                   |
| [`docs-supported-devices`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-supported-devices)         | ✅ Done   | Added verified device/firmware compatibility matrix to `README.md` and `docs/protocol_architecture.md`  |
| [`docs-supported-functions`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-supported-functions)     | ✅ Done   | Documented all entities, platforms, services, and supported features in `docs/parameters.md`           |
| [`docs-troubleshooting`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-troubleshooting)             | ✅ Done   | Expanded troubleshooting section in `docs/parameters.md`                                               |
| [`docs-use-cases`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-use-cases)                         | ✅ Done   | Documented real-world use cases in `docs/services_and_automations.md`                                  |
| [`dynamic-devices`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dynamic-devices)                       | ✅ Exempt | Integration is `integration_type: device`; single-TV per config entry by design                        |
| [`entity-category`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-category)                       | ✅ Done   | `EntityCategory.DIAGNOSTIC` and `CONFIG` applied to all appropriate entities                           |
| [`entity-device-class`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-device-class)               | ✅ Done   | Device classes used where applicable (`sensor`, `binary_sensor`, `switch`, `media_player`)             |
| [`entity-disabled-by-default`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-disabled-by-default) | ✅ Done   | Calibration number entities + secondary diagnostic switches disabled by default                        |
| [`entity-translations`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-translations)               | ✅ Done   | Full `_attr_translation_key` across all platforms; 100% parity `strings.json` ↔ `translations/en.json` |
| [`exception-translations`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/exception-translations)         | ✅ Done   | Translatable exception keys in `strings.json`                                                          |
| [`icon-translations`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/icon-translations)                   | ✅ Done   | Full `icons.json` with MDI icons for all entity translation keys and services                          |
| [`reconfiguration-flow`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reconfiguration-flow)             | ✅ Done   | `async_step_reconfigure` implemented                                                                   |
| [`repair-issues`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/repair-issues)                           | ✅ Done   | Native HA Repairs issues raised for invalidated tokens and missing certs                               |
| [`stale-devices`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/stale-devices)                           | ✅ Done   | Implemented `async_remove_config_entry_device` in `__init__.py`                                         |

**Gold status:** 100% complete (declared in `quality_scale.yaml` and `manifest.json`).

---

### 🏆 Platinum Tier — Status: ⚠️ ~33% complete

| Rule                                                                                                                    | Status     | Notes                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`async-dependency`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/async-dependency)   | ⚠️ **TODO** | `paho-mqtt` is a synchronous library; all MQTT callbacks dispatched via `call_soon_threadsafe`. Evaluate `aiomqtt` or `asyncio-mqtt` for a fully async MQTT dependency |
| [`inject-websession`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/inject-websession) | ✅ Exempt   | Integration uses raw TLS/MQTT sockets — no HTTP web session required                                                                                                   |
| [`strict-typing`](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/strict-typing)         | ✅ Done     | `py.typed` marker + inline type annotations throughout                                                                                                                 |

**Platinum gap:** `async-dependency` — evaluating async MQTT library migration (see Task #1 above for connection research context).

---

### 📋 `quality_scale.yaml` — Formal Tracking File

The IQS requires integrations tracking their tier to include a `quality_scale.yaml` file in the integration directory. This file is required for official HA Core submission but is also useful for HACS integrations aiming for the standard.

- [x] **Create `quality_scale.yaml`** with `done` / `exempt` / `todo` status for all rules.

---

## 🧹 Code Quality & Architecture Refactoring

- [x] **Sensor Platform Decomposition (`sensor.py`, `sensors_diagnostic.py`)**: Extracted diagnostic sensors into `sensors_diagnostic.py` (222 lines), reducing `sensor.py` from 409 lines to 235 lines.
- [x] **TV Settings Actions Mixin (`tv/settings.py` / `tv/actions.py`)**: Extracted picture and sound settings actions into `tv/settings.py` (293 lines), reducing `tv/actions.py` from 439 lines to 350 lines.
- [x] **Token Lifecycle Subpackage (`protocol/auth_lifecycle.py`)**: Extracted background token watch timer, proactive renewal, and exponential retry backoff from `client.py` into dedicated `TokenLifecycleManager`.
- [x] **TV Actions Mixin (`tv/actions.py`, `tv/settings.py`)**: Extracted TV action execution, settings commands, and navigation methods from `client.py` into reusable `TvActionsMixin` and `TvSettingsActionsMixin`.
- [x] **Client Runtime State Mixin (`tv/state.py`)**: Adopted `TvStateMixin` in `HisenseTvClient` to encapsulate telemetry and settings state attributes and power properties.
- [x] **Client Connection Lifecycle Mixin (`protocol/connection.py` / `client.py`)**: Extracted MQTT connection loops, keepalive management, async queries, and socket error recovery from `client.py` into dedicated `ConnectionManagerMixin` (`client.py` reduced from 842 -> 388 lines, -53.9%).
- [x] **Config Flow Modular Decomposition (`flow_certs.py`, `flow_discovery.py`, `flow_reauth.py`, `flow_helpers.py`)**: Decomposed monolithic `config_flow.py` (580 lines -> 268 lines) into single-purpose mixins and helper functions for discovery, reauth, certificate handling, and schema generation.
- [x] **CLI Diagnostic & Debug Script Parity (`test_client.py`, `debug_tv.py`)**: Updated CLI tools to support standalone execution outside Home Assistant container with automated fallback mocks.
- [x] **Media Player Broadcast State Parsing (`tv/media.py` / `media_player.py`)**: Extracted incoming broadcast telemetry, state, volume, and input handlers from `media_player.py` into modular parser functions (`parse_media_state_broadcast`, `parse_volume_broadcast`, `parse_sourcelist_data`, `parse_applist_data`).
- [x] **UPnP LAN Control & DLNA Subsystem (`protocol/upnp.py`, `client.py`)**: Implemented non-blocking UPnP client supporting port `38400` / `18400` with `RenderingControl:1`, `AVTransport:1`, and proprietary `LanControlInfo:1` actions for instantaneous volume/mute and media transport tracking.
- [x] **Zero-Cost Clock Drift Detection & Diagnostic Probes (`protocol/upnp.py`, `sensors_diagnostic.py`, `tv/fingerprint.py`)**: Integrated HTTP `Date` header clock offset calculation without NTP traffic, hardened `HisenseVidaaClockDriftSensor` against `None` offsets, added CLI probe integration (`test_client.py upnp`, `debug_tv.py --probe-upnp`), and documented router NTP DNAT port redirect rules.
- [x] **MQTT Disconnect & Re-Auth Collision Elimination (`client.py`, `flow_reauth.py`)**: Gracefully disconnected running background MQTT loops before initiating interactive reauth PIN pairing, preventing socket contention.
- [x] **MQTT v5 Connack Reason Codes (`protocol/connection.py`, `client.py`)**: Added explicit handling for codes `134` (Bad username/password) and `135` (Not authorized) to promptly trigger re-authentication.
- [x] **Startup Query Debounce & False PIN Prevention (`media_player.py`, `coordinator.py`)**: Eliminated unsolicited PIN prompts on TV screen during container startup by debouncing initial status queries until connections stabilize.
- [x] **Shared Diagnostics Probing & Script Consolidation (`tv/fingerprint.py`, `discovery.py`)**: Consolidated duplicate UPnP probing and XML parsing logic into shared `probe_upnp_services`, eliminating redundant test scripts.


