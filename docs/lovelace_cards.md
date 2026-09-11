# 📱 Lovelace Remote Cards & Dashboard Guide

This guide details the ready-to-use Home Assistant Lovelace dashboard remote configurations available in the [`examples/`](../examples/) directory.

---

## 🇦🇺 1. Australian Physical Remote (EN2G30H)

<p align="center">
  <img src="../assets/screenshots/ha_australian_remote.png" alt="Hisense Australian Remote Card" width="320" />
</p>

- **File:** [`examples/lovelace-australian-remote-card.yaml`](../examples/lovelace-australian-remote-card.yaml)
- **Requirements:** `custom:button-card` (HACS)
- **Features:**
  - Pixel-accurate recreation of the physical 12-app Australian remote control.
  - Dedicated quick-launch buttons with custom SVGs/badges for **Netflix, YouTube, Prime Video, Disney+, Stan, Kayo, Binge, Foxtel, ABC iview, SBS On Demand, 7plus, 9Now, and 10 play**.
  - Dual vertical pill rockers for Volume (`+`/`-`) and Channel (`+`/`-`).
  - Full D-pad navigation wheel with center `OK`, `Back`, and `Home`.
  - 12-key number pad (`1`–`9`, `•`, `0`, `CH.LIST`).
  - Full media transport controls (`Rewind`, `Play/Pause`, `Stop`, `Fast Forward`).

---

## 🇺🇸 2. US Edition Physical Remote (North America)

- **File:** [`examples/lovelace-us-remote-card.yaml`](../examples/lovelace-us-remote-card.yaml)
- **Requirements:** `custom:button-card` (HACS)
- **Features:**
  - Pixel-accurate recreation of the North American / US Hisense TV remote control.
  - Dedicated quick-launch buttons for **Netflix, YouTube, Prime Video, Disney+, Hulu, Peacock, Max, and Tubi**.
  - Circular power button, Google/VIDAA Voice Microphone shortcut, and Input selector.
  - Full D-pad navigation ring with center `OK` (supports long-press) and system navigation (`Back`, `Home`, `Menu`).
  - Dual volume and channel rockers with center `Mute` and **CC (Closed Captions)** buttons.
  - Full 10-key number pad with `INFO` and media playback controls.

---

## 📺 3. Classic Free-to-Air Remote (No Smart Apps)

- **File:** [`examples/lovelace-classic-remote-card.yaml`](../examples/lovelace-classic-remote-card.yaml)
- **Requirements:** `custom:button-card` (HACS)
- **Features:**
  - Traditional brushed dark remote layout designed specifically for Free-to-Air broadcast TV and clean media setups without streaming app clutter.
  - Dedicated `Power`, `Input` cycling, `Subtitle`, `Teletext`, `Guide/EPG`, `Channel List`, and `Exit` buttons.
  - Dual volume and channel rockers with center `Mute` and `Guide`.
  - Full 12-key number pad and color keys (`Red`, `Green`, `Yellow`, `Blue`) for Freeview Plus / HbbTV.

---

## 🧱 3. Standard Modular Button Card Remote

- **File:** [`examples/lovelace-button-card-remote.yaml`](../examples/lovelace-button-card-remote.yaml)
- **Requirements:** `custom:button-card` (HACS)
- **Features:**
  - Modular vertical stack layout using standard card structures that easily adapt to various dashboard themes.

---

## 📱 4. Android TV Card Profile

- **File:** [`examples/lovelace-android-tv-card.yaml`](../examples/lovelace-android-tv-card.yaml)
- **Requirements:** `custom:android-tv-card` (HACS)
- **Features:**
  - Pre-mapped key configurations and touchpad gestures for users who prefer the `android-tv-card` UI.

---

## 📺 5. Classic TV Card Profile

- **File:** [`examples/lovelace-tv-card.yaml`](../examples/lovelace-tv-card.yaml)
- **Requirements:** `custom:tv-card` (HACS)
- **Features:**
  - Compact, minimalist remote layout.
