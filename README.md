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
2. Obtain the generic TV SSL connection certificate (`cert.pem`) and private key (`key.pem`) from an external reference source.
3. Place both files inside the `certs/` subdirectory within the integration folder:
   ```text
   custom_components/hisense_vidaa/certs/cert.pem
   custom_components/hisense_vidaa/certs/key.pem
