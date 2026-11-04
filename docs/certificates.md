# 🔒 Advanced SSL Certificate Setup & Management Guide

> [!TIP]
> ### 🔰 Looking for a Simple 3-Minute Setup?
> If you are a first-time user or beginner, **you do not need to read this technical reference!**  
> Jump straight to the **[Beginner's Quick Start Guide](quick_start_beginners.md)** for a simple 3-step walk-through (zero OpenSSL, zero terminal commands).
>
> *This document is an advanced technical reference for power users needing custom PEM keypairs, OpenSSL conversion commands, Root CA validation, or legacy firmware configurations.*

VIDAA OS smart TVs enforce mutual TLS (mTLS) or client certificate authentication on MQTT port `36669`. To establish a secure connection, Home Assistant must present a valid client certificate and private key.

> [!IMPORTANT]
> ### 📱 No Android Device or Running Mobile App Required!
> A common misconception is that this integration requires an Android smartphone, tablet, or running mobile app. **It does not.**
> - **Direct Local Control**: Home Assistant communicates directly across your local network to the TV's hardware MQTT broker. No mobile device is involved at runtime.
> - **VIDAA OS is Linux**: VIDAA OS is a proprietary embedded Linux OS (not Android TV).
> - **Why is the Android APK Mentioned?**: Hisense/VIDAA distributes the pre-signed client mutual TLS certificate bundled inside their official companion app package (`.apk`). An APK file is literally just a standard ZIP archive. You can download and unzip it on any PC, Mac, Linux machine, or directly on your Home Assistant terminal to obtain the `.p12` file. You never need an Android device or emulator.

---

## 📁 Recommended Certificate Location

To prevent certificate loss when updating integrations via HACS, certificates should **always** be placed in Home Assistant's dedicated SSL/configuration directories:

1. `/config/ssl/` (Recommended standard HA SSL directory)
2. `/ssl/`
3. `/config/certs/`
4. `/config/`

Place your certificate files or PKCS#12 bundles in `/config/ssl/`.

---

## 📋 Supported Certificate Formats & Naming

The integration natively supports both **auto-extracted PKCS#12 archives** (`.p12` / `.pfx`) and **PEM-encoded keypairs** (`.pem` / `.crt` / `.key`):

| Format / Profile | Firmware / Model Generation | Certificate / Bundle Filename | Private Key Filename |
| :--- | :--- | :--- | :--- |
| **PKCS#12 Bundle (Auto-Extracted)** | Any Modern VIDAA / RemoteNOW | `client_mobile_android.p12`, `El.p12`, `rcamobile.p12`, `toshiba.p12`, `loewe.p12`, or `philips.p12` | *(Bundled in .p12 archive)* |
| **Modern VIDAA 2.0 (PEM)** | VIDAA U6+ / U7 (2024+) | `vidaa_client_v01.pem`, `vidaa_client_v02.pem`, `vidaa_2024_cert.pem`, or `vidaa_client.pem` | `vidaa_client_v01.key`, `vidaa_client_v02.key`, `vidaa_2024_key.pem`, or `vidaa_client.key` |
| **Brand-Specific PEM** | Toshiba, Loewe, Philips / TPV, Hisense | `toshiba.crt`, `loewe.crt`, `philips.crt`, `tpv.crt`, or `hisense.crt` | `toshiba.key`, `loewe.key`, `philips.key`, `tpv.key`, or `hisense.key` |
| **RemoteNOW Standard (PEM)** | VIDAA U4 / U5 / U6 (2018–2023) | `vidaa_client_v01.pem`, `remotenow_2018_cert.pem`, or `hisense.crt` | `vidaa_client_v01.key`, `remotenow_2018_key.pem`, or `hisense.key` |
| **Generic / Custom PEM** | Standard fallback for any profile | `cert.pem` | `key.pem` |
| **Optional Root CA** | Optional TLS server verification | `remote_ca.pem` or `RemoteCA.crt` | *(Public root CA)* |

> [!TIP]
> **Automatic Brand & Model Hinting from Certificate Filenames:**
> When you name your certificate files with your TV's brand (e.g. `toshiba.crt` / `toshiba.key`, `loewe.crt` / `loewe.key`, `philips.crt` / `philips.key`, or `tpv.crt` / `tpv.key`), Home Assistant automatically detects your TV brand from the filename during setup. This automatically pre-configures the correct OEM brand salt and device manufacturer without requiring manual selection.

---

## 📦 PKCS#12 (.p12 / .pfx) Setup & Auto-Extraction

The easiest method to configure SSL is providing the vendor PKCS#12 keystore (`El.p12`). When placed in `/config/ssl/`, Home Assistant automatically extracts the certificate and private key into PEM format on the fly—no OpenSSL commands required.

> [!NOTE]
> **Zero Distribution & Independent Sourcing Policy**:
> Proprietary vendor client certificates and application binaries are the intellectual property of Hisense / VIDAA. In accordance with open-source licensing standards and Home Assistant community distribution policies, this integration **never** bundles, distributes, or redistributes proprietary certificates or vendor APK files. Users must independently source the public application package as described below.

---

### Step 1: Obtain the Official Public APK (Any Computer / Browser)

You do **not** need an Android device or Google Play login to download the APK. An `.apk` is simply a standard zip archive distributed by Hisense.

1. On any desktop computer (Windows, macOS, Linux), open your web browser.
2. Search for the official companion application:
   - **Application Name**: **VIDAA Smart TV** (by VIDAA USA, Inc.)
   - **Package Identifier**: `com.universal.remote.multi`
   *(For older 2018–2020 TV models using RemoteNOW, the legacy package identifier is `com.hisense.tv.remotenow`).*
3. Download the free `.apk` package from a reputable public APK mirror (such as [APKMirror](https://www.apkmirror.com) or [APKPure](https://apkpure.com)).

---

### Step 2: Extract `El.p12` from the APK Archive

Once downloaded, extract the client keystore using standard archive tools on your computer:

- **Linux / macOS / HA Terminal**:
  ```bash
  unzip -j com.universal.remote.multi.apk res/El.p12 -d /config/ssl/
  # Or in alternative APK releases:
  # unzip -j com.universal.remote.multi.apk res/3R.p12 -d /config/ssl/
  # unzip -j com.universal.remote.multi.apk res/raw/client_mobile_android.p12 -d /config/ssl/
  ```

- **Windows**:
  1. Rename the downloaded file extension from `.apk` to `.zip` (e.g. `app.zip`).
  2. Open the `.zip` in Windows File Explorer or 7-Zip.
  3. Navigate to the `res/` folder and copy `El.p12` (or `3R.p12`).
  4. Paste `El.p12` into your Home Assistant `/config/ssl/` directory via Samba/SMB or File Editor.

---

### Step 3: Automatic Discovery & Loading in Home Assistant

1. Verify that `El.p12` (or `client_mobile_android.p12`) is placed in `/config/ssl/` (or `/ssl/` / `/config/certs/`).
   *(Optional: You may rename it to match your TV brand, e.g. `toshiba.p12`, `loewe.p12`, or `philips.p12`, to enable automatic brand hinting).*
2. The integration automatically discovers `El.p12`, decrypts it using the embedded keystore password, and generates `El_cert.pem` and `El_key.pem`.

> [!NOTE]
> **One Universal Keystore for All Brands**:
> There are no separate remote apps or certificate bundles for Toshiba, Loewe, or other VIDAA OS brands. The client certificate bundled inside (`CN=VidaaAppAndroidV01`) is accepted by all VIDAA OS televisions regardless of badging, because all hardware brokers share the same root certificate authority (`RemoteCA`).

> [!NOTE]
> **Modern Firmware (2024+ / `p20.09...`):** Newer VIDAA firmware builds enforce client certificate subject identity (`CN=VidaaAppAndroidV01`). Using older 2018 RemoteNOW certificates (`rcm_certchain_pem.cer`) on these firmware builds will result in connection rejection (**`rc: 5` - Not Authorized**). Use the modern VIDAA certificate bundle (`El.p12` / `vidaa_2024_cert.pem`) to resolve this.

> [!TIP]
> **Manual PKCS#12 Conversion (OpenSSL 3.x / Legacy Ciphers):** If automatic extraction fails (e.g. if the `.p12` was created with legacy RC2/3DES ciphers and the host environment does not enable the OpenSSL legacy provider), convert the archive manually to standard PEM files:
> ```bash
> openssl pkcs12 -legacy -in client_mobile_android.p12 -passin pass:186e990688070325a1c4b0ce275d2388 -clcerts -nokeys -out hisense.crt
> openssl pkcs12 -legacy -in client_mobile_android.p12 -passin pass:186e990688070325a1c4b0ce275d2388 -nocerts -nodes -out hisense.key
> ```


---

## 🛡️ Root CA Verification

By default, the integration connects with `CERT_NONE` certificate verification for the TV's self-signed server certificate, matching the official VIDAA mobile app behavior.

If you wish to enforce strict root CA verification against the TV's TLS broker:
1. Place the root CA certificate (`remote_ca.pem` or `RemoteCA.crt`) in your certs directory.
2. The integration will automatically load and validate the server certificate against this root authority.

---

## 🛠️ Testing SSL Connectivity via CLI

You can verify your certificates and validate the mutual TLS handshake with your TV before configuring Home Assistant using the [`test_client.py`](../test_client.py) utility.

> For setup prerequisites, one-line curl runners, and complete diagnostic commands, see the **[Standalone CLI Testing & Diagnostic Tools Guide](cli_tools.md)**.

```bash
# Test SSL handshake with auto-detected certs in /config/ssl:
python3 test_client.py test-ssl --ip <TV_IP>

# Test with explicit certificate paths:
python3 test_client.py test-ssl --ip <TV_IP> --cert /path/to/cert.pem --key /path/to/key.pem
```
