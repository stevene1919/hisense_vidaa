# 🛠️ Advanced Installation, Development & Lifecycle Guide

This guide covers advanced deployment methods for the **VIDAA Smart TV Integration**, including direct Git cloning, tracking pre-release/beta branches, Git submodule management, air-gapped offline installations, standalone CLI diagnostics, and clean uninstallation.

> [!NOTE]
> For standard installations, using **HACS** (Home Assistant Community Store) or extracting the official release archive is recommended. See [Beginner's Quick Start Guide](quick_start_beginners.md).

---

## 🧭 Overview of Advanced Methods

| Method | Target Audience | Primary Use Case |
| :--- | :--- | :--- |
| **[1. Git Clone Deployment](#1-git-clone-deployment)** | Power users, developers | Track cutting-edge fixes on `main` before HACS releases |
| **[2. Testing Pre-Release Branches](#2-testing-pre-release-branches)** | Testers, bug reporters | Verify PRs and bug fix branches (e.g. `feat/ssl-cert-validation`) |
| **[3. Git Submodule Integration](#3-git-submodule-integration)** | Infrastructure-as-code users | Manage `/config` as a version-controlled monorepo |
| **[4. Standalone CLI Diagnostics](#4-standalone-cli-diagnostics-without-home-assistant)** | Network & TV debuggers | Test TLS, pairing, and UPnP without running Home Assistant |
| **[5. Offline / Air-Gapped Setup](#5-offline--air-gapped-installation)** | Isolated smart home setups | Install on VLANs with blocked WAN / internet access |
| **[6. Clean Removal & Uninstallation](#6-clean-removal--uninstallation)** | Any user | Completely delete integration, entities, and clean up certs |

---

## 1. Git Clone Deployment

Deploying via Git allows you to pull updates directly using `git pull` without waiting for HACS releases.

### Architecture Warning (Avoid Nested Component Collision)
The repository root contains developer tooling (`test_client.py`, tests, documentation, and metadata). Home Assistant expects the component directory to be located at:
```text
/config/custom_components/vidaa/
├── manifest.json
├── __init__.py
└── ...
```
> [!CAUTION]
> **Do not clone the repository directly into `/config/custom_components/vidaa/`**. 
> Doing so places the repository root (and extraneous developer files) into Home Assistant's component loader path, causing loader errors.

### Recommended Git Setup (Symlink Method)
Clone the repository into a separate scratch or projects folder, and symlink the inner component:

```bash
# 1. SSH into your Home Assistant server or open Terminal
cd /config

# 2. Clone the repository into a development directory
git clone https://github.com/stevene1919/hisense_vidaa.git hisense_vidaa_repo

# 3. Create the custom_components directory if it does not exist
mkdir -p custom_components

# 4. Symlink the integration component into custom_components
ln -s /config/hisense_vidaa_repo/custom_components/vidaa /config/custom_components/vidaa

# 5. Restart Home Assistant to load the component
```

To update to the latest commit on `main`:
```bash
cd /config/hisense_vidaa_repo
git pull origin main
# Restart Home Assistant
```

---

## 2. Testing Pre-Release Branches

If you are collaborating on an open issue or testing an unreleased fix (e.g. `feat/ssl-cert-validation`):

```bash
cd /config/hisense_vidaa_repo

# Fetch all remote branches
git fetch origin

# Switch to the target feature or fix branch
git checkout <branch_name>

# Restart Home Assistant to load the branch's code
```

When testing is complete, return to the stable branch:
```bash
git checkout main
git pull origin main
```

---

## 3. Git Submodule Integration

If you track your entire Home Assistant `/config` folder in a private Git repository (e.g., Forgejo, GitLab, or GitHub):

```bash
cd /config

# Add the integration as a Git submodule inside your components directory
git submodule add https://github.com/stevene1919/hisense_vidaa.git custom_components/hisense_vidaa_submodule

# Symlink the inner component
ln -s hisense_vidaa_submodule/custom_components/vidaa custom_components/vidaa

# Commit the submodule reference in your config repository
git add .gitmodules custom_components/
git commit -m "feat(submodule): add vidaa integration submodule"
```

To update the submodule:
```bash
git submodule update --remote custom_components/hisense_vidaa_submodule
```

---

## 4. Standalone CLI Diagnostics (Without Home Assistant)

The repository includes standalone diagnostic utilities ([`scripts/test_client.py`](../scripts/test_client.py) and [`scripts/debug_tv.py`](../scripts/debug_tv.py)) that can run from **any machine** on your local network (Linux, macOS, or Windows WSL). You do not need Home Assistant running to inspect TV telemetry, verify SSL certificates, or test PIN pairing.

### Setting Up a Virtual Environment

```bash
# 1. Clone the repository on your workstation or laptop
git clone https://github.com/stevene1919/hisense_vidaa.git
cd hisense_vidaa

# 2. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install the required client dependencies
pip install aiomqtt cryptography defusedxml
```

### Useful Standalone Commands

```bash
# Full diagnostic report (ping, TLS cipher, UPnP, clock drift, and auth probe)
python3 scripts/test_client.py report --ip 192.168.50.12 --probe

# Quick 3-tier connectivity ping
python3 scripts/test_client.py ping --ip 192.168.50.12

# Inspect UPnP / DLNA device services & clock drift
python3 scripts/test_client.py upnp --ip 192.168.50.12

# Test raw SSL/TLS certificate negotiation
python3 scripts/test_client.py test-ssl --ip 192.168.50.12 --cert certs/cert.pem --key certs/key.pem

# Interactive PIN pairing test
python3 scripts/test_client.py auth --ip 192.168.50.12 --profile auto
```

> For full CLI command arguments and streaming options, see the **[CLI Testing & Diagnostic Tools Guide](cli_tools.md)**.

---

## 5. Offline / Air-Gapped Installation

For privacy-centric smart homes where Home Assistant and the TV operate on an isolated IoT VLAN without internet access:

1. **Download Release Archive on an Internet-Connected Machine**:
   - Download `vidaa.zip` from the [Latest Releases](https://github.com/stevene1919/hisense_vidaa/releases).
2. **Transfer to Home Assistant Host**:
   - Via Secure Copy (`scp`):
     ```bash
     scp vidaa.zip <username>@<homeassistant_ip>:/tmp/
     ```
   - Or copy via local Samba / SMB network share into `/config/`.
3. **Extract to `custom_components`**:
   ```bash
   mkdir -p /config/custom_components/vidaa
   unzip /tmp/vidaa.zip -d /config/custom_components/vidaa/
   ```
4. **Copy Certificates**:
   - Place client certificates in `/config/ssl/` (e.g. `/config/ssl/remotenow_2018_cert.pem` and `key.pem`).
5. **Restart Home Assistant**:
   - Navigate to **Settings → System → Restart** and proceed with standard UI integration setup.

---

## 6. Clean Removal & Uninstallation

To cleanly remove and uninstall the **VIDAA Smart TV** integration from Home Assistant:

### 6.1 Delete Config Entry
1. In Home Assistant, navigate to **Settings → Devices & Services → Integrations**.
2. Locate the **VIDAA Smart TV** integration card.
3. If you have multiple configured TVs, select the specific TV you wish to remove.
4. Click the three vertical dots (`⋮`) menu in the card header and click **Delete**.
5. Confirm the deletion when prompted.

> [!NOTE]
> Deleting the config entry automatically unregisters associated entity devices, unloads custom services (when no other TVs remain configured), and cancels active background MQTT network loops.

### 6.2 Clean Up Certificates (Optional)
If you placed client certificates or key files in `/config/ssl/vidaa/` (or `/config/ssl/` / `/ssl/`), and no other tools or TV instances require them:
1. Open your Home Assistant Terminal, SSH session, or File Editor.
2. Delete the certificate files from the directory (e.g. `rm -rf /config/ssl/vidaa` or delete `El.p12`).

### 6.3 Uninstall Component
- **Via HACS (Recommended)**:
  1. Navigate to **HACS → Integrations**.
  2. Find **VIDAA Smart TV** in the list of installed integrations.
  3. Click the three vertical dots (`⋮`) on the integration row and select **Remove**.
  4. Confirm the removal.
- **Manual Installation**:
  1. Connect via SSH or Terminal to your Home Assistant host.
  2. Delete the integration directory:
     ```bash
     rm -rf /config/custom_components/vidaa
     ```

### 6.4 Restart Home Assistant
Restart Home Assistant to flush cached Python modules:
- Navigate to **Settings → System → Restart** (top right) → **Restart Home Assistant**.
