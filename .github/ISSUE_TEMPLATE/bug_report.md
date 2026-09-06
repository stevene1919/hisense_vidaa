---
name: "🐛 Bug Report"
about: "Report a bug or issue with Hisense VIDAA TV integration"
title: "[BUG]: "
labels: ["bug"]
assignees: ""
---

### 🧪 Diagnostic Test Commands
Before opening a bug report, running the built-in diagnostic tool against your TV's IP address can often pinpoint the exact issue (firmware compatibility, certificate error, or network block):

```bash
# 1. Full Diagnostic Report (Recommended - Paste output below):
python3 test_client.py report --ip <YOUR_TV_IP>

# 2. Quick 3-Tier Connectivity & MQTT Broker Probe:
python3 test_client.py ping --ip <YOUR_TV_IP>

# 3. Test Raw SSL/TLS Negotiation & Certificates:
python3 test_client.py test-ssl --ip <YOUR_TV_IP>
```

### ✅ Prerequisites
- [ ] The TV is powered ON and connected to the same local network / subnet as Home Assistant.
- [ ] Outbound WAN / Internet & DNS resolution are unblocked on the TV (required by VIDAA OS for token handshakes).
- [ ] Client certificates (`cert.pem` and `key.pem`) are present in `certs/`.
- [ ] I have restarted Home Assistant and verified the issue persists.

### ℹ️ Environment & Versions
- **Home Assistant Version:** e.g. 2026.5.4
- **Integration Version:** e.g. v1.5.0
- **TV Model & Firmware Build:** e.g. 65U7G / VIDAA U6 / Build V0000.09.09U.P1027

### 📝 Describe the Bug
A clear and concise description of what the issue is.

### 👣 Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. See error

### 📋 CLI Diagnostics Report Output (`test_client.py report`)
```text
(Paste the output from `python3 test_client.py report --ip <TV_IP>` here)
```

### 🪵 Home Assistant Logs / Tracebacks
```bash
(Paste relevant logs or error tracebacks here)
```
