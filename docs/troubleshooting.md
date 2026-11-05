# 🛠️ Hisense VIDAA TV Troubleshooting Guide

This guide helps you identify, diagnose, and resolve common issues encountered when using the **Hisense VIDAA TV** integration in Home Assistant, including service call errors, standby behavior, pairing recovery, and network connectivity.

---

## 🧭 Quick Diagnostic Flow

When something isn't working as expected, follow these first steps:

1. **Check TV Power & Network State**: Can the TV be pinged, or is it in deep sleep? (VIDAA TVs shut down their network cards in deep standby unless Wake-on-LAN/Mobile Turn-On is enabled in TV settings).
2. **Check Home Assistant Repairs**: If the TV wiped its pairing session tokens, Home Assistant will create an alert under **Settings** → **Repairs**.
3. **Inspect Entity State & Diagnostics**: Open `media_player.<tv_name>` in Developer Tools or download diagnostics from the integration device card (**Settings** → **Devices & Services** → **Hisense VIDAA TV** → **⋮** → **Download diagnostics**).
4. **Enable Debug Logging**: Toggle `switch.<tv_name>_debug_logging` to capture live communication in **Settings** → **System** → **Logs**.

---

## ⚠️ Service Action & Automation Error Reference

When an automation or manual service call fails, Home Assistant displays an error banner or logs an exception. Use this table to understand the cause and resolution:

| Error Message / Translation Key | Cause | How to Fix |
| :--- | :--- | :--- |
| **`Failed to send key {key}: {error}`**<br>(`send_key_failed`) | The TV's MQTT broker rejected the key command, the TV is disconnected, or an invalid key name was supplied. | 1. Ensure the TV is awake (send a Wake-on-LAN command if asleep).<br>2. Verify the key name matches supported keys (e.g., `KEY_POWER`, `KEY_VOLUMEUP`, `KEY_HOME`). See [`services_and_automations.md`](services_and_automations.md#11-supported-key-names). |
| **`Key sequence cannot be empty`**<br>(`empty_key_sequence`) | The `send_key_sequence` action was triggered with an empty `sequence` list. | Ensure your automation or script passes at least one key name in the `sequence` list parameter. |
| **`Failed to send key sequence at step {index} ({key}): {error}`**<br>(`send_key_sequence_failed`) | The sequence was interrupted (e.g. TV disconnected, command timed out, or unmapped key at step *N*). | Check the error details for the specific key step that failed. Increase `delay` between keys (e.g., to `0.5`s or `1.0`s) to give the TV OS time to process each keypress. |
| **`Channel digits must contain numbers only: {channel}`**<br>(`invalid_channel_digits`) | The `change_channel` action received non-numeric characters (e.g., letters or spaces). | Provide only numeric digits or dot-separated channel numbers (e.g. `10`, `70`, `7.1`). |
| **`Failed to send channel digit {digit}: {error}`**<br>(`change_channel_digit_failed`) | Communication with the TV failed while sending one of the numeric channel keys (`KEY_0` - `KEY_9`). | Ensure the TV is currently in Live TV / Antenna tuner mode before changing channels. If the TV is in an HDMI input or streaming app, tune to Live TV first. |
| **`Failed to send channel confirmation key {key}: {error}`**<br>(`change_channel_confirm_failed`) | The TV failed to receive the trailing confirmation key (`KEY_OK` / `KEY_ENTER`). | Increase `digit_delay` in the service call (e.g., `digit_delay: 0.5`) to allow slower TV tuners to register digits before confirmation. |
| **`Failed to launch app {app_name}: {error}`**<br>(`launch_app_failed`) | The app name or app ID is not installed on this TV, or the TV OS rejected the launch payload. | Verify that the app is installed and visible in the TV's native app launcher. Check `media_player.<tv_name>` attributes for the list of available sources/apps. |
| **`Failed to set picture setting {setting} to {value}: {error}`**<br>(`set_picture_setting_failed`) | The requested picture preset or numeric value is out of range or not supported on this TV model. | Use the built-in UI select/number entities (e.g., `select.<tv_name>_picture_mode`) or check supported modes in the TV settings menu. |
| **`Failed to set sound setting {setting} to {value}: {error}`**<br>(`set_sound_setting_failed`) | The requested sound mode is unsupported or ARC/eARC soundbar control is overriding TV internal sound modes. | If an external soundbar or AV receiver is connected via eARC, sound modes may be locked by the external audio device. |
| **`Failed to send text input: {error}`**<br>(`send_text_input_failed`) | The TV refused the text string because an on-screen keyboard dialog is not currently open. | Ensure the TV screen is currently displaying an active text input search box or keyboard before calling `send_text_input`. |

---

## 🔌 Connection & Network Issues

### 1. TV Shows "Unavailable" When Powered Off
* **Explanation:** VIDAA OS operates in two tiers of standby:
  1. **Light Standby (Screen Off)**: MQTT broker stays active for ~5-15 minutes after power-off.
  2. **Deep Standby (Cold Sleep)**: The TV powers down its main system board and Wi-Fi chip to comply with EU/international eco-power regulations (<0.5W). In this state, the TV cannot maintain a TCP/MQTT socket connection and will appear **unavailable** in Home Assistant.
