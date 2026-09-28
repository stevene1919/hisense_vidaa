# 🌐 Network Requirements & Best Practices

To ensure reliable, long-term operation of the Hisense VIDAA TV integration, please review the following network topology recommendations.

---

## ⚡ 1. 100% Local LAN Control & Zero Internet Dependency

> [!NOTE]
> **No Cloud or Internet Access Required**:
> 
> The `hisense_vidaa` integration is **100% local (`iot_class: local_push`)**. Home Assistant connects directly to the TV's embedded MQTT broker on port `36669` over your local subnet (`LAN`).
> 
> - **Local Authentication & Token Renewal**: The initial 4-digit PIN challenge-response handshake and subsequent 30-day token renewals are computed and validated **entirely on the TV hardware itself**. No cloud authentication servers, external API endpoints, or internet bridges are contacted.
> - **Isolated IoT VLAN Friendly**: The TV can be safely placed on an isolated IoT VLAN without internet access (WAN blocked), provided Home Assistant can reach the TV on port `36669` (and UDP port `9` for Wake-on-LAN).
> - **Official App vs Integration**: While official Hisense smartphone apps (*RemoteNOW* / *VIDAA Smart Remote*) require internet connectivity for cloud account logins and catalog syncing, the underlying hardware control channel on the TV is local. This integration interacts directly with that local channel, bypassing the cloud entirely.

---

## 📌 2. Static DHCP Reservation (Fixed IP)

While the integration tracks the TV across IP changes via hardware MAC matching (ARP / UPnP discovery), setting a **static DHCP reservation** on your router or gateway is strongly advised:

- **Guarantees immediate reconnection** after TV reboots or router restarts.
- **Prevents lease expiration delays** where Home Assistant might temporarily mark the media player entity as unavailable.
- **Eliminates ARP cache resolution latency** on busy home networks.

---

## 🔌 3. Wake-on-LAN (WoL) & Network Power-On

> [!WARNING]
> **Hardware Limitation Notice (2020–2022 Models)**:
> On several 2020–2022 VIDAA models (notably the **A6 / A53 / A7 series** running VIDAA U4/U5), **Wake-on-LAN magic packets do not work—even over a direct wired Ethernet connection**. 
> 
> The mainboard hardware depowers the Ethernet PHY chip completely in deep sleep to comply with $\le 0.5\text{W}$ energy standards, dropping the physical link.
> 
> **To turn on these TVs reliably from Home Assistant**:
> - Ensure **Fast Power On is ON** (`Settings → System → Advanced Settings → Fast Power On`).
> - When Fast Power On is enabled, Home Assistant wakes the display instantly via **MQTT `KEY_POWER`** over the existing local socket, bypassing the need for WoL magic packets.
> - For true cold-boots from unpowered states, use **HDMI-CEC** or an **IR blaster**.

For models that do support hardware Wake-on-LAN:
1. **Prefer Wired Ethernet**: Many VIDAA TV models power down their Wi-Fi radios in standby, while supported wired Ethernet NICs maintain a low-power listening state for magic packets.
2. **Enable Wake-on-LAN in TV Settings**:
   - Navigate to **Settings → Network / System → Advanced Settings → Wake on LAN / Power on by Apps** and ensure it is switched **ON**.
3. **Enable WoL in Integration Options**:
   - In Home Assistant, go to **Settings → Devices & Services → Hisense VIDAA TV → Configure** and check **Enable Wake-on-LAN**.

---

## ⚡ 4. Recommended TV Power & Standby Settings (Prevent Token Loss)

### 🌍 Regulatory Context & Two-Tier Standby Architecture

National energy efficiency regulations—such as **Australian GEMS (AS/NZS 62087)**, **European Ecodesign / Lot 26 (Directive 2019/2021)**, and **Energy Star**—mandate that smart TVs implement automated power-down mechanisms when inactive.

To comply with these standards, VIDAA OS implements a **two-tier standby architecture**:

1. **Tier 1: Networked Standby ("Fast Power On" / `fake_sleep`)**:
   - Triggered when you turn the TV off via the remote control or Home Assistant.
   - The display panel is powered down, but the TV's application processor maintains a low-power network-listening state ($\approx 1.5\text{W}$–$2.5\text{W}$).
   - The embedded MQTT broker (`36669`) continues running in RAM. Issued access and refresh tokens remain intact in volatile memory.
2. **Tier 2: Regulatory Deep Standby (Auto-Power-Down)**:
   - Mandated to trigger when an active video signal is lost (e.g. **15 minutes** default) or after 4 hours of remote inactivity.
   - To achieve the legally required deep standby threshold ($\le 0.5\text{W}$), VIDAA OS shuts down the application processor and terminates all background userland daemons—**including the internal MQTT broker**.
   - **Volatile Token Storage**: VIDAA does not persist dynamically paired session tokens to flash storage (to prevent NAND flash degradation and secure credential leakage). When the TV transitions to Tier 2 deep sleep, **all issued tokens in volatile RAM are wiped**.
   - Upon next power-up or wake, the broker starts fresh with an empty credential table. Reconnection attempts with previously valid tokens are actively rejected with **`rc: 4`** (*Bad username or password*).

