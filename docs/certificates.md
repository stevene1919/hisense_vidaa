# 🔒 SSL Certificate Setup & Management Guide

VIDAA OS smart TVs enforce mutual TLS (mTLS) or client certificate authentication on MQTT port `36669`. To establish a secure connection, Home Assistant must present a valid client certificate and private key.

---

## 📁 Certificate Search Locations

The integration automatically searches the following paths (in order) inside your Home Assistant instance:

1. `/config/custom_components/hisense_vidaa/certs/`
2. `/config/certs/`
3. `/config/ssl/`
4. `/ssl/`

Place your certificate files or PKCS#12 bundles in any of these directories.

---

## 📋 Supported Certificate Formats & Naming

The integration natively supports both **auto-extracted PKCS#12 archives** (`.p12` / `.pfx`) and **PEM-encoded keypairs** (`.pem` / `.crt` / `.key`):

| Format / Profile | Firmware / Model Generation | Certificate / Bundle Filename | Private Key Filename |
| :--- | :--- | :--- | :--- |
| **PKCS#12 Bundle (Auto-Extracted)** | Any Modern VIDAA / RemoteNOW | `client_mobile_android.p12` or `rcamobile.p12` | *(Bundled in .p12 archive)* |
| **Modern VIDAA 2.0 (PEM)** | VIDAA U7 / U8 / OS 7.x+ (`Q0704`+) | `vidaa_2024_cert.pem` or `vidaa_client.pem` | `vidaa_2024_key.pem` or `vidaa_client.key` |
| **RemoteNOW Standard (PEM)** | VIDAA U4 / U5 / U6 (2018–2023) | `remotenow_2018_cert.pem` or `hisense.crt` | `remotenow_2018_key.pem` or `hisense.key` |
| **Generic / Custom PEM** | Standard fallback for any profile | `cert.pem` | `key.pem` |
| **Optional Root CA** | Optional TLS server verification | `remote_ca.pem` or `RemoteCA.crt` | *(Public root CA)* |

---

## 📦 PKCS#12 (.p12 / .pfx) Auto-Extraction

If you have extracted the PKCS#12 bundle from the official VIDAA Android / iOS app (`client_mobile_android.p12` or `rcamobile.p12`), you do **not** need to manually split it with OpenSSL.

The integration uses Python's `cryptography` library to automatically extract the client certificate and private key in-memory during connection setup.

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
