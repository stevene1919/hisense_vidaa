# Changelog

All notable changes to the Hisense VIDAA TV integration will be documented in this file.

## [2.2.0] - 2026-09-11

### Added
- **LEGACY STATIC AUTHENTICATION PROFILE (`legacy`)**: Added native support for pre-2022 Hisense TVs using static MQTT credentials (`hisenseservice` / `multimqttservice`). Automatically probes TV capabilities, bypasses PIN pairing, and disables token refresh loops for legacy devices.
- **AUTOMATIC TV CLOCK SYNCHRONIZATION**: Added UPnP/DLNA HTTP `Date` header extraction to synchronize pairing timestamp calculations directly with the TV's internal clock, preventing `rc: 5` / `rc: 4` authentication rejections during clock drift or offline time rollover.
- **NATIVE HOME ASSISTANT REAUTH & RECONFIGURE FLOWS**: Implemented `async_step_reauth`, `async_step_reauth_confirm`, and `async_step_reconfigure` (`supports_reconfigure: true`) with automated reauth triggering upon expired sessions and one-click PIN regeneration.
- **CLI DIAGNOSTIC PROBE ENHANCEMENTS**: Updated `test_client.py` with `--profile legacy`, dynamic 3-tier auth compatibility probing (Legacy Static, Standard Dynamic, Modern Dynamic), and Markdown issue reporting.

### Fixed
- **ENTITY STATE & AVAILABILITY OVERHAUL**: Media player and remote entities now correctly report `state = STATE_OFF` (`"off"`) with `available = True` while the TV is in standby/disconnected, preserving UI power toggles and automation triggers.
- **CODE DEDUPLICATION & ARCHITECTURAL REFACTORING**: Extracted options flow into dedicated `options_flow.py`, centralized ARP hardware MAC resolution in `discovery.py`, and ensured 100% logic sharing between the HA integration and `test_client.py`.

## [2.0.0] - 2026-09-06

### Added
- **MODULAR ARCHITECTURE REFACTOR**: Modularized the codebase into single-responsibility components: [`crypto.py`](custom_components/hisense_vidaa/crypto.py) (authentication hashing, XOR masking, and cert discovery), [`discovery.py`](custom_components/hisense_vidaa/discovery.py) (UPnP XML and mDNS discovery), [`const.py`](custom_components/hisense_vidaa/const.py) (constants and profile definitions), and [`client.py`](custom_components/hisense_vidaa/client.py) (async MQTT lifecycle).
- **DUAL-TIER AUTHENTICATION PROFILE SELECTOR**: Added support for choosing between Modern VIDAA 2.0 (`libmqttcrypt.so` / `Q0704`+ with XOR mask and Modern salt `h!i@s#$v%i^d&a*a`) and Legacy RemoteNOW (`h*i&s%e!r^v0i1c9` salt), alongside automatic profile detection and selective certificate resolution (`vidaa_2024_*`, `remotenow_2018_*`, and `cert.pem`).

### Fixed
- **INSTANT 1ST-ATTEMPT PAIRING**: Resolved race condition during initial pairing where the TV challenge response arrived before the MQTT subscription was acknowledged by adding a 500ms subscription settling delay and multi-attempt retry loop for `vidaa_app_connect`.
- **RECONNECTION STORM PROTECTION**: Added exponential reconnect backoff (`min_delay=2, max_delay=30`) and safe executor-based disconnection handling upon config entry unload.
- **GITHUB ACTIONS RELEASE WORKFLOW**: Fixed `actions/checkout` versioning and changelog extraction parser in CI release workflows.

## [1.5.0] - 2026-09-06

