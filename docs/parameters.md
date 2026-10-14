# ⚙️ Configuration & Options Parameters Reference

This document provides a comprehensive reference for all user-configurable parameters across the **Initial Setup (Config Flow)** and **Options Flow** in the `hisense_vidaa` Home Assistant integration, adhering to Home Assistant Silver Tier Quality Scale standards.

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

To customize integration behavior for an existing TV, navigate to **Settings $\rightarrow$ Devices & Services $\rightarrow$ Hisense VIDAA TV $\rightarrow$ Configure**. Options are organized into 5 categorized tabs:

### 2.1 General Settings (`general`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`enable_remote`** | `boolean` | `true` | When enabled, registers a `remote.<tv>` entity for sending discrete remote keys and sequences. |
| **`enable_notify`** | `boolean` | `true` | When enabled, registers a `notify.<tv>` entity for displaying on-screen toast popup notifications. |
| **`enable_wol`** | `boolean` | `true` | Automatically sends Wake-on-LAN (WoL) magic packets to wake the TV when powering on from cold standby. |
| **`secondary_mac_address`** | `string` | `None` | Secondary MAC address (e.g., Ethernet MAC if paired over Wi-Fi, or vice-versa). WoL packets will be broadcast to both MACs simultaneously. |
| **`refresh_in_standby`** | `boolean` | `false` | When enabled, proactively refreshes MQTT access tokens even while the TV is in standby (recommended for TVs that maintain an active network stack in standby). |

### 2.2 Input Sources & Apps (`sources`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`enable_cec_names`** | `boolean` | `true` | Automatically replaces generic input names (`HDMI1`, `HDMI2`) with discovered HDMI-CEC device names (e.g. `Apple TV`, `PlayStation 5`, `Chromecast`). |
| **`include_apps_in_sources`** | `boolean` | `true` | Merges installed Smart TV apps (Netflix, YouTube, Prime Video, etc.) directly into the `media_player` source selector dropdown. |

### 2.3 Picture & Sound Controls (`picture_sound`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`enable_picture_controls`** | `boolean` | `true` | Exposes `select.<tv>_picture_mode` and calibration number entities (Backlight, Brightness, Contrast). |
| **`enable_sound_controls`** | `boolean` | `true` | Exposes `select.<tv>_sound_mode` for switching audio modes (Standard, Theater, Music, Speech, Late Night). |
| **`enable_audio_only`** | `boolean` | `true` | Exposes `switch.<tv>_audio_only` to turn off the TV display backlight while keeping audio playing. |
| **`enable_media_controls`** | `boolean` | `true` | Enables Play, Pause, Stop, Next, and Previous track controls on the media player entity. |

### 2.4 Remote Keys & Macros (`remote_keys`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`key_delay`** | `float` (seconds) | `0.2` | Delay in seconds between consecutive key commands when sending sequences or repeated keystrokes. |
| **`key_repeat`** | `integer` | `1` | Default number of times each keypress command is repeated. |

### 2.5 Security & Certificates (`certs`)

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`auth_profile`** | `select` | `auto` | Allows updating the authentication protocol tier without re-pairing. |
| **`use_ssl`** | `boolean` | `true` | Enforces TLS encrypted communication to the TV's broker on port 36669. |
| **`certfile`** | `string` | Auto-resolved | Path to updated client certificate file. |
| **`keyfile`** | `string` | Auto-resolved | Path to updated client private key file. |
