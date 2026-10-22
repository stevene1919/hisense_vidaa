# ⚙️ Configuration & Options Parameters Reference

This document provides a comprehensive reference for all user-configurable parameters across the **Initial Setup (Config Flow)** and **Options Flow** in the `hisense_vidaa` Home Assistant integration, adhering to Home Assistant Gold Tier Quality Scale standards.

---

## 📡 Data Update & Local Push Architecture

The integration operates using **100% Local Push (`iot_class: local_push`)**:
- **No Background Polling**: Home Assistant does not poll the TV for power state, volume, active app, or input sources. The TV pushes live state updates over a persistent, encrypted TLS MQTT connection (port `36669`) as events occur.
- **Instant Response**: Power changes, volume adjustments, and playback state transitions are reflected instantly in Home Assistant UI.
- **Clock Sync Interval**: A lightweight UPnP request runs every 2 hours (and on wake transition from standby) to check host-to-TV hardware clock drift without polling media telemetry.

---

## 📱 Supported Entities, Platforms & Features

The integration automatically registers entities across 9 Home Assistant platforms:

| Platform | Entity Class | Description & Features |
| :--- | :--- | :--- |
| **`media_player`** | `MediaPlayerDeviceClass.TV` | Power toggle, volume step/set, mute, source input switcher, Smart TV app launcher, media transport controls (Play, Pause, Stop, Next, Previous), active source/app artwork, and display state. |
| **`remote`** | `RemoteEntity` | Discrete key press commands, sequence dispatching (`hisense_vidaa.send_key_sequence`), configurable inter-key delays, and repeat counts. |
| **`sensor`** | `SensorEntity` | Active Source, Active App, Audio Output Mode, Session Status, Auth Profile, and Hardware Clock Drift offset ($> 60\text{s}$ warning threshold). |
| **`binary_sensor`** | `BinarySensorEntity` | Live MQTT Connection state and In Use indicator. |
| **`button`** | `ButtonEntity` | **Sync TV Clock**, **Force Reconnect**, and **Trigger Re-pairing** diagnostic buttons. |
| **`switch`** | `SwitchEntity` | **Debug Logging** logger toggle and **Audio Only** screen backlight toggle. |
| **`notify`** | `NotifyEntity` | On-screen toast message notification service (`notify.send_message`). |
| **`select`** | `SelectEntity` | **Picture Mode** (`Standard`, `Cinema Day`, `Cinema Night`, `Dynamic`, `Sports`, `Game`, `Filmmaker`) and **Sound Mode** switcher (`Standard`, `Theatre`, `Music`, `Speech`, `Late Night`, `Sports`). |
| **`number`** | `NumberEntity` | Calibration sliders for **Backlight**, **Brightness**, and **Contrast** (0–100). |

---

## ⚠️ Known Limitations

Before deploying the integration, note the following hardware and firmware limitations:

1. **No ICMP Ping in Standby**: Most Hisense VIDAA televisions turn off their ICMP ping responder while in low-power standby (`fake_sleep_0`). ICMP ping integration or ping binary sensors will report the TV as offline during standby.
2. **Wi-Fi Wake-on-LAN Unreliability**: Wake-on-LAN (WoL) over 802.11 Wi-Fi can drop initial packets when the TV's Wi-Fi module enters deep power-saving mode. Connecting the TV via wired Ethernet or enabling multi-burst WoL in options is strongly recommended.
3. **Firmware Compatibility Gaps**: Pre-2018 Hisense TV models (VIDAA U2 or earlier) lack the internal MQTT broker daemon on port `36669` and cannot be controlled via local TLS MQTT.
4. **App Deep-Linking Restrictions**: Certain Smart TV applications (e.g. Netflix, Disney+) enforce proprietary DRM restrictions that prevent launching directly into specific video content URLs without navigating through the app's main UI.

---

## 🚀 1. Installation & Setup Parameters (Config Flow)