### 🛠️ Recommended TV Configuration

> For the comprehensive model-by-model settings matrix (VIDAA U4 through 2024+) and multi-device setup recommendations (Chromecast, Apple TV, PC monitors), see the dedicated **[TV Power, Standby & Network Settings Guide](power_and_standby_settings.md)**.

To prevent connected HDMI devices (such as **Chromecast with Google TV**, **Apple TV**, or gaming consoles) from inadvertently dragging the TV into a Tier 2 broker-killing shutdown when they sleep:

| Setting | Recommended Value | Path in TV Menu | Reason |
| :--- | :--- | :--- | :--- |
| **Fast Power On** | **ON** | `Settings → System → Advanced Settings → Fast Power On` | Keeps the network interface and internal MQTT broker alive in Tier 1 standby so Home Assistant can read states and send commands. |
| **Auto Standby with No Signal** | **OFF** | `Settings → System → Timer Settings → Auto Standby with No Signal` | Prevents the TV from initiating an aggressive Tier 2 shutdown when connected HDMI streaming boxes sleep or cut their video output. |
| **Auto Sleep / Idle Standby** | **OFF** | `Settings → System → Timer Settings → Auto Sleep` | Prevents automated energy-saving shutdowns after continuous idle periods that kill background services. |
| **Power On Mode** | **Standby** | `Settings → System → Advanced Settings → Power On Mode` | Ensures the TV recovers cleanly to standby following any mains power restoration. |

---

## 🔒 5. IoT VLAN Firewall & Port Matrix

If your Hisense TV is placed on an isolated **IoT VLAN** separate from your Home Assistant server (e.g. `HA_VLAN` $\leftrightarrow$ `IOT_VLAN`), configure the following firewall rules on your router/gateway:

### 📋 Port & Protocol Matrix

| Port | Protocol | Traffic Type | Direction | Purpose | Required? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`36669`** | TCP | Unicast (TLS) | HA $\rightarrow$ TV | **Core TV MQTT Control Channel** (Pairing, commands, state updates, source switching, volume) | **Mandatory** |
| **`56669`** | TCP | Unicast (Plain) | HA $\rightarrow$ TV | **Legacy Plaintext MQTT Channel** (Pre-2018 / legacy models operating without SSL) | *Optional (Legacy only)* |
| **`38400`** | TCP | Unicast (HTTP) | HA $\rightarrow$ TV | **UPnP Device Description (`rendererdevicedesc.xml`) & Clock Header Sync** (Modern VIDAA) | **Recommended** |
| **`18400`** | TCP | Unicast (HTTP) | HA $\rightarrow$ TV | **UPnP Device Description (`rendererdevicedesc.xml`) & Clock Header Sync** (Alternate VIDAA port) | **Recommended** |
| **`9` / `7`** | UDP | Directed Broadcast / Unicast | HA $\rightarrow$ TV | **Wake-on-LAN (WoL)** (Power-on magic packet to wake TV from deep standby) | **Recommended** |
| **`1900`** | UDP | Multicast (`239.255.255.250`) | Both / Multicast | **SSDP / UPnP Auto-Discovery** (Automatic discovery of TV IP and device metadata) | *Optional (Discovery)* |
| **`5353`** | UDP | Multicast (`224.0.0.251`) | Both / Multicast | **mDNS / Zeroconf Network Discovery** | *Optional (Discovery)* |

---

### 🛡️ Recommended Inter-VLAN Firewall Policy Rules

1. **HA to TV (Unicast TCP/UDP)**:
   - **Source**: Home Assistant Server IP (`HA_IP`)
   - **Destination**: Hisense TV IP (`TV_IP`)
   - **Allowed Ports**: `TCP 36669, 56669, 38400, 18400`, `UDP 9, 7`
   - **Action**: `ACCEPT`
2. **TV to HA (Established / Related Return Traffic)**:
   - Allow established and related connection states (`conntrack state ESTABLISHED, RELATED`) from `IOT_VLAN` to `HA_VLAN`.
   - The TV does **not** need to initiate new inbound connections to Home Assistant.
3. **Cross-Subnet SSDP Discovery (Optional)**:
   - SSDP multicast (`UDP 1900` to `239.255.255.250`) does not naturally cross VLAN boundaries. If you want automatic SSDP discovery across subnets, enable an **mDNS / SSDP relay** (such as `smcroute`, `igmpproxy`, or `udp-broadcast-relay-redux`) on your gateway.
   - Alternatively, simply enter the TV's IP address directly during integration setup to bypass SSDP discovery.
4. **Cross-Subnet Wake-on-LAN (WoL)**:
   - Standard WoL packets broadcast to `255.255.255.255`. For cross-VLAN wake-on-LAN, configure your gateway to permit **Subnet Directed Broadcast** (e.g. `192.168.50.255:9`) or use a UDP broadcast relay daemon.

