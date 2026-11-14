# VIDAA Smart TV Integration für Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-blue?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-gray?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/vidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

[![Öffnen Sie Ihre Home Assistant-Instanz und öffnen Sie das Repository im HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

Eine native Home Assistant-Integration für Smart-TVs und Projektoren mit **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO und Partner-Marken).

Verbindet sich **direkt** mit dem internen MQTT-Broker des Fernsehers (TLS-Port `36669`) mittels Client-Zertifikaten. Bietet sofortige lokale Push-Aktualisierungen, Mediensteuerung, App-Start, Wake-on-LAN und virtuelle Fernbedienung – ganz ohne Cloud oder externe Bridges.

---

## 🔰 Schnellstart (Anleitung für Einsteiger)

Die Einrichtung dauert weniger als 3 Minuten in 3 einfachen Schritten:

### 1️⃣ Installation über HACS
Klicken Sie auf den Button unten (oder suchen Sie in HACS nach **VIDAA Smart TV** → Integrationen → Herunterladen):

[![HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

### 2️⃣ Schlüsseldatei (`client_mobile_android.p12` oder `El.p12`) hinterlegen
VIDAA-Fernseher erfordern gegenseitiges TLS auf Port 36669. Kopieren Sie die universelle Datei **`client_mobile_android.p12`** (oder `El.p12`) in Ihr Home Assistant-Verzeichnis **`/config/ssl/`**.
- Laden Sie die kostenlose öffentliche **VIDAA Smart TV**-App (APK) im Browser herunter, benennen Sie `.apk` in `.zip` um und entpacken Sie `res/raw/client_mobile_android.p12` (oder `res/El.p12`).
- *Kein Android-Gerät oder Emulator erforderlich!*

> [!TIP]
> **Schritt-für-Schritt-Anleitung gesucht?**  
> Siehe **[Schnellstart-Leitfaden für Einsteiger](../quick_start_beginners.md)** mit Screenshots (für fortgeschrittene OpenSSL-Befehle siehe [SSL-Zertifikate](../certificates.md)).

### 3️⃣ Kopplung mit Bildschirm-PIN
1. Starten Sie Home Assistant neu (`Einstellungen` → `System` → `Neu starten`).
2. Gehen Sie zu **Einstellungen → Geräte & Dienste → Integration hinzufügen** und suchen Sie nach **VIDAA Smart TV**.
3. Geben Sie die lokale IP-Adresse Ihres Fernsehers ein und klicken Sie auf **Absenden**.
4. Geben Sie den auf dem Fernsehbildschirm angezeigten **4-stelligen PIN-Code** ein. Fertig!

---

## 📺 Unterstützte TV-Marken & Modelle

Unterstützt offiziell **alle Smart-TVs mit VIDAA OS** (Kopplung per **4-stelligem Bildschirm-PIN**):

- 📺 **Hisense** (U6, U7, U8, UX, A6, A7 Serien — U4 bis U8, Baujahre 2018 bis 2026+)
- 📺 **Loewe** (We. SEE, stellar VIDAA OS Serien)
- 📺 **Toshiba** (C350, M550, Z670 VIDAA-Modelle)
- 📺 **Philips / TPV** (OLED, The One, PUS Serien mit VIDAA OS)
- 📺 **Metz, Schneider, Telefunken, Beko, Sharp, JVC** und weitere Lizenzpartner
- 📽️ **TOPTRO** (Tragbare Smart-Beamer mit VIDAA OS)

---

## ✨ Wichtigste Funktionen

- **100 % Lokale LAN-Steuerung (`iot_class: local_push`)**: Vollständig lokal, keine Cloud-Abhängigkeit, funktioniert in isolierten IoT-VLANs.
- **Mediaplayer**: Ein-/Ausschalten, Lautstärkeregelung, Eingangsquellen, Senderumschaltung, App-Start und kontextsensitive Tasten (Senderwechsel im Live-TV, Titelsprung in Apps).
- **Bild & Tonjustierung (`select` & `number`)**: Bildmodi (`Standard`, `Kino`, `Dynamisch`, `Sport`, `Filmmaker`) und Helligkeit/Kontrast/Hintergrundbeleuchtung einstellen; Tonmodi und Tonausgabe umschalten.
- **Dedizierte Fernbedienung (`remote`)**: Steuerkreuz-Navigation, Zifferntasten, Menü, Farbtasten und konfigurierbare Tastenwiederholung.
- **Einschalt-Automationen (`device_trigger`)**: Native Unterstützung für `vidaa.turn_on`-Trigger zum Schalten von Zwischensteckern oder Wake-on-LAN.

---

## 📚 Dokumentations-Bibliothek

| Leitfaden | Beschreibung |
| :--- | :--- |
| 🔰 **[Einsteiger-Schnellstart](../quick_start_beginners.md)** | Schritt-für-Schritt-Anleitung mit `El.p12`-Extraktion. |
| ⚙️ **[Konfiguration & Optionen](../parameters.md)** | Vollständige Parameter-Referenz für alle Einstellungsmenüs. |
| ⚡ **[Strom- & Standby-Einstellungen](../power_and_standby_settings.md)** | Standby-Verhalten, Schnellstart und Schutz vor Token-Verlust. |
| 📱 **[Lovelace Dashboards & Karten](../lovelace_cards.md)** | Fernbedienungs-Karten, Button-Cards und Dashboard-Vorlagen. |
| 🛠️ **[Dienste & Automationen](../services_and_automations.md)** | Fertige YAML-Vorlagen für Kinoabende, Eingangswahl und Tastenfolgen. |
| 🔒 **[Erweiterte SSL-Zertifikate](../certificates.md)** | Dateipfade, eigene PEM-Zertifikate und OpenSSL-Befehle. |
| 🧪 **[CLI-Test & Diagnose-Tools](../cli_tools.md)** | Eigenständige Werkzeuge (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Fehlerbehebung & Problembehebung](../troubleshooting.md)** | Diagnose und Lösungen für Verbindungs- und Kopplungsfehler. |
