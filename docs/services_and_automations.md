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

## 🌟 Real-World Use Cases & Automation Patterns

### Use Case 1: Ambient Cinema Atmosphere
When launching streaming video apps (Netflix, Prime Video, Disney+, Plex) in the evening, automatically dim the living room light scene to 15%, adjust picture mode to `Cinema Night`, and set sound EQ mode to `Theatre`.

### Use Case 2: Game Console Low-Latency Picture Sync
When switching active source to PlayStation 5 or Xbox Series X on HDMI 1 or HDMI 2, automatically trigger low-latency `Game` picture mode and turn down backlight for night sessions.

### Use Case 3: Bedtime All-Off & Late Night Audio Guard
When executing a "Good Night" voice command or bedtime automation, if the TV is still playing in the master bedroom, turn off screen backlight via `switch.audio_only` or automatically power off the TV after 30 minutes, switching sound output to `Late Night` EQ mode.

### Use Case 4: Smart Doorbell On-Screen Notifications
When someone rings the smart video doorbell, display a real-time high-priority text toast banner on the television screen notifying occupants without interrupting current playback.

---

## 🤖 Copy-Paste YAML Automation Recipes

### Recipe 1: Cinema Mode & Ambient Lighting Sync
```yaml
alias: "Cinema: Dim Lights & Set Movie Picture Mode"
description: "Automatically dim lights and switch to Cinema Night picture mode when movie apps open after sunset."
trigger:
  - platform: state
    entity_id: media_player.living_room_tv
    attribute: app_name
    to:
      - "Netflix"
      - "Prime Video"
      - "Disney+"
      - "Plex"
condition:
  - condition: sun
    after: sunset
action:
  - action: select.select_option
    target:
      entity_id: select.living_room_tv_picture_mode
    data:
      option: "Cinema Night"
  - action: select.select_option
    target:
      entity_id: select.living_room_tv_sound_mode
    data:
      option: "Theatre"
  - action: light.turn_on
    target:
      area_id: living_room
    data:
      brightness_pct: 15
      transition: 3
```

### Recipe 2: PlayStation / Xbox Game Mode Sync
```yaml
alias: "Gaming: Activate Game Mode on PS5 Input"
description: "Switch picture mode to Game and adjust backlight when PS5 is selected."
trigger:
  - platform: state
    entity_id: media_player.living_room_tv
    attribute: source
    to: "HDMI 1"
action:
  - action: select.select_option
    target:
      entity_id: select.living_room_tv_picture_mode
    data:
      option: "Game"
  - action: number.set_value
    target:
      entity_id: number.living_room_tv_backlight
    data:
      value: 80
```

### Recipe 3: Smart Doorbell Toast Notification
```yaml
alias: "Notifications: Show Doorbell Banner on TV"
description: "Pop up an on-screen toast message when the front doorbell rings."
trigger:
  - platform: state
    entity_id: binary_sensor.front_doorbell_visitor
    to: "on"
action:
  - action: notify.send_message
    target:
      entity_id: notify.living_room_tv_notifications
    data:
      title: "🔔 Doorbell Ringing"
      message: "Someone is at the Front Door!"
```

### Recipe 4: Late Night Volume & EQ Guard
```yaml
alias: "Audio: Late Night Equalizer Guard"
description: "Switch sound mode to Late Night after 10 PM to compress dynamic volume range."
trigger:
  - platform: time
    at: "22:00:00"
condition:
  - condition: state
    entity_id: media_player.living_room_tv
    state: "on"
action:
  - action: select.select_option
    target:
      entity_id: select.living_room_tv_sound_mode
    data:
      option: "Late Night"
```