### Added
- **OPTIONS FLOW SUPPORT**: Added `OptionsFlowHandler` allowing full configuration of features and device behaviors via **Settings -> Devices & Services -> Configure** on existing TVs without re-pairing.
- **DEDICATED REMOTE ENTITY PLATFORM (`remote`)**: Added native `remote` entity (`remote.<tv_name>`) supporting D-pad navigation, numeric keypad, channel switching, media controls, color buttons, and app shortcuts.
- **MEDIA CONTROLS EXPANSION**: Added `PLAY`, `PAUSE`, `STOP`, `NEXT_TRACK`, `PREVIOUS_TRACK`, and `PLAY_MEDIA` support to the `media_player` entity.
- **SMART TV APPS IN SOURCE LIST**: Configurable option (`include_apps_in_sources`) to dynamically include installed Smart TV apps (Netflix, YouTube, Prime, Plex, etc.) in the `media_player` source dropdown alongside hardware HDMI/TV inputs.
- **WAKE-ON-LAN POWER ON**: Configurable option (`enable_wol`) to broadcast a UDP magic packet on `turn_on` to wake TVs from deep standby.
- **KEY ALIAS RESOLUTION**: Added alias normalizer supporting friendly command names (`up`, `down`, `home`, `menu`, `back`, `netflix`, `youtube`, etc.) across `remote.send_command` and CLI `test_client.py`.

## [1.4.2] - 2026-09-06

### Added
- **DYNAMIC TV DEVICE & ENTITY NAMING**: Config flow now automatically detects the TV's broadcast friendly name (e.g. `Smart TV`, custom name from TV settings, or model code) via UPnP/mDNS and names the Home Assistant device and entity accordingly upon pairing.

## [1.4.1] - 2026-09-06

### Added
- **GITHUB ISSUE DIAGNOSTIC REPORT (`report`)**: Added `python3 test_client.py report --ip <IP>` command generating a pre-formatted, redacted Markdown diagnostic block with hardware specs, firmware indicators, and auth capabilities ready to paste into GitHub issues.
- **ACTIVE MULTI-TIER AUTH PROBING**: Enhanced `ping` and `report` with live compatibility testing for standard dynamic (`his$<timestamp>`), modern dynamic (XOR), and legacy static (`hisenseservice`) pairing handshakes.
- **AUTOMATED DEVICE FINGERPRINTING**: Added UPnP/DLNA XML parser and mDNS discovery to automatically identify TV model names, VIDAA platform capabilities, and Wi-Fi / Ethernet MAC addresses.

## [1.4.0] - 2026-09-06

### Added
- **NEW VIDAA FIRMWARE AUTHENTICATION FALLBACK**: Added support for newer VIDAA OS firmware versions (e.g. `V0000.09.09U.P1027`) where the internal broker rejects pairing with MQTT `rc: 5`. The integration now automatically falls back to XOR timestamp credential hashing (`his${timestamp ^ 6239759785777146216}`) on `rc: 5` pairing failures.
- **IMPROVED CONNECTION CLEANUP**: Ensured MQTT client disconnect and loop termination on failed initial pairing attempts.

## [1.3.1] - 2026-09-04

