# Changelog

All notable changes to the Hisense VIDAA TV integration will be documented in this file.

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