* **Solution:**
  * Go to TV **Settings** → **Network** / **System** → **Advanced Settings** and enable:
    * **Wake on LAN / Network Standby** (or **Mobile App Turn On / TV Auto Action**)
    * **Fast Start / Fast Boot** (if available)
  * Configure Wake-on-LAN in the integration's Options Flow (burst count 3-5 packets) so Home Assistant can wake the TV over the network when you press Power On.
  * See [`power_and_standby_settings.md`](power_and_standby_settings.md) for TV firmware setting guides.

### 2. Connection Refused on Port 36669
* **Explanation:** The integration communicates with the TV's local MQTT broker over port `36669` (TCP/TLS).
* **Troubleshooting Steps:**
  * Confirm the TV and Home Assistant are on the same subnet, or that routing/firewall rules permit traffic from Home Assistant to TV port `36669`.
  * Verify reachability from Home Assistant terminal:
    ```bash
    nc -zv <tv_ip> 36669
    ```
  * Note: Hisense and VIDAA devices often drop ICMP ping requests by default. Reachability must be verified via TCP port `36669` or UPnP HTTP port `38400` (e.g. `curl -I http://<tv_ip>:38400/MediaServer/rendererdevicedesc.xml`), not standard `ping`.
  * See [`network_requirements.md`](network_requirements.md) for complete port and firewall specifications.

---

## 🔐 Pairing & Authentication Issues

### 1. Pairing Fails or PIN Does Not Appear on Screen
* **Mobile App Conflict:** VIDAA TVs typically allow only one active remote control session at a time. If the official **RemoteNOW** or **VIDAA** mobile app is currently running on a phone or tablet, close the mobile app completely before starting pairing in Home Assistant.
* **Stale Pairing Cache:** In Home Assistant, restart the config flow or trigger re-pairing via `button.<tv_name>_trigger_re_pairing`.
* **Expired PIN:** PIN codes displayed on the TV screen expire after 60 seconds. Enter the 4-digit code promptly.

### 2. Frequent Token Loss or Prompts to Re-Authenticate
* **Cause: Volatile Memory Wipes on Standby:**
  * Some VIDAA TV models clear their RAM when entering deep sleep if external HDMI streaming sticks (Fire TV, Roku, Chromecast) draw power from the TV's USB port. When the TV goes into standby, the USB port cuts power abruptly, causing an ungraceful shutdown that wipes volatile authentication tokens.
* **Fix:**
  * Power streaming sticks from a wall AC adapter rather than the TV's USB ports.
  * In TV Settings, disable **Auto Standby with No Signal**.
  * Keep Home Assistant's client certificates properly configured in `/config/ssl/` as documented in [`certificates.md`](certificates.md) to enable automatic mutual TLS authentication.

### 3. Broker Rejection or "Not Authorized" Error (`rc: 5` / `rc: 135`)
* **Cause: OEM Brand Code Mismatch:**
  * When communicating with licensed partner brands (Toshiba, Loewe, TPV/Philips, Sharp, JVC, TOPTRO, etc.), the TV/projector broker validates client credentials against an OEM brand prefix salt. If generic Hisense credentials (`his`) are sent to a partner device, the broker rejects authentication with `rc: 5` (MQTT 3.1.1) or `rc: 135` (MQTT 5.0).
* **Fix:**
  * Keep **Brand Profile** set to **Auto Detect (Recommended)**. When enabled, the integration queries UPnP port `38400` / `18400` to extract `brand=` from `<modelDescription>` or cascades through supported candidate OEM brands (`tos`, `loe`, `tpv`, `shp`, `jvc`, `tpo`).
  * If adding a device across an isolated VLAN where UPnP is blocked and cascade is exhausted, open **Settings → Devices & Services → Hisense VIDAA TV → Configure → Security** and manually select your device's brand from the dropdown.
  * Inspect `sensor.<tv_name>_brand_profile` to view the currently configured brand profile and active OEM brand code in real time.

### 4. Do I Need an Android Phone or Android TV to Use This?
* **No.** VIDAA OS is a Linux-based operating system, not Android TV.
* **No Android Hardware/OS Required:** You do not need an Android phone, tablet, or emulator to set up or run this integration. Home Assistant connects directly to the TV over your local network.
* **Why the APK is Mentioned:** The vendor pre-signs its client mutual TLS certificate (`.p12` bundle) inside the publicly available VIDAA remote app package (`.apk`). Because an `.apk` is simply an unencrypted ZIP archive, you can open and extract it on any computer (Windows, macOS, Linux) with standard tools like `unzip` or 7-Zip without ever owning an Android device.

---

## 📊 Diagnostic Logs & Bug Reporting

If you continue to experience problems:

1. Enable the integration's diagnostic switch: `switch.<tv_name>_debug_logging`.
2. Reproduce the problem (e.g. attempt to turn on, send a key, or change inputs).
3. Download the sanitized diagnostic file from **Settings** → **Devices & Services** → **Hisense VIDAA TV** → **⋮** → **Download diagnostics**.
4. Open an issue on GitHub: [`https://github.com/stevene1919/hisense_vidaa/issues`](https://github.com/stevene1919/hisense_vidaa/issues) and attach the sanitized diagnostics JSON file along with relevant log excerpts.
