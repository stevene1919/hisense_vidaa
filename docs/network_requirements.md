# 🌐 Network Requirements & Best Practices

To ensure reliable, long-term operation of the Hisense VIDAA TV integration, please review the following network topology recommendations.

---

## ⚡ 1. Internet & DNS Connectivity

> [!IMPORTANT]
> **Outbound Internet & Unblocked DNS Required During Pairing & Token Renewal**:
> 
> Hisense smart TVs running VIDAA OS require active outbound internet connectivity and unblocked DNS resolution to authenticate with VIDAA cloud services during the initial 4-digit PIN pairing sequence and subsequent 30-day token renewals.
> 
> - If your TV is hosted on an **isolated IoT VLAN** without internet access, or if network ad-blockers (e.g., AdGuard Home, Pi-hole) block Hisense/VIDAA telemetry/auth domains, the TV will reject the pairing request or fail to refresh tokens.
> - Ensure the TV has unblocked outbound internet access during initial setup and periodic token renewal.

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
