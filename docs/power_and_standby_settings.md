# ⚡ VIDAA TV Power, Standby & Network Settings Guide

This guide details optimal TV system and power configurations to ensure continuous Home Assistant connectivity, reliable Wake-on-LAN, and zero authentication token loss across all Hisense VIDAA OS generations.

---

## 🧭 The Core Principle: Tier 1 vs Tier 2 Standby

Hisense smart TVs implement a **two-tier standby architecture** driven by statutory national energy efficiency mandates (e.g. **Australian GEMS / AS/NZS 62087**, **European Ecodesign / Lot 26 / Directive 2019/2021**, and **US Energy Star**):

```
+-----------------------------------------------------------------------------------+
|                               TV POWER STATES                                     |
+-----------------------------------------------------------------------------------+
|  [ON]                Screen active, UI responsive, MQTT broker active             |
|    |                                                                              |
|    +-- (User presses Remote Power / HA turn_off)                                 |
|    |                                                                              |
|    v                                                                              |
|  [TIER 1 STANDBY]    "Fast Power On" / Networked Standby (~1.5W - 2.5W)           |
|                      Display off, SoC in low-power listen, broker running in RAM  |
|                      ==> Tokens preserved, HA commands & sensors remain alive     |
|                                                                              |
|    +-- (No signal timer trips / 4h idle auto-sleep)                              |
|    |                                                                              |
|    v                                                                              |
|  [TIER 2 STANDBY]    Regulatory Deep Sleep (<= 0.5W)                              |
|                      SoC powered down, broker process killed                      |
|                      ==> Volatile RAM flushed: TOKENS WIPED                       |
+-----------------------------------------------------------------------------------+
```

### Why Tokens Are Lost in Tier 2
VIDAA stores dynamic session credentials (`access_token` and `refresh_token`) exclusively in **volatile system RAM** (`libmqttcrypt.so`). Tokens are deliberately never written to onboard NAND flash (to prevent wear and avoid plain-text credential retention). 

When statutory energy-saving timers force the TV into a Tier 2 shutdown, the application processor powers down and wipes RAM. Upon the next power-on, the broker boots cold with an empty token table and actively rejects Home Assistant's stored credentials (`rc: 4`).

---

## 📊 Optimal Settings Matrix by VIDAA OS Version

### 1. VIDAA U4 & U5 (2020–2022 Models)
*Examples: A6, A7, U7G, U8G series*

| Setting | Recommended Value | Path in TV Menu | Purpose |
| :--- | :--- | :--- | :--- |
| **Fast Power On** | **ON** | `Settings → System → Advanced Settings → Fast Power On` | Keeps network interface and MQTT broker alive in Tier 1 standby. |
| **Auto Standby with No Signal** | **OFF** | `Settings → System → Timer Settings → Auto Standby with No Signal` | Prevents deep Tier 2 shutdown when connected HDMI devices (Chromecast, PC) sleep. Default is 15 min. |
| **Auto Sleep** | **OFF** | `Settings → System → Timer Settings → Auto Sleep` | Prevents automated shutdown after 3h/4h of remote inactivity. |
| **Power On Mode** | **Standby** | `Settings → System → Advanced Settings → Power On Mode` | Ensures TV boots into clean standby after mains power recovery. |
| **Wake on LAN** | **ON (limited)** | `Settings → Network / System → Advanced Settings → Wake on LAN` | Often non-functional on 2020–2022 models even over wired Ethernet (see limitation section below). |
| **Sleep Timer** | **OFF** | `Settings → System → Timer Settings → Sleep Timer` | Ensures no countdown timers inadvertently cut power. |

---

### 2. VIDAA U6 & U7 (2022–2023 Models)
*Examples: A6H, U6H, U7H, U8H, U6K, U7K, U8K series*

| Setting | Recommended Value | Path in TV Menu | Purpose |
| :--- | :--- | :--- | :--- |
| **Fast Power On / Quick Start** | **ON** | `Settings → System → Advanced Settings → Fast Power On` | Maintains low-power networked standby. |
| **Auto Standby with No Signal** | **OFF** | `Settings → System → Timers (or Timer Settings) → Auto Standby with No Signal` | Disables automated energy-saving power cut on signal loss. |
| **Auto Sleep / Idle Standby** | **OFF** | `Settings → System → Timers → Auto Sleep` | Disables 4-hour inactivity timer. |
| **Wake on Wireless Network** | **ON** | `Settings → Network → Wake on Wireless Network` | Keeps Wi-Fi chip in low-power DTIM listening mode (if wired Ethernet unavailable). |
| **Wake on LAN** | **ON** | `Settings → Network → Wake on LAN` | Preserves wired WoL capability. |
| **Wake on Cast** | **ON** | `Settings → Network → Wake on Cast` | Allows casting/DIAL events to wake TV. |
| **CEC Control** | **User preference** | `Settings → Connection → HDMI & CEC → CEC Control` | Toggle if connected HDMI devices inadvertently toggle TV power. |