When adding a new Hisense VIDAA TV (**Settings $\rightarrow$ Devices & Services $\rightarrow$ Add Integration $\rightarrow$ Hisense VIDAA TV**), the following parameters are available:

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`ip_address`** | `string` (IPv4) | **Yes** | None | The local network IP address of the Hisense Smart TV (e.g. `192.168.50.12`). It is strongly recommended to configure a static DHCP reservation on your router. |
| **`name`** | `string` | Optional | `Hisense TV` | User-friendly display name used to prefix created entity IDs and device registry names. |
| **`mac_address`** | `string` (MAC) | Optional | Auto-discovered | Hardware Ethernet or Wi-Fi MAC address (e.g. `e8:51:77:ec:98:1c`). Used for Wake-on-LAN packets and unique entity IDs. Discovered automatically via UPnP/ARP. |
| **`auth_profile`** | `select` | **Yes** | `auto` | Authentication and certificate selection tier: <br>• `auto`: Dynamically cascades from modern dynamic auth to middle, standard, and legacy profiles.<br>• `modern`: Modern XOR-masked timestamp dynamic auth (VIDAA U6, U7, U8, 2024+ models).<br>• `middle`: Middle dynamic auth protocol (transport_protocol 3000–3285).<br>• `remotenow`: Legacy RemoteNOW protocol (VIDAA U3 / U4).<br>• `legacy`: Static authentication without timestamp hashing.<br>• `vidaa_2024`: 2024+ firmware profile with strict broker handshakes. |
| **`pin_code`** | `string` (4 digits) | **Yes** (during pairing) | None | The 4-digit numeric verification code displayed on the physical TV screen during the initial pairing handshake. |
| **`certfile`** | `string` (file path) | Optional | Auto-resolved | Absolute path to custom client TLS certificate (`.pem` or `.crt`). If omitted, automatically resolves from default bundle or `ssl/` folder. |
| **`keyfile`** | `string` (file path) | Optional | Auto-resolved | Absolute path to custom client TLS private key (`.pem` or `.key`). |
| **`ca_cert`** | `string` (file path) | Optional | None | Optional custom root Certificate Authority file for strict broker TLS verification. |

---

## 🎛️ 2. Options Flow Parameters

To customize integration behavior for an existing TV, navigate to **Settings $\rightarrow$ Devices & Services $\rightarrow$ Hisense VIDAA TV $\rightarrow$ Configure**. Options are organized into 4 categorized tabs:

### 2.1 Power & Network (`power_network`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`enable_wol`** | `boolean` | `true` | Automatically sends Wake-on-LAN (WoL) magic packets to wake the TV when powering on from cold standby. |
| **`secondary_mac_address`** | `string` | `None` | Secondary MAC address (e.g., Ethernet MAC if paired over Wi-Fi, or vice-versa). WoL packets will be broadcast to both MACs simultaneously. |
| **`refresh_in_standby`** | `boolean` | `false` | When enabled, proactively refreshes MQTT access tokens even while the TV is in standby (recommended for TVs that maintain an active network stack in standby). |

### 2.2 Playback & Sources (`playback_sources`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`include_apps_in_sources`** | `boolean` | `true` | Merges installed Smart TV apps (Netflix, YouTube, Prime Video, etc.) directly into the `media_player` source selector dropdown. |
| **`enable_cec_names`** | `boolean` | `true` | Automatically replaces generic input names (`HDMI1`, `HDMI2`) with discovered HDMI-CEC device names (e.g. `Apple TV`, `PlayStation 5`, `Chromecast`). |
| **`enable_media_controls`** | `boolean` | `true` | Enables Play, Pause, Stop, Next, and Previous track controls on the media player entity. |
| **`playback_debounce`** | `float` (slider, seconds) | `0.5` | Settle window duration to filter out transient rapid state flickers (e.g., buffering transitions) from re-triggering automations. |

### 2.3 Entities & Remote Controls (`features_remote`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`enable_remote`** | `boolean` | `true` | When enabled, registers a `remote.<tv>` entity for sending discrete remote keys and sequences. |
| **`enable_notify`** | `boolean` | `true` | When enabled, registers a `notify.<tv>` entity for displaying on-screen toast popup notifications. |
| **`enable_picture_controls`** | `boolean` | `true` | Exposes `select.<tv>_picture_mode` and calibration number entities (Backlight, Brightness, Contrast). |
| **`enable_sound_controls`** | `boolean` | `true` | Exposes `select.<tv>_sound_mode` for switching audio modes (Standard, Theater, Music, Speech, Late Night). |
| **`enable_audio_only`** | `boolean` | `true` | Exposes `switch.<tv>_audio_only` to turn off the TV display backlight while keeping audio playing. |
| **`key_delay`** | `float` (slider, seconds) | `0.2` | Delay in seconds between consecutive key commands when sending sequences or repeated keystrokes. |
| **`key_repeat`** | `integer` (box) | `1` | Default number of times each keypress command is repeated. |

