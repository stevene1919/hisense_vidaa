# Hisense VIDAA TV Integration for Home Assistant

A custom Home Assistant integration for Hisense TVs running VIDAA OS. 

This integration connects **directly** to the TV's internal MQTT broker (SSL port `36669`) using generic certificates, meaning you do **not** need to configure a Mosquitto MQTT bridge at the system level.

## Features

- **Direct Secure Connection**: Connects straight to the TV over SSL.
- **Easy UI Setup**: Fully configured via Home Assistant Config Flow.
- **PIN Authentication**: Automatic on-screen challenge PIN display and input within the integration setup flow.
- **Wake-on-LAN Support**: Power on the TV from standby using MAC address.
- **Media Player Entity**:
  - Power control.
  - Volume adjust, step, and mute.
  - Source selector (combines HDMI/AV inputs and installed applications).
  - Media Browser for launching applications.
  - Real-time updates via local push.

## Installation

1. Copy the `hisense_vidaa` directory to your Home Assistant `custom_components/` directory (e.g. `/config/custom_components/hisense_vidaa`).
2. Restart Home Assistant.
3. In Home Assistant, go to **Settings** -> **Devices & Services** -> **Add Integration**.
4. Search for **Hisense VIDAA TV** and follow the step-by-step UI configuration (you will be prompted to enter the 4-digit code displayed on your TV screen).
