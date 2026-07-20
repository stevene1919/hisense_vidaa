# Changelog

All notable changes to the Hisense VIDAA TV integration will be documented in this file.

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