### 2.4 Connection & Security (`security`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`auth_profile`** | `select` | `auto` | Authentication handshake profile (`auto`, `modern`, `middle`, `remotenow`, `legacy`). |
| **`use_ssl`** | `boolean` | `true` | Toggle SSL/TLS socket encryption for broker communications. |
| **`certfile`** | `string` (file path) | Auto-resolved | Custom client certificate path (`.crt`, `.pem`, `.p12`). |
| **`keyfile`** | `string` (file path) | Auto-resolved | Custom client private key path (`.key`, `.pem`). |

---

## 🩺 3. Diagnostic, Telemetry & Debugging Entities

To facilitate real-time monitoring and troubleshooting directly from the Home Assistant UI, the integration provides several built-in diagnostic and maintenance entities under the **Diagnostic** category:

### 3.1 Maintenance Buttons (`button`)

| Entity ID | Entity Name | Description |
| :--- | :--- | :--- |
| **`button.<tv>_sync_clock`** | **Sync TV Clock** | Queries the TV's UPnP `Date:` HTTP header on port `38400` / `18400`, recalculates the host-to-TV clock drift in seconds, and updates the clock drift diagnostic sensor. |
| **`button.<tv>_force_reconnect`** | **Force Reconnect** | Tears down the existing MQTT broker connection loop, resets socket state, and re-establishes a fresh connection to the TV. Useful when recovering from router reboots or network glitches. |
| **`button.<tv>_trigger_re_pairing`** | **Trigger Re-pairing** | Manually initiates Home Assistant's native re-authentication and PIN pairing flow on the device without waiting for an automated token error or repairs issue. |

### 3.2 Diagnostic Sensors (`sensor` & `binary_sensor`)

| Entity ID | Entity Name | Description & Attributes |
| :--- | :--- | :--- |
| **`sensor.<tv>_clock_drift`** | **Clock Drift** | Reports TV hardware clock drift in seconds relative to the Home Assistant host. Automatically synchronized every 2 hours and on wake transition from standby. Changes icon between `mdi:clock-check-outline` (synced, $< 60\text{s}$) and `mdi:clock-alert-outline` ($> 60\text{s}$). Attributes: `synchronized` (bool), `drift_human` (e.g. `+15s`, `-5d 14h`), `tv_time`, `host_time`, `last_synced`. |
| **`sensor.<tv>_session_status`** | **Session Status** | Indicates active session state (`Active`, `Standby`, `Reauth Required`). Attributes: `encryption` (TLS version/port), `local_only` (bool), `paired_at`, `access_token_expires_at`, `refresh_token_expires_at`. |
| **`sensor.<tv>_auth_profile`** | **Auth Profile** | Displays the active authentication tier negotiated with the TV (e.g. `VIDAA 2.0 (Newer Firmware / 2024+)`). |
| **`sensor.<tv>_audio_output`** | **Audio Output** | Displays whether sound is currently output through `TV Speakers` or `ARC / eARC`. |
| **`sensor.<tv>_active_source`** | **Active Source** | Current input source name with `connected_device` HDMI-CEC display names. |
| **`sensor.<tv>_active_app`** | **Active App** | Currently running Smart TV application name. |
| **`binary_sensor.<tv>_mqtt_connected`** | **MQTT Connected** | Live binary indicator of whether the persistent TLS MQTT socket to port `36669` is established. |
| **`binary_sensor.<tv>_in_use`** | **In Use** | Indicates whether the TV display is powered on and actively drawing playback/content. |

### 3.3 Debugging Switches (`switch`)

