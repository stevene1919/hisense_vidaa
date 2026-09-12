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

## 🔒 4. Firewall & Port Reference

The TV and Home Assistant communicate over the following local network ports:

| Port | Protocol | Purpose | Direction |
| :--- | :--- | :--- | :--- |
| **`36669`** | TCP / TLS | TV Internal MQTT Broker (Commands, State, Pairing) | HA $\rightarrow$ TV |
| **`38400` / `18400`** | TCP / HTTP | UPnP / DLNA Device Description & Clock Sync | HA $\rightarrow$ TV |
| **`9` / `7`** | UDP | Wake-on-LAN Subnet Directed Broadcast | HA $\rightarrow$ TV / Broadcast |
| **`1900`** | UDP | SSDP / UPnP Discovery Broadcast | Broadcast $\leftrightarrow$ Both |
| **`5353`** | UDP | mDNS / Zeroconf Network Discovery | Broadcast $\leftrightarrow$ Both |
