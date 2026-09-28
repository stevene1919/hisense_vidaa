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

---

## 🏆 Home Assistant Integration Quality Scale Tracking

Tracking adherence to official [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index) rules.

### 🥉 Bronze Tier (Target: Official Compliance) — Status: ✅ 100%
- [x] **`config-flow`**: UI configuration via config flow (`config_flow.py`).
- [x] **`test-before-setup`**: Connection test and PIN validation before adding device.
- [x] **`unique-id`**: All entities have stable unique IDs derived from MAC/entry ID.
- [x] **`common-modules`**: Standard entity platforms used (`media_player`, `sensor`, `binary_sensor`, `remote`, `select`, `number`, `button`, `switch`, `notify`).
- [x] **`has-entity-name`**: `_attr_has_entity_name = True` implemented across all entity platforms.
- [x] **`entity-category`**: `EntityCategory.DIAGNOSTIC` and `CONFIG` applied to appropriate entities.
- [x] **`appropriate-polling`**: `should_poll = False` (pure local push via MQTT).
- [x] **`brands`**: Brand logos and icons provided in `brand/`.
- [x] **`reauthentication-flow`**: Interactive re-pairing flow implemented with repairs integration.
- [x] **`discovery-update-id`**: SSDP/Zeroconf/ARP dynamic MAC tracking for IP updates.

### 🥈 Silver Tier — Status: ✅ 100%
- [x] **`config-entry-unloading`**: Clean unload lifecycle without leaking tasks, MQTT loops, or listeners.
- [x] **`log-when-unavailable`**: Exponential backoff reconnection logging to prevent log spam.
- [x] **`reconfiguration-flow`**: Config flow reconfiguration supported (`async_step_reconfigure`).
- [x] **`repair-issues`**: Native Home Assistant Repairs issues created for invalidated tokens and missing certs.
- [x] **`diagnostics`**: Sanitized diagnostics platform implemented (`diagnostics.py`).
- [x] **`entity-disabled-by-default`**: Advanced calibration number entities and secondary diagnostic switches disabled/opt-in by default.
- [x] **`parallel-updates`**: Explicit `PARALLEL_UPDATES = 0` declared across all platform modules.

### 🥇 Gold Tier — Status: 🟡 ~95%
- [x] **`discovery`**: Automatic background discovery via SSDP (`urn:schemas-upnp-org:device:MediaRenderer:1`) and Zeroconf.
- [x] **`devices`**: Full Device Registry binding with MAC hardware connections, manufacturer, model, and software version.
- [x] **`entity-translations`**: Full `_attr_translation_key` adoption across all entity platforms with 100% parity between `strings.json` and `translations/en.json`.
- [x] **`entity-service-descriptions`**: Comprehensive `services.yaml` with selectors, names, and descriptions.
- [x] **`exception-translations`**: Translatable exception keys in `strings.json`.
- [x] **`icon-translations`**: Full `icons.json` mapping all entity translation keys and custom services to Material Design Icons.
- [x] **`test-coverage`**: 111 unit tests across all flows, platforms, crypto, and network state transitions.
- [x] **`strict-typing`**: PEP 561 `py.typed` marker file and inline type annotations.
- [ ] **`dynamic-options-update`**: Verify runtime options modifications take effect dynamically without requiring full integration reloads where possible.
- [ ] **`service-response-data`**: Add `SupportsResponse.OPTIONAL` on diagnostic and probe services to return structured execution data.

---

## 🧹 Code Quality & Architecture Refactoring
- [x] **Sensor Platform Streamlining (`sensor.py`)**: Consolidated callback registration and state dispatcher lifecycle hooks across 6 sensor entity classes.
- [x] **Token Lifecycle Subpackage (`protocol/auth_lifecycle.py`)**: Extracted background token watch timer, proactive renewal, and exponential retry backoff from `client.py` into dedicated `TokenLifecycleManager`.
- [x] **TV Actions Mixin (`tv/actions.py`)**: Extracted TV action execution, settings commands, and navigation methods from `client.py` into reusable `TvActionsMixin`.
- [x] **Client Runtime State Mixin (`tv/state.py`)**: Adopted `TvStateMixin` in `HisenseTvClient` to encapsulate telemetry and settings state attributes and power properties (`client.py` reduced from 842 -> 576 lines).
- [x] **Config Flow Modular Decomposition (`flow_certs.py`, `flow_discovery.py`, `flow_reauth.py`, `flow_helpers.py`)**: Decomposed monolithic `config_flow.py` (580 lines -> 267 lines) into single-purpose mixins and helper functions for discovery, reauth, certificate handling, and schema generation.
- [x] **CLI Diagnostic & Debug Script Parity (`test_client.py`, `debug_tv.py`)**: Updated CLI tools to support standalone execution outside Home Assistant container with automated fallback mocks.
- [ ] **Media Player Broadcast State Parsing (`tv/media.py` / `media_player.py`)**: Extract incoming broadcast telemetry, state, volume, and input handlers from `media_player.py` (currently 429 lines) into modular parser functions.
- [ ] **Client Connection Lifecycle Management (`protocol/connection.py` / `client.py`)**: Extract MQTT connection loops, keepalive management, and socket error recovery from `client.py` into dedicated connection lifecycle handlers.