| Entity ID | Entity Name | Description |
| :--- | :--- | :--- |
| **`switch.<tv>_debug_logging`** | **Debug Logging** | Dynamically enables or disables verbose `DEBUG` level logging for the `custom_components.hisense_vidaa` module in real-time without requiring a Home Assistant restart. |
| **`switch.<tv>_audio_only`** | **Audio Only** | Turns off the physical screen panel backlight while keeping audio playback streaming through TV speakers or ARC soundbar. |

---

## 🛠️ 4. Home Assistant Debugging & Diagnostics Guide

When troubleshooting communication, pairing, or state synchronization issues between Home Assistant and the TV, several debugging facilities are available:

### 4.1 Enabling Debug Logging

There are four convenient methods to enable verbose debug logging for the integration:

#### Method 1: On-the-Fly via Diagnostic Switch (Recommended)
Toggle the built-in diagnostic switch entity:
- **Entity ID**: `switch.<tv>_debug_logging`
- **Behavior**: Instantly sets the Python logger level for `custom_components.hisense_vidaa` to `DEBUG` without restarting Home Assistant or modifying any configuration files. Toggle off to return to `INFO` level.

#### Method 2: Via Home Assistant UI
1. Navigate to **Settings** → **Devices & Services**.
2. Locate the **Hisense VIDAA TV** integration card.
3. Click the three-dot menu (**⋮**) and select **Enable debug logging**.
4. Reproduce the issue, then return to the menu and click **Disable debug logging** to download the generated debug log bundle.

#### Method 3: Via `configuration.yaml`
Add or update the `logger` integration in your Home Assistant configuration:
```yaml
logger:
  default: warning
  logs:
    custom_components.hisense_vidaa: debug
```
Apply by restarting Home Assistant or calling the `logger.reload` action.

#### Method 4: Via Developer Tools Action (`logger.set_level`)
Without restarting, navigate to **Developer Tools** → **Actions** and execute:
```yaml
action: logger.set_level
data:
  custom_components.hisense_vidaa: debug
```

---

### 4.2 Downloading Home Assistant Diagnostics

Home Assistant provides official sanitized diagnostic bundles for bug reports:
1. Navigate to **Settings** → **Devices & Services** → **Hisense VIDAA TV**.
2. Click on the device or the integration three-dot menu (**⋮**) and choose **Download diagnostics**.
3. **Privacy & Redaction**: The integration automatically sanitizes sensitive fields before generating the JSON file. Masked keys include:
   - Certificate file paths (`ssl_cert`, `ssl_key`, `p12_path`, `client_cert_path`, `client_key_path`)
   - Certificate passwords (`p12_password`)
   - Session tokens (`access_token`, `refresh_token`, auth passwords)
   - Network MAC addresses and unique hardware identifiers
4. **Diagnostic Contents**:
   - Integration entry options and network parameters
   - Live client connection state and negotiated TLS cipher/version
   - TV hardware fingerprint (model, chipset, software build, firmware version)
   - UPnP capability probe results and hardware clock drift offset
   - Broadcast telemetry and registered HDMI/source lists

---

### 4.3 Native Repairs & PIN Re-Pairing Flow

- **Automated Repairs**: If the TV purges its internal mobile authentication token table or if credentials become invalid, the integration automatically registers a Home Assistant **Repair Issue** alerting you that re-authentication is required.
- **Manual Trigger**: To proactively renew pairing or re-pair after TV firmware updates, press the **`button.<tv>_trigger_re_pairing`** entity on the TV device page in Home Assistant. This immediately initiates the PIN entry dialog on your television screen and in the Home Assistant UI.

---

### 4.4 Inspecting Logs

To view live integration logs:
1. Go to **Settings** → **System** → **Logs**.
2. Filter the search box by `custom_components.hisense_vidaa`.
3. Key log entries to monitor:
   - `[hisense_vidaa] Connected to MQTT broker at <ip>:36669 (TLS 1.2)`
   - `[hisense_vidaa] Clock drift detected: <offset>s (TV: <date>, Host: <date>)`
   - `[hisense_vidaa] Connection dropped, reconnecting in <backoff>s...`
   - `[hisense_vidaa] UPnP probed on port <port>: RenderingControl=True, AVTransport=True`



