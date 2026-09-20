# 🔒 SSL Certificate Setup & Management Guide

VIDAA OS smart TVs enforce mutual TLS (mTLS) or client certificate authentication on MQTT port `36669`. To establish a secure connection, Home Assistant must present a valid client certificate and private key.

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
| **PKCS#12 Bundle (Auto-Extracted)** | Any Modern VIDAA / RemoteNOW | `client_mobile_android.p12`, `El.p12`, or `rcamobile.p12` | *(Bundled in .p12 archive)* |
| **Modern VIDAA 2.0 (PEM)** | VIDAA U6+ / U7 (2024+) | `vidaa_client_v01.pem`, `vidaa_client_v02.pem`, `vidaa_2024_cert.pem`, or `vidaa_client.pem` | `vidaa_client_v01.key`, `vidaa_client_v02.key`, `vidaa_2024_key.pem`, or `vidaa_client.key` |
| **RemoteNOW Standard (PEM)** | VIDAA U4 / U5 / U6 (2018–2023) | `vidaa_client_v01.pem`, `remotenow_2018_cert.pem`, or `hisense.crt` | `vidaa_client_v01.key`, `remotenow_2018_key.pem`, or `hisense.key` |
| **Generic / Custom PEM** | Standard fallback for any profile | `cert.pem` | `key.pem` |
| **Optional Root CA** | Optional TLS server verification | `remote_ca.pem` or `RemoteCA.crt` | *(Public root CA)* |

---

## 📦 PKCS#12 (.p12 / .pfx) Auto-Extraction

If you have extracted the PKCS#12 bundle from the official VIDAA Android / iOS app (`client_mobile_android.p12`, `El.p12`, or `rcamobile.p12`), you do **not** need to manually split it with OpenSSL.

### Extracting `El.p12` from the VIDAA Smart TV App:
In the official **VIDAA Smart TV** Android APK (`com.universal.remote.multi`), the client keystore is bundled inside the APK zip at `res/El.p12`:
1. Extract the file directly from the APK archive:
   ```bash
   unzip -j app.apk res/El.p12
   ```
2. Place `El.p12` in `/config/ssl/` (or `/ssl/` / `/config/certs/`).
3. The integration automatically discovers `El.p12`, decrypts it using the embedded keystore password, and writes `El_cert.pem` and `El_key.pem`.

> [!NOTE]
> **Modern Firmware (2024+ / `p20.09...`):** Newer VIDAA firmware builds enforce client certificate subject identity (`CN=VidaaAppAndroidV01`). Using older 2018 RemoteNOW certificates (`rcm_certchain_pem.cer`) on these firmware builds will result in connection rejection (**`rc: 5` - Not Authorized**). Use the modern VIDAA certificate bundle (`El.p12` / `vidaa_2024_cert.pem`) to resolve this.

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
