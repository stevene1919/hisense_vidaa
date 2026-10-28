# Release Tag: v3.0.0
# Release Title: v3.0.0 — 🎉 1,000 Downloads Community Celebration Edition

# 🎉 1,000 Downloads Community Celebration Edition

This milestone release celebrates surpassing **1,000 active downloads** on HACS in just over a week since our previous major release! 

A heartfelt thank you to our vibrant open-source smart home community for your testing, feedback, and contributions that helped shape this release:

**PR's:** @Syax89 @mzhur  
**Issues:** @cyranius669 @Mrgrafcox @ThatCKx @yagoid @lvbubi @ndesgranges  
*(Special thanks also to everyone in the Home Assistant community who submitted anonymous diagnostic traces and starred the repository!)*

---

### ☕ Support the Project
If this integration has added value to your smart home setup, consider buying me a coffee to support continued development and maintenance:

[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

---

## 🌟 What's New & Hardened in v3.0.0

### 📡 Live MQTT Device Registry Enrichment & Sanitization (`discovery.py`, `tv/state.py`, `entity.py`, `__init__.py`)
- **Sanitized Placeholder Manufacturers**: Replaced generic UPnP `<manufacturer>SmartTV</manufacturer>` placeholders using SSDP brand codes (`BRAND_MAP`), eliminating unsightly "SmartTV" labels on device cards.
- **Live Device Registry Telemetry**: Automatically updates Home Assistant's official Device Registry with the TV's true hardware build (`model_name`, `manufacturer`, `uVersion`) received over MQTT on boot.
- **HA 2025.1+ Deprecation Compliance**: Modernized device lookups using `async_get_device_by_identifier` with backwards-compatible fallback, preventing core deprecation warnings.

### 🎨 Dynamic MDI App & Source Branding Icons (`media_player.py`)
- Automatically resolves active inputs and streaming applications to intuitive Material Design Icons:
  - **Streaming Apps**: Netflix, YouTube, Prime Video, Disney+, Plex, Spotify, Apple TV, Web Browser.
  - **Hardware Sources**: Dynamic HDMI port icons (`mdi:hdmi-port`), Live TV tuner (`mdi:television-classic`), and AV inputs.

### 🧩 Multi-Brand VIDAA OS Protocol Preparation (`crypto.py`, `client.py`, `flow_discovery.py`)
- Parameterized brand identifiers across pairing handshakes, dynamic username generation, client ID formatting, and password hashing (`"his"`, `"tos"`, `"loe"`, `"sch"`, `"aka"`, `"bek"`, `"tel"`, `"bus"`, `"vic"`).
- Establishes the core architectural and cryptographic foundation in preparation for the upcoming universal VIDAA integration rebrand (Toshiba, Loewe, Schneider, Akai, Beko, Telefunken, Bush).

### 🥇 Integration Quality Scale (Gold Tier) Hardening & Documentation
- **Stale Device Cleanup**: Implemented `async_remove_config_entry_device` in `__init__.py` allowing clean removal of orphaned devices.
- **Quality Scale Tracking**: Added official `quality_scale.yaml` documenting adherence across Bronze, Silver, and Gold IQS rules.
- **Expanded Documentation**: Complete guides for local-push architecture, diagnostic entities, supported limitations, and real-world automation recipes.

### 🧪 Test Suite Expansion
- Test coverage expanded to **221 unit tests passing** across stale device cleanup, dynamic source icons, brand credentials derivation, deprecation-free device registry enrichment, and telemetry parsers.

---

**Full Changelog**: https://github.com/stevene1919/hisense_vidaa/compare/v2.11.1...v3.0.0
