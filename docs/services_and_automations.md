# 🛠️ Custom Services & Example Automations

This guide details the custom Home Assistant action services exposed by the Hisense VIDAA TV integration along with practical automation and dashboard examples.

---

## ⚡ Custom Services

### 1. `hisense_vidaa.launch_app`
Launch an installed Smart TV application by name or direct URL. Optional `app_id`,
`app_name`, and `url` fields override the values found in the TV's app list. This
is useful when a launch needs a specific app ID and deep link. You can also omit
`app` and provide only `app_id` to launch an app directly by ID.

```yaml
action: hisense_vidaa.launch_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "Netflix" # Options: Netflix, YouTube, Prime Video, Plex, Disney+, Stan, etc.
```

To launch YouTube with a video URL (equivalent to the CLI's `--app-id`, app name,
and `--url` arguments):

```yaml
action: hisense_vidaa.launch_app
target:
  entity_id: media_player.living_room_tv
data:
  app: "YouTube"
  app_id: "3"
  app_name: "YouTube"
  url: "https://www.youtube.com/watch?v=REPPgPcw4hk"
```

The integration publishes the launch payload over its existing authenticated
TLS/MQTT connection to the TV. Use this action rather than `mqtt.publish`:
Home Assistant's generic MQTT broker connection is separate from the TV's
certificate-authenticated MQTT session.

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

### 3. `hisense_vidaa.send_text_input`
Inject virtual keyboard text directly into on-screen search bars and text inputs (e.g. searching YouTube, Netflix, or browser).

```yaml
action: hisense_vidaa.send_text_input
target:
  entity_id: media_player.living_room_tv
data:
  text: "The Matrix"
```

### 4. `hisense_vidaa.set_picture_setting`
Execute custom picture setting adjustments via raw menu ID and parameter value.

```yaml
action: hisense_vidaa.set_picture_setting
target:
  entity_id: media_player.living_room_tv
data:
  menu_id: 91
  menu_value: "Cinema Night"
```

### 5. `hisense_vidaa.set_sound_setting`
Execute custom sound equalizer adjustments via raw menu ID and parameter value.

```yaml
action: hisense_vidaa.set_sound_setting
target:
  entity_id: media_player.living_room_tv
data:
  menu_id: 1
  menu_value: "Theatre"
```

### 6. `hisense_vidaa.send_key_sequence`
Send a sequence of remote key commands with configurable delays between keys. Supports passing a list of key names or a comma-separated string.

```yaml
action: hisense_vidaa.send_key_sequence
target:
  entity_id: media_player.living_room_tv
data:
  sequence:
    - home
    - right
    - ok
  delay: 0.3
```

Or using comma-separated notation:

```yaml
action: hisense_vidaa.send_key_sequence
target:
  entity_id: media_player.living_room_tv
data:
  sequence: "home, right, ok"
  delay: 0.3
```

### 7. `hisense_vidaa.change_channel`
Directly tune to a numeric TV channel by sequentially dispatching number keys with an optional confirmation (`KEY_OK`) key.

```yaml
action: hisense_vidaa.change_channel
target:
  entity_id: media_player.living_room_tv
data:
  channel: 701
  confirm: true
  delay: 0.2
```

---

## 🎛️ Picture & Sound Controls (`number` and `select` entities)

### Adjust Backlight, Brightness, and Contrast Sliders
Control display parameters in automations using standard `number.set_value`:

```yaml
action: number.set_value
target:
  entity_id: number.living_room_tv_backlight
data:
  value: 45 # Range: 0 - 100
```

### Switch Picture Mode Dynamically
Switch Picture Mode based on ambient light or time of day:

```yaml
action: select.select_option
target:
  entity_id: select.living_room_tv_picture_mode
data:
  option: "Cinema Night" # Options: Standard, Cinema Day, Cinema Night, Dynamic, Sports, Game, Filmmaker Mode
```

### Switch Sound Equalizer Mode
Change audio EQ presets based on active media or content:

```yaml
action: select.select_option
target:
  entity_id: select.living_room_tv_sound_mode
data:
  option: "Theatre" # Options: Standard, Theatre, Music, Speech, Late Night, Sports
```

---

## 📢 On-Screen Toast Notifications (`notify.send_message`)

Send on-screen alert notifications and toast banners directly onto the TV display:

```yaml
action: notify.send_message
target:
  entity_id: notify.living_room_tv_notifications
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
  option: "ARC / eARC" # Options: "TV Speakers", "ARC / eARC", "Headphone / Bluetooth"
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
