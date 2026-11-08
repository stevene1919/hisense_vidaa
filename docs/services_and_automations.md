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
  entity_id: media_player.living_room_hisense_vidaa_tv
data:
  app: "Netflix" # Options: Netflix, YouTube, Prime Video, Plex, Disney+, Stan, etc.
```

To launch YouTube with a video URL (equivalent to the CLI's `--app-id`, app name,
and `--url` arguments):

```yaml
action: hisense_vidaa.launch_app
target:
  entity_id: media_player.living_room_hisense_vidaa_tv
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
  entity_id: remote.living_room_hisense_vidaa_tv_remote
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
  entity_id: media_player.living_room_hisense_vidaa_tv
data:
  text: "The Matrix"
```

> [!TIP]
> You can also send text or clear search fields using the standard `remote.send_command` action via the `text:` / `type:` prefix:
> ```yaml
> action: remote.send_command
> target:
>   entity_id: remote.living_room_hisense_vidaa_tv_remote
> data:
>   command:
>     - "text:The Matrix" # or "type:The Matrix", "text:replace:New Query", "clear_text"
> ```

### 4. `hisense_vidaa.set_picture_setting`
Execute custom picture setting adjustments via raw menu ID and parameter value.

```yaml
action: hisense_vidaa.set_picture_setting
target:
  entity_id: media_player.living_room_hisense_vidaa_tv
data:
  menu_id: 91
  menu_value: "Cinema Night"
```

### 5. `hisense_vidaa.set_sound_setting`
Execute custom sound equalizer adjustments via raw menu ID and parameter value.

```yaml
action: hisense_vidaa.set_sound_setting
target:
  entity_id: media_player.living_room_hisense_vidaa_tv
data:
  menu_id: 1
  menu_value: "Theatre"
```

### 6. `hisense_vidaa.send_key_sequence`
Send a sequence of remote key commands with configurable delays between keys. Supports passing a list of key names or a comma-separated string.

```yaml
action: hisense_vidaa.send_key_sequence
target:
  entity_id: media_player.living_room_hisense_vidaa_tv
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
  entity_id: media_player.living_room_hisense_vidaa_tv
data:
  sequence: "home, right, ok"
  delay: 0.3
```

### 7. `hisense_vidaa.change_channel`
Directly tune to a numeric TV channel by sequentially dispatching number keys with an optional confirmation (`KEY_OK`) key.

```yaml
action: hisense_vidaa.change_channel
target:
  entity_id: media_player.living_room_hisense_vidaa_tv
data:
  channel: 701
  confirm: true
  delay: 0.2
```

---

## 🎯 Service Target Resolution (Single-TV vs Multi-TV)

All `hisense_vidaa.*` action services support targeting via standard Home Assistant selectors: `target.entity_id`, `target.device_id`, `target.area_id`, `target.floor_id`, or `target.label_id`.

* **Single TV Setup**: If you only have one Hisense VIDAA TV configured in Home Assistant, omitting the `target` parameter will automatically target that single TV for convenience.
* **Multiple TVs Setup**: When 2 or more Hisense VIDAA TVs are configured:
  * You **must** provide a target selector (`target.entity_id`, `target.device_id`, etc.) identifying which TV should receive the command. Omitting the target will raise a `ServiceValidationError` (`ambiguous_target`) to prevent inadvertent commands being sent to the wrong TV.
  * To explicitly broadcast a service command to all configured TVs at once, pass `entity_id: "all"` (e.g. `target: { entity_id: "all" }`).

---

## 🎛️ Picture & Sound Controls (`number` and `select` entities)

### Adjust Backlight, Brightness, and Contrast Sliders
Control display parameters in automations using standard `number.set_value`:

```yaml
action: number.set_value
target:
  entity_id: number.living_room_hisense_vidaa_tv_backlight
data:
  value: 45 # Range: 0 - 100
```

### Switch Picture Mode Dynamically
Switch Picture Mode based on ambient light or time of day:

```yaml
action: select.select_option
target:
  entity_id: select.living_room_hisense_vidaa_tv_picture_mode
data:
  option: "Cinema Night" # Options: Standard, Cinema Day, Cinema Night, Dynamic, Sports, Game, Filmmaker Mode
