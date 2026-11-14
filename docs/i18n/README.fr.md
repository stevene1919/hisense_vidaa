# Intégration VIDAA Smart TV pour Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-gray?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-blue?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/hisensevidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

[![Ouvrez votre instance Home Assistant et ouvrez le dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

Une intégration native Home Assistant pour téléviseurs intelligents et projecteurs fonctionnant sous **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO et marques partenaires).

Elle se connecte **directement** au courtier MQTT interne du téléviseur (port TLS `36669`) via des certificats clients, offrant des mises à jour push locales instantanées, le contrôle multimédia, le lancement d'applications, le Wake-on-LAN et une télécommande virtuelle, sans aucun cloud ni passerelle externe.

---

## 🔰 Démarrage Rapide (Guide Débutant)

L'installation prend moins de 3 minutes en 3 étapes simples :

### 1️⃣ Installation via HACS
Cliquez sur le bouton ci-dessous (ou recherchez **VIDAA Smart TV** dans HACS → Intégrations → Télécharger) :

[![Ouvrir HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

### 2️⃣ Déposer le fichier de clé (`client_mobile_android.p12` ou `El.p12`)
Les téléviseurs VIDAA nécessitent une négociation TLS mutuelle sur le port 36669. Copiez le fichier universel **`client_mobile_android.p12`** (ou `El.p12`) dans le dossier **`/config/ssl/`** de Home Assistant.
- Téléchargez l'application gratuite **VIDAA Smart TV** (APK) dans votre navigateur, renommez `.apk` en `.zip` et extrayez `res/raw/client_mobile_android.p12` (ou `res/El.p12`).
- *Aucun appareil Android ou émulateur n'est requis !*

> [!TIP]
> **Besoin d'instructions pas à pas ?**  
> Consultez le **[Guide de démarrage rapide pour débutants](../quick_start_beginners.md)** avec captures d'écran (pour les certificats PEM et commandes OpenSSL, voir le [Guide avancé SSL](../certificates.md)).

### 3️⃣ Appairage avec le code PIN à l'écran
1. Redémarrez Home Assistant (`Paramètres` → `Système` → `Redémarrer`).
2. Allez dans **Paramètres → Appareils et services → Ajouter une intégration** et recherchez **VIDAA Smart TV**.
3. Saisissez l'adresse IP locale de votre téléviseur et cliquez sur **Soumettre**.
4. Saisissez le **code PIN à 4 chiffres** affiché sur l'écran du téléviseur pour finaliser la configuration !

---

## 📺 Marques et Modèles de Téléviseurs Compatibles

Prend officiellement en charge **tous les téléviseurs sous VIDAA OS** (appairage avec **code PIN à 4 chiffres à l'écran**) :

- 📺 **Hisense** (Séries U6, U7, U8, UX, A6, A7 — U4 à U8, années 2018 à 2026+)
- 📺 **Loewe** (Séries We. SEE, stellar sous VIDAA OS)
- 📺 **Toshiba** (Modèles VIDAA C350, M550, Z670)
- 📺 **Philips / TPV** (Séries OLED, The One, PUS équipées de VIDAA OS)
- 📺 **Metz, Schneider, Telefunken, Beko, Sharp, JVC** et autres marques sous licence
- 📽️ **TOPTRO** (Projecteurs intelligents portables sous VIDAA OS)

---

## ✨ Fonctionnalités Principales

- **Contrôle 100 % Local sur le LAN (`iot_class: local_push`)** : Zéro dépendance au cloud, fonctionne dans des VLANs IoT isolés.
- **Lecteur Multimédia (`media_player`)** : Allumage/extinction, volume, sélection des sources, changement de chaîne, lancement d'applications et touches contextuelles (zapping en direct, navigation de pistes dans les applications).
- **Réglages Image & Son (`select` & `number`)** : Modes d'image (`Standard`, `Cinéma`, `Dynamique`, `Sport`, `Filmmaker`), luminosité, contraste et rétroéclairage ; modes audio et sortie sonore.
- **Télécommande Dédiée (`remote`)** : Flèches directionnelles, pavé numérique, menu, touches de couleur et répétition de touches configurable.
- **Déclencheurs d'Allumage (`device_trigger`)** : Prise en charge native du déclencheur `vidaa.turn_on` pour activer des prises connectées ou Wake-on-LAN.

---

## 📚 Bibliothèque de Documentation

| Guide | Description |
| :--- | :--- |
| 🔰 **[Guide de démarrage pour débutants](../quick_start_beginners.md)** | Instructions pas à pas avec extraction facile de `El.p12`. |
| ⚙️ **[Configuration et Options](../parameters.md)** | Référence complète de tous les paramètres et menus de configuration. |
| ⚡ **[Paramètres d'Alimentation et de Veille](../power_and_standby_settings.md)** | Comportement de veille, démarrage rapide et préservation des jetons d'appairage. |
| 📱 **[Tableaux de Bord et Cartes Lovelace](../lovelace_cards.md)** | Cartes de télécommande, cartes à boutons et modèles d'interface. |
| 🛠️ **[Services et Automatisations](../services_and_automations.md)** | Exemples YAML pour soirées cinéma, sélection d'entrées et séquences de touches. |
| 🔒 **[Certificats SSL Avancés](../certificates.md)** | Emplacements des fichiers, certificats PEM personnalisés et commandes OpenSSL. |
| 🧪 **[Outils de Test et Diagnostic CLI](../cli_tools.md)** | Utilitaires autonomes (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Dépannage et Résolution de Problèmes](../troubleshooting.md)** | Diagnostic et solutions pour les erreurs de connexion et d'appairage. |
