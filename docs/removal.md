# 🗑️ Removal & Uninstallation Guide

This guide details the procedure for cleanly removing and uninstalling the **Hisense VIDAA TV** integration from Home Assistant.

---

## 1. Delete Config Entry

1. In the Home Assistant web interface, navigate to **Settings $\rightarrow$ Devices & Services $\rightarrow$ Integrations**.
2. Locate the **Hisense VIDAA TV** integration card.
3. If you have multiple configured TVs, select the TV you wish to remove.
4. Click the three vertical dots (`⋮`) menu in the card header and click **Delete**.
5. Confirm the deletion when prompted.

> [!NOTE]
> Deleting the config entry automatically unregisters associated entity devices, unloads custom services (when no other TVs remain configured), and cancels active background MQTT network loops.

---

## 2. Clean Up Certificates (Optional)

If you placed client certificates or key files in `/config/ssl/hisense_vidaa/` (or `/config/ssl/` / `/ssl/`), and no other tools or TV instances require them:

1. Open your Home Assistant Terminal, SSH session, or File Editor.
2. Delete the certificate files from the directory (e.g. `rm -rf /config/ssl/hisense_vidaa`).

---

## 3. Uninstall Component

### Via HACS (Recommended)
1. Navigate to **HACS $\rightarrow$ Integrations**.
2. Find **Hisense VIDAA TV** in the list of installed integrations.
3. Click the three vertical dots (`⋮`) on the integration row and select **Remove**.
4. Confirm the removal.

### Manual Installation
1. Connect via SSH or Terminal to your Home Assistant host.
2. Delete the integration directory:
   ```bash
   rm -rf /config/custom_components/hisense_vidaa
   ```

---

## 4. Restart Home Assistant

Restart Home Assistant to flush cached Python modules:
- Navigate to **Settings $\rightarrow$ System $\rightarrow$ Restart** (top right) $\rightarrow$ **Restart Home Assistant**.
