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

## 🔌 3. Wired Ethernet for Reliable Wake-on-LAN (WoL)

For dependable power-on control from Home Assistant when the TV is in standby:

1. **Prefer Wired Ethernet**: Many VIDAA TV models completely power down their Wi-Fi radios in deep standby/eco modes to comply with energy consumption standards. The wired Ethernet NIC typically stays powered in a low-power listening state for magic packets.
2. **Enable Wake-on-LAN in TV Settings**:
   - Navigate to **Settings → Network / System → Advanced Settings → Wake on LAN / Power on by Apps** and ensure it is switched **ON**.
3. **Enable WoL in Integration Options**:
   - In Home Assistant, go to **Settings → Devices & Services → Hisense VIDAA TV → Configure** and check **Enable Wake-on-LAN**.

---

## 🔒 4. IoT VLAN Firewall & Port Matrix

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

