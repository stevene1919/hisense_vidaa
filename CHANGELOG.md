# Changelog

All notable changes to the Hisense VIDAA TV integration will be documented in this file.

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
- **Wake-on-LAN (WoL)**: Automatic WoL magic packet dispatching to turn the TV on from deep sleep/standby.
