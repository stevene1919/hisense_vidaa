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
| **`38400`** | TCP | Unicast (HTTP) | HA $\rightarrow$ TV | **UPnP / DLNA LAN Control (`RenderingControl:1`, `AVTransport:1`, `LanControlInfo`, Clock Sync)** (Modern VIDAA) | **Recommended** |
| **`18400`** | TCP | Unicast (HTTP) | HA $\rightarrow$ TV | **UPnP / DLNA LAN Control (`RenderingControl:1`, `AVTransport:1`, `LanControlInfo`, Clock Sync)** (Alternate VIDAA port) | **Recommended** |
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

---

## ⏰ 6. TV Hardware Clock, NTP Sync & Isolated IoT LANs (WAN-Blocked)

### ⚠️ The Isolated IoT VLAN Clock Drift Problem

Smart TVs running VIDAA OS lack battery-backed hardware Real-Time Clocks (RTC). When completely powered off (e.g. smart plug cutoff, wall switch, or mains power loss) or cold-booted, the internal hardware clock resets to a baseline firmware build epoch.

Under standard consumer setups, VIDAA synchronizes its internal clock through two mechanisms:
1. **DVB / ATSC Broadcast Signal**: Time metadata received via RF digital TV antenna coaxial input.
2. **Public Internet NTP Servers**: Hardcoded NTP pool queries (`UDP 123` to `time.google.com`, `pool.ntp.org`, `time.windows.com`).

When a TV is deployed in a hardened smart home environment:
- **No RF Antenna Connected**: Streaming and smart apps only (HDMI / OTT).
- **Isolated IoT VLAN with WAN Blocked**: All outbound internet access is firewalled to protect privacy and prevent manufacturer telemetry.

In this topology, the TV has **no way to reach public NTP servers**. As a result, its hardware clock can drift significantly (often falling behind by hours, days, or even weeks). While the `hisense_vidaa` integration automatically detects clock drift via UPnP `Date:` headers and compensates for timestamp skew during dynamic MQTT challenge generation, extreme drift can affect TLS certificate validation and token expiry calculation.

### 🛑 The DNS Sinkhole Trap (AdGuard Home / Pi-hole returning 0.0.0.0)

> [!WARNING]
> If you sandbox your TV with AdGuard Home, Pi-hole, or DNS blocklists, a firewall port redirect rule alone is **not sufficient**.

When a blanket block rule (such as `||*$client=hisense-tv`) is applied to sandbox the TV, DNS queries for NTP servers (`au.pool.ntp.org`, `pool.ntp.org`, `time.google.com`) return **`0.0.0.0`** (the default sinkhole null-route).

1. **Why It Breaks**: The Linux network stack in VIDAA OS treats `0.0.0.0` as an invalid destination address (`EADDRNOTAVAIL`). Because DNS resolution fails to return a routable IP, **the TV aborts without ever transmitting any UDP packets to port 123**.
2. **The Symptom**: Your firewall DNAT redirect rule shows **`0 packets / 0 bytes`**, and the TV clock continues to drift.
3. **The Fix (DNS Rewrite)**: You must configure a **DNS Rewrite** so that the TV receives the router's local IP address instead of `0.0.0.0`:

#### A. AdGuard Home (Recommended)
Add the following rules to **Filters $\rightarrow$ Custom filtering rules** (the `$important` modifier overrides client block rules):

```text
||pool.ntp.org^$dnsrewrite=<router_ip>,important,client=<client_id>
||*.pool.ntp.org^$dnsrewrite=<router_ip>,important,client=<client_id>
||time.google.com^$dnsrewrite=<router_ip>,important,client=<client_id>
||time.android.com^$dnsrewrite=<router_ip>,important,client=<client_id>
```
*(Or navigate to **Filters $\rightarrow$ DNS Rewrites** and add `*.pool.ntp.org` $\rightarrow$ `<router_ip>`)*.

#### B. Pi-hole
Navigate to **Local DNS $\rightarrow$ DNS Records** and add:
- `pool.ntp.org` $\rightarrow$ `<router_ip>`
- `time.google.com` $\rightarrow$ `<router_ip>`

#### C. dnsmasq (OpenWrt `/etc/config/dhcp`)
```uci
config domain
	option name 'pool.ntp.org'
	option ip '<router_ip>'
```

Once the DNS rewrite is active:
1. The TV asks for `pool.ntp.org` and immediately receives the router's LAN IP (`<router_ip>`).
2. The TV sends standard UDP 123 packets directly to the gateway's local NTP server.
3. Zero queries leave your LAN, preserving 100% WAN isolation.

### 🛠️ Solution: Gateway NTP DNAT Port Redirection (UDP 123)

To ensure the TV maintains accurate system time without granting it external internet access, configure a **Destination NAT (DNAT) port redirection** rule on your router/gateway. This captures all outbound NTP queries from the TV on `UDP 123` and redirects them to the router's local NTP server (e.g. AdGuard Home, Chrony, ntpd, or Unbound).

#### 1. OpenWrt (Flint 2 / Flint / Archer / etc.)

Add a firewall redirect rule via UCI or `/etc/config/firewall`:

```bash
# Add NTP redirect rule via UCI CLI:
uci add firewall redirect
uci set firewall.@redirect[-1].name='Redirect-IoT-NTP-to-Gateway'
uci set firewall.@redirect[-1].src='iot'
uci set firewall.@redirect[-1].src_dport='123'
uci set firewall.@redirect[-1].proto='udp'
uci set firewall.@redirect[-1].dest_port='123'
uci set firewall.@redirect[-1].target='DNAT'
uci commit firewall
/etc/init.d/firewall reload
```

Or add directly to `/etc/config/firewall`:
```uci
config redirect
	option name 'Redirect-IoT-NTP-to-Gateway'
	option src 'iot'
	option proto 'udp'
	option src_dport '123'
	option dest_port '123'
	option target 'DNAT'
```

#### 2. Linux `nftables`

```nft
table inet fw4 {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        iifname "iot0" udp dport 123 counter redirect to :123
    }
}
```

#### 3. Linux `iptables`

```bash
iptables -t nat -A PREROUTING -i iot0 -p udp --dport 123 -j REDIRECT --to-ports 123
```

#### 4. OPNsense / pfSense Port Forward

- **Interface**: `IoT`
- **Address Family**: `IPv4`
- **Protocol**: `UDP`
- **Destination**: Invert Destination (`[X] Invert match`) $\rightarrow$ `IoT Address`
- **Destination Port Range**: `123 (NTP)` to `123 (NTP)`
- **Redirect Target IP**: `127.0.0.1` (or local IoT Gateway IP)
- **Redirect Target Port**: `123 (NTP)`
- **Description**: `Redirect IoT NTP to Local Gateway`


