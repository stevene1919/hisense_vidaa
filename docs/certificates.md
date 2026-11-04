# 🔒 SSL Certificate Setup & Management Guide

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

## 📦 PKCS#12 (.p12 / .pfx) Auto-Extraction

If you have extracted the PKCS#12 bundle from the official VIDAA Android / iOS app (`client_mobile_android.p12`, `El.p12`, or `rcamobile.p12`), you do **not** need to manually split it with OpenSSL.

### How to Extract `El.p12` from the VIDAA APK Archive (Any Computer):
In the official **VIDAA Smart TV** Android app distribution package (`com.universal.remote.multi` APK), the client keystore is bundled inside the APK zip archive (commonly located at `res/El.p12`, `res/3R.p12`, or `res/raw/client_mobile_android.p12`).

You can extract this file on any computer (no phone needed):

- **Linux / macOS / HA Terminal**:
  ```bash
  unzip -j app.apk res/El.p12 -d /config/ssl/
  # Or in some APK releases:
  # unzip -j app.apk res/3R.p12 -d /config/ssl/
  # unzip -j app.apk res/raw/client_mobile_android.p12 -d /config/ssl/
  ```
- **Windows**:
  Rename `app.apk` to `app.zip`, open it in Windows File Explorer or 7-Zip, locate `res/El.p12`, and copy it to your Home Assistant `/config/ssl/` share.
2. Place `El.p12` in `/config/ssl/` (or `/ssl/` / `/config/certs/`).
   *(Optional: You may rename it to your TV brand, e.g. `toshiba.p12` or `loewe.p12`, for automatic brand detection).*
3. The integration automatically discovers `El.p12`, decrypts it using the embedded keystore password, and writes `El_cert.pem` and `El_key.pem`.

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

You can verify your certificates before setting up Home Assistant using [`test_client.py`](cli_tools.md):

```bash
# Test SSL handshake with auto-detected certs:
python3 test_client.py test-ssl --ip <TV_IP>

# Test with explicit certificate paths:
python3 test_client.py test-ssl --ip <TV_IP> --cert /path/to/cert.pem --key /path/to/key.pem
```