### Changed
- **DOCUMENTATION & REPOSITORIES**: Updated references to legacy alternatives ([`sehaas/ha_hisense_tv`](https://github.com/sehaas/ha_hisense_tv) and [`Krazy998/mqtt-hisensetv`](https://github.com/Krazy998/mqtt-hisensetv/)).
- **PROBE MESSAGES**: Pointed diagnostic probe output in `client.py` directly to the README section for integration selection guidance.

## [1.3.0] - 2026-09-04

### Added
- **STANDARD HACS DIRECTORY STRUCTURE**: Relocated integration files into standard `custom_components/hisense_vidaa/` layout for seamless HACS installation and updates.
- **HACS BRANDING & ASSETS**: Included icon and logo brand assets inside the component directory for HACS validation.
- **MY HOME ASSISTANT BADGE**: Added 1-click installation badge and updated documentation for HACS Custom Repository setup.

### Changed
- **HACS CONFIGURATION**: Removed deprecated `content_in_root` attribute in `hacs.json`.
- **CI WORKFLOWS**: Streamlined Hassfest validation and HACS Action checks to run directly on the standard component directory.

## [1.2.0] - 2026-09-04

### Added
- **CONNECTIVITY & FIRMWARE PROBE (`ping`)**: Added a 3-tier diagnostic probe (TCP port, TLS handshake, and broker response) with automatic firmware detection (suggests legacy vs modern VIDAA integration).
- **SSL CERTIFICATE TESTING (`test-ssl`)**: Added dedicated `test-ssl` command and `test_ssl_connection()` method to verify TLSv1.2 cipher suites and certificate validity directly against port 36669.
- **CUSTOM CERTIFICATE PATHS**: Added support for explicit `--cert` and `--key` arguments with fallback search order (`custom` -> `certs/` -> `/config/certs/` -> `/config/ssl/`).
- **STANDALONE TEST SUITE (`test_client.py`)**: Unified testing utility sharing 100% of its backend logic with the Home Assistant `HisenseTvClient` integration code.
- **AUTOMATIC MAC ADDRESS DISCOVERY**: Removed manual MAC address input from the setup modal; the integration now automatically discovers and formats the hardware MAC address via ARP cache and binds it to the Home Assistant Device Registry.
- **DOCUMENTATION OF LEGACY ALTERNATIVES**: Added comprehensive guide in README referencing established legacy integrations (`ha_hisense_tv`, `hisensetv`, `mqtt-hisensetv`) for older static-credential models.

### Fixed
- **ENTITY NAMING DUPLICATION**: Fixed entity ID generation producing `media_player.hisense_tv_hisense_tv_...` by setting `_attr_has_entity_name = True` and removing redundant name overrides (Issue #5).
- **THREAD-STORM PREVENTION**: Added mutex locks and a 10-second minimum cooldown to prevent thread storms and runaway CPU usage during connection failures or network drops (Issue #6).
- **THREAD-SAFE ASYNC FUTURE COMPLETION**: Wrapped event loop futures with `call_soon_threadsafe` across Paho-MQTT network threads and asyncio loops to ensure instantaneous challenge PIN and token resolution.
- **STARTUP BLOCKING CALLS**: Offloaded certificate loading and MQTT client instantiation to `loop.run_in_executor` during async config flows.

## [1.1.0] - 2026-07-21

### Fixed
- **STANDBY WAKE-UP**: Switched `turn_on` method from Wake-on-LAN to direct MQTT `KEY_POWER` command, resolving standby power control issues.
- **STABLE BACKGROUND POLLING**: Fixed token expiration causing permanent disconnection after the TV was turned off for more than 2 hours. The integration now intercepts MQTT auth failures, asynchronously refreshes the access token, updates Paho credentials, and reconnects in the background.
- **NON-BLOCKING STARTUP**: Modified startup MQTT connection loop to be non-blocking. If the TV is powered down when Home Assistant boots, the integration setup succeeds and auto-connects as soon as the TV becomes reachable on the network.
- **DYNAMIC TOKEN STORAGE**: Refreshed tokens are now dynamically persisted back to the Config Entry in Home Assistant, surviving restarts.

### Removed
- **WAKE-ON-LAN**: Removed `wakeonlan` package dependency and UDP magic packet dispatching entirely. Retained MAC address configuration input solely for device registry binding.
- **MEDIA BROWSER**: Removed Home Assistant Media Browser and `PLAY_MEDIA` features to simplify integration and prevent diagnostic errors.

## [1.0.0] - 2026-07-19

### Added
- **Initial Release**: Full conversion of the standalone `hisense.py` Python control script into a native Home Assistant custom integration.
- **Direct Secure Connection**: Native connection directly to the TV's secure TLS MQTT broker on port `36669` using certificates packaged with the component. No Mosquitto configuration or systems-level bridges are required.
- **User-Friendly Setup**: Integrated Config Flow for simple step-by-step setup in the Home Assistant UI (IP, optional MAC, and automatic display-and-entry challenge PIN).
- **Core Controls**: Complete media player capabilities (Power toggle, volume adjustment, volume steps, mute/unmute).
- **Filtered Input Source List**: Cleaned up the input source selector to list only hardware interfaces (HDMI1, HDMI2, HDMI3, TV, AV) and ignore internal VIDAA app services, keeping the UI simplified.
- **Robust Connection Handlers**: 
  - Offloaded MQTT connections to a thread pool executor.
  - Used event-loop threadsafe hooks (`call_soon_threadsafe`) for UI state updates.
  - Added smart token refresh logic on startup to prevent session conflicts and infinite reloading loops.