---

### 3. VIDAA 2.0 / VIDAA OS 7.x & 8.x (2024–2026 Models)
*Examples: U7N, U8N, UX, CanvasTV series*

| Setting | Recommended Value | Path in TV Menu | Purpose |
| :--- | :--- | :--- | :--- |
| **Quick Start / Fast Boot** | **ON** | `Settings → System → Advanced Settings → Quick Start` | Ensures background services remain resident across standby. |
| **Auto Standby with No Signal** | **OFF** | `Settings → System → Timers → Auto Standby with No Signal` | Prevents Tier 2 deep sleep during idle HDMI states. |
| **Energy Saving / Eco Mode** | **Standard / Off** | `Settings → System → Power & Energy → Energy Saving` | Avoids aggressive background daemon culling. |
| **Network Management in Standby** | **Always On** | `Settings → Network → Advanced → Network in Standby` | Explicitly permits network card and broker to stay active. |
| **Wake on LAN / Wi-Fi** | **ON** | `Settings → Network → Wake on LAN / Wake on Wi-Fi` | Enables network-directed wake. |
| **VIDAA Art / Ambient Mode** | **Review settings** | `Settings → System → Advanced Settings → VIDAA Art` | On CanvasTV, adjust ambient sleep timers so panel sleep doesn't force cold shutdown. |

---

## ⚠️ Wake-on-LAN Hardware Limitations (2020–2022 / VIDAA U4 & U5 Era)

Extensive testing confirms that on many budget and mid-range 2020–2022 VIDAA models (such as the **A6, A53, A7, and early U-series**), **Wake-on-LAN (WoL) magic packets fail completely—even over a direct wired Ethernet connection**.

### Why WoL Fails on These Models:
1. **Unpowered Ethernet PHY in Deep Sleep**: To achieve statutory standby power limits ($\le 0.5\text{W}$), the mainboard cuts all DC power rails to the physical Ethernet transceiver (PHY) and Wi-Fi SoC when the display is off. The physical Ethernet link drops entirely (switch link light turns off), making it physically impossible for the network card to receive UDP magic packets.
2. **Firmware WoL Toggle Flaws**: On certain VIDAA U4 and U5 firmware builds, the "Wake on LAN" menu toggle is purely cosmetic or resets its state upon shutdown.

### 💡 The Solution: MQTT Wake via Fast Power On
Because WoL packets cannot wake a depowered network chip, the **only reliable way** to turn on these TVs from Home Assistant is:

1. **Keep Fast Power On = ON**:
   - The TV remains in shallow Network Standby (**Tier 1 / `fake_sleep`**).
   - The network card and internal MQTT broker stay alive.
   - Home Assistant wakes the TV by sending the native `KEY_POWER` command directly over the encrypted local MQTT connection—**zero Wake-on-LAN magic packets required**.
2. **Alternative Cold-Boot Fallbacks**:
   - **HDMI-CEC**: Waking a connected device (e.g. Chromecast, Apple TV, gaming console, or PC with HDMI-CEC) automatically wakes the TV over the HDMI bus.
   - **IR Blaster**: Using a network IR transmitter (e.g. Broadlink RM4, SofaBaton, or Tuya IR) as an emergency cold-boot fallback if mains power is cut.

---

## 🔌 Multi-Device Setup Recommendations

### 1. Chromecast with Google TV / Apple TV / Streaming Sticks
Streaming boxes routinely put their video outputs to sleep after 15–30 minutes of idle ambient screensaver. 
- If **Auto Standby with No Signal** is left at its default (15 minutes), the TV will shut down exactly 15 minutes after the streaming box sleeps, wiping all MQTT credentials.
- **Remedy**: Always disable **Auto Standby with No Signal** when using an external HDMI streaming stick as your primary video source.

### 2. PC / Laptop as Monitor (HDMI)
When used as a desktop computer display:
- When your operating system enters display sleep or powers down the GPU output, the TV transitions to "No Signal".
- Disabling **Auto Standby with No Signal** ensures the TV stays in Tier 1 standby, allowing Home Assistant to manage power or wake the display automatically via presence sensors.

### 3. Gaming Consoles (PS5, Xbox Series X, Nintendo Switch)
- If you have HDMI-CEC enabled (**Settings → Connection → HDMI & CEC**):
  - Enabling **Device Auto Power Off** will turn off your console when the TV turns off.
  - Enabling **TV Auto Power On** will wake the TV when the console controller is pressed.
  - Keep **Fast Power On = ON** so the TV's internal CEC processor coordinates cleanly with Home Assistant's media player source selector.
