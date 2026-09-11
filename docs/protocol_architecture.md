# 🔬 VIDAA Protocol & Cryptographic Architecture

This document provides a comprehensive technical breakdown of the Hisense VIDAA OS MQTT communication protocol, reverse-engineered from `libmqttcrypt.so` and the official VIDAA / RemoteNOW Android applications.

---

## 🧭 Communication Overview

Hisense smart TVs running VIDAA OS host an internal MQTT broker listening on TLS port `36669`. Communication requires mutual TLS with client certificates and a challenge-response pairing sequence.

```mermaid
sequenceDiagram
    autonumber
    participant HA as Home Assistant (Client)
    participant TV as Hisense VIDAA TV (:36669)
    
    Note over HA,TV: 1. TLS v1.2 Mutual Handshake (Client Cert & Key)
    HA->>TV: Connect MQTT (Dynamic Username + Salt Hash)
    TV-->>HA: CONNACK (rc: 0)
    
    Note over HA,TV: 2. Challenge-Response PIN Handshake
    HA->>TV: Subscribe: /remoteapp/mobile/<client_id>/ui_service/data/#
    HA->>TV: Publish: .../actions/vidaa_app_connect
    TV-->>HA: Display 4-digit PIN on screen & publish authentication challenge
    HA->>TV: Publish: .../actions/authenticationcode {"authNum": <PIN>}
    TV-->>HA: Publish: {"result": 1} (PIN Accepted)
    
    Note over HA,TV: 3. Session Token Issuance
    HA->>TV: Publish: .../platform_service/<client_id>/data/gettoken
    TV-->>HA: Publish: Token Payload (Access Token [2 days], Refresh Token [30 days])
    
    Note over HA,TV: 4. Normal Runtime Operations
    HA->>TV: Reconnect with Access Token as MQTT password
    HA->>TV: Publish Commands (actions/sendkey, actions/changesource, etc.)
    TV-->>HA: Push State Broadcasts (volumechange, tvsleep, ui_service/state)
```

---

## 🔐 Multi-Tier Authentication Models

The TV's internal MQTT broker (`libmqttcrypt`) enforces a strict client ID whitelist format during initial pairing: `${mac}$his${md5_prefix}_vidaacommon_001`. The suffix must be `_vidaacommon_001` or the connection is rejected (`rc: 2`).

### 🟢 1. Generation 2: Modern VIDAA 2.0 (`libmqttcrypt.so` / Firmware `Q0704`+)
- **Pattern:** `PATTERN = "38D65DC30F45109A369A86FCE866A85B"`
- **Client ID:** `f"{mac}$his${md5(f'{PATTERN}${mac}')[:6]}_vidaacommon_001"`
- **Username:** `f"his${timestamp ^ 6239759785777146216}"` *(XOR 64-bit mask `0x5689ab4102ef1908`)*
- **Cross-Sum:** `sum_digit = sum(int(d) for d in str(timestamp)) % 10`
- **Modern Salt:** `h!i@s#$v%i^d&a*a` *("hisvidaa")*
- **Password Hash:** `md5(f"{timestamp}${md5(f'his{sum_digit}h!i@s#$v%i^d&a*a')[:6]}").upper()`

### 🟡 2. Generation 1: RemoteNOW (Standard / Firmware `P1027` and older)
- **Client ID:** `f"{mac}$his${md5(f'{PATTERN}${mac}')[:6]}_vidaacommon_001"`
- **Username:** `f"his${timestamp}"`
- **Standard Salt:** `h*i&s%e!r^v0i1c9` *("hiserv0i1c9")*
- **Password Hash:** `md5(f"{timestamp}${md5(f'his{sum_digit}h*i&s%e!r^v0i1c9')[:6]}").upper()`

### ⚪ 3. Generation 0: Legacy Static (Pre-2022)
- **Username:** `hisenseservice`
- **Password:** `multimqttservice`
- **Pairing:** Bypasses PIN challenge; connects directly with static credentials.

---

## ⏳ Session Token Lifecycle & Auto-Renewal

```mermaid
stateDiagram-v2
    [*] --> InitialPairing: First Setup / PIN
    InitialPairing --> TokenIssued: 4-digit PIN verified
    TokenIssued --> ActiveSession: Store Access Token (48h) + Refresh Token (30d)
    
    ActiveSession --> ActiveSession: Commands & Live State (Normal Operation)
    ActiveSession --> Refreshing: Token Expired (>48h) or Connection rc:4/5
    
    Refreshing --> ActiveSession: New 48h Access Token Issued
    Refreshing --> InitialPairing: Refresh Token Expired (>30d offline)
```

1. **Access Token (`accesstoken`):** Valid for **48 hours (2 days)**. Used directly as the MQTT password for all runtime commands and queries.
2. **Refresh Token (`refreshtoken`):** Valid for **30 days**. When the access token expires, the client connects to `platform_service/data/tokenissuance` using the refresh token to request a new access token without requiring a new PIN.

---

## 📡 MQTT Topic Hierarchy Reference

| Topic Path | Direction | Purpose |
| :--- | :--- | :--- |
| `/remoteapp/tv/ui_service/{client_id}/actions/vidaa_app_connect` | `Publish` | Initiate pairing handshake & trigger on-screen PIN |
| `/remoteapp/tv/ui_service/{client_id}/actions/authenticationcode` | `Publish` | Submit user-entered 4-digit PIN |
| `/remoteapp/tv/ui_service/{client_id}/actions/authenticationcodeclose` | `Publish` | Dismiss PIN modal on TV screen |
| `/remoteapp/tv/platform_service/{client_id}/data/gettoken` | `Publish` | Request initial access/refresh token pair |
| `/remoteapp/tv/remote_service/{client_id}/actions/sendkey` | `Publish` | Dispatch remote keypress (e.g. `KEY_POWER`, `KEY_HOME`) |
| `/remoteapp/tv/ui_service/{client_id}/actions/changesource` | `Publish` | Switch input source (`{"sourceid": "HDMI1", "sourcename": "HDMI1"}`) |
| `/remoteapp/tv/ui_service/{client_id}/actions/launchapp` | `Publish` | Launch installed Smart TV application (`{"appId": "...", "name": "..."}`) |
| `/remoteapp/tv/ps_service/{client_id}/actions/changevolume` | `Publish` | Set absolute volume level (`0`–`100`) |
| `/remoteapp/mobile/{client_id}/ui_service/data/authentication` | `Subscribe` | Receive TV pairing challenge response |
| `/remoteapp/mobile/{client_id}/platform_service/data/tokenissuance` | `Subscribe` | Receive issued / refreshed authentication tokens |
| `/remoteapp/mobile/broadcast/ui_service/state` | `Subscribe` | Real-time push notifications for TV power and UI state |
| `/remoteapp/mobile/broadcast/platform_service/actions/volumechange`| `Subscribe` | Real-time push notifications for volume and mute changes |
| `/remoteapp/mobile/broadcast/ui_service/volume` | `Subscribe` | Secondary broadcast topic for volume changes |
| `/remoteapp/mobile/{client_id}/ui_service/data/sourcelist` | `Subscribe` | Response containing available physical inputs |
| `/remoteapp/mobile/{client_id}/ui_service/data/applist` | `Subscribe` | Response containing installed Smart TV applications |
