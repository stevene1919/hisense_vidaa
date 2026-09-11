# 🛠️ Custom Services & Example Automations

This guide details the custom Home Assistant action services exposed by the Hisense VIDAA TV integration along with practical automation and dashboard examples.

---

## ⚡ Custom Services

### 1. `hisense_vidaa.launch_app`
Launch an installed Smart TV application by name or direct URL.

```yaml
action: hisense_vidaa.launch_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "Netflix" # Options: Netflix, YouTube, Prime Video, Plex, Disney+, Stan, etc.
```

### 2. `hisense_vidaa.send_key`
Send fast single or repeated key commands with configurable delays.

```yaml
action: hisense_vidaa.send_key
target:
  entity_id: remote.living_room_tv_remote
data:
  key: "home" # Supports all aliases: up, down, left, right, ok, back, home, menu, volume_up, etc.
  repeat: 1
  delay: 0.2
```

---

## 📢 On-Screen Toast Notifications (`notify.send_message`)

Send on-screen alert notifications and toast banners directly onto the TV display:

```yaml
action: notify.send_message
target:
  entity_id: notify.living_room_tv
data:
  message: "Front Doorbell: Motion detected"
  title: "Security Alert"
```

---

## 🔊 Audio Output Mode Selection (`select.select_option`)

Switch the TV sound output mode programmatically between internal speakers, ARC/eARC soundbar/receiver, headphones, or Bluetooth:

```yaml
action: select.select_option
target:
  entity_id: select.living_room_tv_audio_output
data:
  option: "ARC/eARC" # Options: "TV Speaker", "ARC/eARC", "Headphone", "Bluetooth"
```

---

## 🎮 Native Remote Key Sequences (`remote.send_command`)

Home Assistant's native `remote.send_command` action can dispatch ordered key sequences with custom delays between presses:

```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_tv_remote
data:
  command:
    - home
    - right
    - right
    - ok
  delay_secs: 0.3
```

---

## 📱 Dashboard App Launcher Buttons

Create quick-launch button rows in Lovelace using standard horizontal stacks:

```yaml
type: horizontal-stack
cards:
  - type: button
    name: Netflix
    icon: mdi:netflix
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_tv
      data:
        app: Netflix
  - type: button
    name: YouTube
    icon: mdi:youtube
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_tv
      data:
        app: YouTube
  - type: button
    name: Prime Video
    icon: mdi:movie-open
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_tv
      data:
        app: Prime Video
```

---

## 🤖 Example Automations

### Turn on TV & Switch to HDMI 2 when Gaming Console Powers On
```yaml
alias: "TV: Switch to Xbox on Power"
trigger:
  - platform: state
    entity_id: binary_sensor.xbox_power
    to: "on"
action:
  - action: media_player.turn_on
    target:
      entity_id: media_player.living_room_tv
  - delay: "00:00:03"
  - action: media_player.select_source
    target:
      entity_id: media_player.living_room_tv
    data:
      source: "HDMI2"
```

### Automatically Dim Lights When Netflix or Movie App Launches
```yaml
alias: "Cinema: Dim Lights on Movie App"
trigger:
  - platform: state
    entity_id: sensor.living_room_tv_active_app
    to:
      - "Netflix"
      - "Prime Video"
      - "Disney+"
action:
  - action: light.turn_on
    target:
      area_id: living_room
    data:
      brightness_pct: 20
      transition: 3
```