```

### Switch Sound Equalizer Mode
Change audio EQ presets based on active media or content:

```yaml
action: select.select_option
target:
  entity_id: select.living_room_hisense_vidaa_tv_sound_mode
data:
  option: "Theatre" # Options: Standard, Theatre, Music, Speech, Late Night, Sports
```

---

## 🔊 Audio Output Mode Selection (`select.select_option`)

Switch the TV sound output mode programmatically between internal speakers, ARC/eARC soundbar/receiver, headphones, or Bluetooth:

```yaml
action: select.select_option
target:
  entity_id: select.living_room_hisense_vidaa_tv_audio_output
data:
  option: "ARC / eARC" # Options: "TV Speakers", "ARC / eARC", "Headphone / Bluetooth"
```

---

## 🎮 Native Remote Key Sequences (`remote.send_command`)

Home Assistant's native `remote.send_command` action can dispatch ordered key sequences with custom delays between presses:

```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_hisense_vidaa_tv_remote
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
        entity_id: media_player.living_room_hisense_vidaa_tv
      data:
        app: Netflix
  - type: button
    name: YouTube
    icon: mdi:youtube
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_hisense_vidaa_tv
      data:
        app: YouTube
  - type: button
    name: Prime Video
    icon: mdi:movie-open
    tap_action:
      action: perform-action
      perform_action: hisense_vidaa.launch_app
      target:
        entity_id: media_player.living_room_hisense_vidaa_tv
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
When executing a "Good Night" voice command or bedtime automation, if the TV is still playing in the living room, turn off screen backlight via `switch.living_room_hisense_vidaa_tv_audio_only` or automatically power off the TV after 30 minutes, switching sound output to `Late Night` EQ mode.

---

## 🤖 Copy-Paste YAML Automation Recipes

### Recipe 1: Cinema Mode & Ambient Lighting Sync
```yaml
alias: "Cinema: Dim Lights & Set Movie Picture Mode"
description: "Automatically dim lights and switch to Cinema Night picture mode when movie apps open after sunset."
trigger:
  - platform: state
    entity_id: media_player.living_room_hisense_vidaa_tv
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
      entity_id: select.living_room_hisense_vidaa_tv_picture_mode
    data:
      option: "Cinema Night"
  - action: select.select_option
    target:
      entity_id: select.living_room_hisense_vidaa_tv_sound_mode
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
    entity_id: media_player.living_room_hisense_vidaa_tv
    attribute: source
    to: "HDMI 1"
action:
  - action: select.select_option
    target:
      entity_id: select.living_room_hisense_vidaa_tv_picture_mode
    data:
      option: "Game"
  - action: number.set_value
    target:
      entity_id: number.living_room_hisense_vidaa_tv_backlight
    data:
      value: 80
```

### Recipe 3: Late Night Volume & EQ Guard
```yaml
alias: "Audio: Late Night Equalizer Guard"
description: "Switch sound mode to Late Night after 10 PM to compress dynamic volume range."
trigger:
  - platform: time
    at: "22:00:00"
condition:
  - condition: state
    entity_id: media_player.living_room_hisense_vidaa_tv
    state: "on"
action:
  - action: select.select_option
    target:
      entity_id: select.living_room_hisense_vidaa_tv_sound_mode
    data:
      option: "Late Night"
```

### Recipe 5: Custom Turn-On Trigger (Smart Plug / Relay / IR Blaster)
```yaml
alias: "Power: Custom TV Turn-On Action"
description: "Intercepts media_player.turn_on to switch on an external smart plug before sending network wake."
trigger:
  - platform: device
    domain: hisense_vidaa
    device_id: <DEVICE_ID>
    type: hisense_vidaa.turn_on
action:
  - action: switch.turn_on
    target:
      entity_id: switch.living_room_tv_smart_plug
```

### Recipe 6: Direct Live TV Channel Tuning by Name or Number
```yaml
alias: "Media: Tune directly to ABC TV"
description: "Switches TV to Live TV tuner and inputs the channel digits matching 'ABC TV'."
action:
  - action: media_player.play_media
    target:
      entity_id: media_player.living_room_hisense_vidaa_tv
    data:
      media_content_type: channel
      media_content_id: "ABC TV"
```
