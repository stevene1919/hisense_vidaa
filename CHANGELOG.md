# Changelog

All notable changes to the Hisense VIDAA TV integration will be documented in this file.

## [2.8.1] - 2026-09-13

### Added
- **SESSION STATUS SENSOR (`sensor.{tv}_session_status`)**: Replaced the misleading "Token Expiry" timestamp countdown with an intuitive diagnostic `Session Status` sensor tracking live authentication state (`Active`, `Standby`, `Reauth Required`) with rich attributes (`paired_at`, `auth_profile`, `encryption`, `client_id`).

### Fixed
- **SELECTIVE PLATFORM UNLOAD ON RECONFIGURATION**: `async_unload_entry` now unloads only the dynamically enabled platforms recorded during setup instead of static `PLATFORMS`. This prevents `ValueError: Config entry was never loaded!` crashes when unloading entries where optional platforms (such as `notify` or `remote`) are disabled or not supported, resolving `ConfigEntryState.FAILED_UNLOAD` and preserving the ability to reload and reconfigure options from the UI.
- **MATERIAL DESIGN ICON CORRECTION**: Updated Sync Clock button icon to standard `mdi:clock-outline` in `button.py` and `icons.json` to fix broken icon rendering.

### Removed
- **REDUNDANT REFRESH TOKEN BUTTON**: Removed `button.{tv}_refresh_access_token` since VIDAA firmware does not require or execute periodic manual token rotations during active pairing sessions.

## [2.8.0] - 2026-09-11

### Added
- **ON-SCREEN TOAST NOTIFICATIONS (`notify` platform)**: Added `notify.{tv}` platform entity implementing `NotifyEntity` and `async_send_message` to broadcast on-screen popup notification banners (doorbell alerts, timers, security warnings) via VIDAA MQTT topics (`actions/showmessage` / `actions/toast`).
- **AUDIO OUTPUT MODE SELECTOR (`select` platform)**: Added `select.{tv}_audio_output` entity allowing users to view and select the TV's audio output routing (`TV Speakers`, `ARC / eARC`, `Headphone / Bluetooth`) from automations and dashboards.
- **CATEGORIZED & TABBED OPTIONS FLOW**: Completely redesigned the Options Flow (**Configure**) into intuitive, categorized submenus:
  - ⚡ **General & Power Options**: Dedicated remote entity toggle, Wake-on-LAN, Secondary MAC, and SSL encryption.
  - 📺 **Sources & Media Controls**: Smart TV app listing, media transport controls, and HDMI-CEC source labeling.
  - 🎮 **Remote Key Timings & Repeats**: Configurable keypress delay (seconds slider) and repeat count box.
  - 🔒 **SSL Certificates & Security**: Custom certificate and private key paths.
- **DYNAMIC HDMI-CEC SOURCE RENAMING**: Media player source list automatically shows connected HDMI-CEC device names (e.g. `"HDMI 2 (PlayStation 5)"`) with smart input stripping on selection.
- **DUAL-MAC WAKE-ON-LAN FALLBACK**: WoL magic packet broadcasting now sends packets to both primary and secondary MAC addresses (Ethernet & Wi-Fi) across ports `9` and `7`.
- **APPLE HOMEKIT TELEVISION ACCESSORY SUPPORT**: Explicitly configured `_attr_device_class = MediaPlayerDeviceClass.TV` for seamless bridging to Apple Home and the native iOS Control Center TV Remote widget.
- **US EDITION LOVELACE REMOTE CARD**: Added pixel-accurate North American remote configuration ([`examples/lovelace-us-remote-card.yaml`](examples/lovelace-us-remote-card.yaml)) featuring Netflix, YouTube, Prime Video, Disney+, Hulu, Peacock, Max, and Tubi quick-launch buttons.

### Fixed
- **REMOTE & MEDIA PLAYER POWER STATE SYNCHRONIZATION**: Remote entity now initializes state from active client connection and registers `connected_callback`, eliminating out-of-sync `off` state when Home Assistant starts while the TV is already running.
- **IDEMPOTENT `turn_on` POWER PROTECTION**: Calling `turn_on` on the remote or media player when the TV is already connected and active is now safely idempotent and will NOT send `KEY_POWER`, preventing accidental TV shutdown caused by power toggle behavior.
- **FAKE SLEEP RECOVERY**: Retained dedicated `KEY_POWER` display wake dispatch when turning on from low-power standby (`statetype == "fake_sleep_0"`).

## [2.7.5] - 2026-09-11

### Added
- **LOVELACE REMOTE CARDS & PHYSICAL REMOTE CONFIGURATIONS**: Added 5 ready-to-use Lovelace remote card example configurations in [`examples/`](examples/):
  - `lovelace-australian-remote-card.yaml`: Pixel-accurate 12-app EN2G30H Australian physical remote layout with streaming quick-launch buttons.
  - `lovelace-classic-remote-card.yaml`: Traditional Free-to-Air remote layout without streaming app shortcuts, focusing on D-pad navigation, volume/channel rockers, full 12-key numpad, and media transport controls.
  - `lovelace-button-card-remote.yaml`: Modular vertical stack remote layout with standard button cards.
  - `lovelace-android-tv-card.yaml`: Custom integration profile for `android-tv-card`.
  - `lovelace-tv-card.yaml`: Clean layout for `tv-card`.
- **WORLDWIDE & REGIONAL SMART APP SHORTCUTS**: Added comprehensive alias mappings and normalized regex/fuzzy matching in `_launch_app_by_name` across Australia/NZ (ABC iview, SBS On Demand, 7plus, 9Now, 10 play, Stan, Kayo, Binge, Foxtel, Optus Sport, TVNZ+, ThreeNow, Neon), UK/Europe (BBC iPlayer, ITVX, Channel 4, My5, NOW, Discovery+, RTL+, Joyn, RaiPlay, RTVE Play), North America (Peacock, Hulu, Sling TV, FuboTV, Philo, Roku, Vudu, Crackle, Freevee, CBC Gem, Crave), and Global services (Disney+, Apple TV, Max/HBO, Paramount+, Spotify, Tidal, Plex, Crunchyroll, DAZN, Tubi, Pluto TV, Rakuten, MUBI, UFC, NBA, UEFA.tv, F1 TV).
- **DUAL-COMPATIBILITY INPUT CYCLING & LIVE TV TUNER FIX**: Resolved input cycling stall on broadcast TV (`livetv`) by passing both `sourceid` and string `sourcename` (dual-publishing for older numeric and modern string firmware compatibility). Added fallback `KEY_LIVETV` trigger when switching to Live TV mode.
- **DIRECT `source:<name>` & `app:<name>` TARGETING**: Added direct prefix targeting in `send_command` (`source:HDMI2`, `app:Stan`) to allow one-shot switching from remote keypads and scripts.
- **EXTENDED KEY ALIASES**: Added comprehensive key aliases across all international and model variants including `text` / `teletext` / `txt`, `guide` / `epg`, `chlist` / `channel_list`, `key_input`, `key_source`, `key_input_menu`, and color keys.

## [2.7.0] - 2026-09-11

### Added
- **MULTI-FORMAT CERTIFICATE & PKCS#12 BUNDLE SUPPORT**: Native support for direct PKCS#12 keystore archives (`.p12`, `.pfx` such as `client_mobile_android.p12` or `rcamobile.p12`) with automatic certificate and private key extraction using standard cryptography, eliminating the need to execute manual `openssl` CLI extraction commands.
- **OPTIONAL SERVER ROOT CA VERIFICATION**: Added support for custom root CA files (`remote_ca.pem`, `RemoteCA.crt`) with `verify_ssl` opt-in while keeping default `CERT_NONE` matching official VIDAA mobile app behavior.
- **AUDIO OUTPUT TYPE SENSOR (`sensor.{tv}_audio_output`)**: Dedicated sensor tracking live audio output mode (`TV Speakers`, `ARC / eARC`, `Muted`) parsed in real-time from TV volume state broadcasts (`volume_type`).
- **HDMI-CEC DEVICE & LIVE TV CHANNEL METADATA**: Media player and active source sensor now track connected HDMI-CEC device name (`connected_device` attribute, e.g. Apple TV, PlayStation 5, Chromecast) and Live TV channel metadata (`channel_name`, `channel_number`).
- **`KEY_AUDIO` SCREEN-OFF HARDWARE COMMAND**: Added key alias mappings (`audio_only`, `screen_off`) to `KEY_AUDIO` allowing users to turn off the TV display panel while keeping background audio playback active.
- **REMOTE HOLD & RAPID BURST KEY SUPPORT**: Added `hold_secs` duration support in `remote.send_command`, mapping to `KEY_OK_LONG_PRESS` / `KEY_MUTE_LONG_PRESS` and high-speed key repetitions.
- **DEEP LINK & DIRECT CHANNEL NUMBER TUNING**: `play_media` now handles direct URI schemes (`netflix://`, `youtube://`, `https://...`) and numeric / decimal channel tuning sequences (e.g. `"70"`, `"7.1"` sending `KEY_CHANNELDOT`).
- **EXTENDED CLI DIAGNOSTICS & TESTING**: Added `launch-app`, `wake`, `--p12`, `--ca`, and `--verify-ssl` subcommands/flags to `test_client.py`.
- **STATIC DHCP & ETHERNET GUIDELINES**: Added network best practices documentation detailing fixed IP reservations and wired Ethernet for reliable Wake-on-LAN (WoL) from deep standby.

## [2.6.0] - 2026-09-11

### Added
- **MEDIA TRANSPORT CONTROLS OPTION (`enable_media_controls`)**: Added new configurable option (default: enabled) to expose or suppress the media player transport control bar (play/pause, stop, skip). Useful for users who only need the TV as an input switcher without transport buttons cluttering the media player card.
- **ACTIVE SOURCE SENSOR (`sensor.{tv}_active_source`)**: Dedicated sensor tracking the currently selected physical input or app (`HDMI1`, `HDMI2`, `TV`, `Netflix`, etc.), with extra attributes for all `available_sources`, `connected_inputs`, and user-defined custom HDMI labels.
- **ACTIVE APP SENSOR (`sensor.{tv}_active_app`)**: Dedicated sensor tracking the currently running Smart TV application name, with extra attributes for `total_installed_apps` and `favorite_apps`.
- **DYNAMIC APP ARTWORK**: `media_image_url` now resolves live CDN icon URLs from the TV's app registry for the currently active app, enabling rich media player card artwork in the HA UI.
- **SYNC CLOCK BUTTON (`button.{tv}_sync_clock`)**: Diagnostic button to trigger manual TV clock synchronization via UPnP/DLNA `Date` header extraction, resolving pairing hash mismatches after NTP failures or offline periods.
- **MQTT CONNECTED BINARY SENSOR (`binary_sensor.{tv}_mqtt_connected`)**: Connectivity sensor reflecting real-time MQTT broker connection state, distinct from TV power state.

### Changed
- **DYNAMIC `supported_features`**: The media player `supported_features` property is now computed dynamically based on the `enable_media_controls` option rather than being a fixed static bitmask. Transport controls (`PLAY`, `PAUSE`, `STOP`, `NEXT_TRACK`, `PREVIOUS_TRACK`) are only advertised when the option is enabled (default: on).

## [2.5.0] - 2026-09-11


### Added
- **HACS & HASSFEST CI VALIDATION**: Added complete HACS repository configuration (`hacs.json`) with minimum Home Assistant version requirements, `integration_type: "device"` in `manifest.json`, and configured dual-action CI validation (`hassfest` + `hacs/action`) on every pull request and push.
- **SECURITY HARDENING & DEFUSED XML PARSING**: Integrated `defusedxml` into UPnP/DLNA XML discovery parsers to protect against XML Entity Expansion (Billion Laughs) and external DTD vulnerabilities during discovery.
- **CLIENT ARCHITECTURE REFACTORING**: Extracted socket and probe diagnostics to `discovery.py`, implemented centralized callback registry and thread-safe dispatching, reducing `client.py` footprint by ~60% while maintaining 100% backward compatibility.
- **SUBNET-AWARE WAKE-ON-LAN**: Enhanced Wake-on-LAN magic packet transmission to broadcast to both the target `/24` subnet directed broadcast address (e.g. `192.168.50.255`) and `255.255.255.255` for maximum cross-VLAN/routed network reliability.
- **CONFIG FLOW UX & SANITIZATION**: Added interactive `SelectSelector` dropdown with friendly descriptive profile labels (`Auto Detect`, `VIDAA 2.0 / 2024+`, `RemoteNOW / 2018–2023`, `Legacy Unencrypted`), smart certificate routing (skipping cert modal if valid certs exist on disk), and automatic PIN sanitization (stripping spaces/dashes).
- **EXTENDED MQTT TOPIC COVERAGE**: Added subscription and dispatch handling for `/remoteapp/mobile/broadcast/ui_service/volume`, `/remoteapp/mobile/broadcast/ui_service/data/hotelmodechange`, `/remoteapp/mobile/{client}/platform_service/data/gettvinfo`, `/remoteapp/mobile/{client}/platform_service/data/getdeviceinfo`, `/remoteapp/mobile/{client}/ui_service/data/capability`, and direct state replies on `.../ui_service/data/state`.
- **EXTENDED REMOTE KEY ALIASES**: Added aliases for `ok_long`, `mute_long`, `mouse`, `zoom_in`, `zoom_out` to `KEY_ALIASES`.
- **EXPANDED TEST SUITE**: Added comprehensive unit tests covering subnet WoL broadcasting, volume topic variants, callback error isolation, and defused XML malformed data recovery (33 passing unit tests).

## [2.2.0] - 2026-09-11

### Added
- **LEGACY STATIC AUTHENTICATION PROFILE (`legacy`)**: Added native support for pre-2022 Hisense TVs using static MQTT credentials (`hisenseservice` / `multimqttservice`). Automatically probes TV capabilities, bypasses PIN pairing, and disables token refresh loops for legacy devices.
- **AUTOMATIC TV CLOCK SYNCHRONIZATION**: Added UPnP/DLNA HTTP `Date` header extraction to synchronize pairing timestamp calculations directly with the TV's internal clock, preventing `rc: 5` / `rc: 4` authentication rejections during clock drift or offline time rollover.
- **NATIVE HOME ASSISTANT REAUTH & RECONFIGURE FLOWS**: Implemented `async_step_reauth`, `async_step_reauth_confirm`, and `async_step_reconfigure` (`supports_reconfigure: true`) with automated reauth triggering upon expired sessions and one-click PIN regeneration.
- **CLI DIAGNOSTIC PROBE ENHANCEMENTS**: Updated `test_client.py` with `--profile legacy`, dynamic 3-tier auth compatibility probing (Legacy Static, Standard Dynamic, Modern Dynamic), and Markdown issue reporting.

### Fixed
- **ENTITY STATE & AVAILABILITY OVERHAUL**: Media player and remote entities now correctly report `state = STATE_OFF` (`"off"`) with `available = True` while the TV is in standby/disconnected, preserving UI power toggles and automation triggers.
- **CODE DEDUPLICATION & ARCHITECTURAL REFACTORING**: Extracted options flow into dedicated `options_flow.py`, centralized ARP hardware MAC resolution in `discovery.py`, and ensured 100% logic sharing between the HA integration and `test_client.py`.

## [2.0.0] - 2026-09-06

### Added
- **MODULAR ARCHITECTURE REFACTOR**: Modularized the codebase into single-responsibility components: [`crypto.py`](custom_components/hisense_vidaa/crypto.py) (authentication hashing, XOR masking, and cert discovery), [`discovery.py`](custom_components/hisense_vidaa/discovery.py) (UPnP XML and mDNS discovery), [`const.py`](custom_components/hisense_vidaa/const.py) (constants and profile definitions), and [`client.py`](custom_components/hisense_vidaa/client.py) (async MQTT lifecycle).
- **DUAL-TIER AUTHENTICATION PROFILE SELECTOR**: Added support for choosing between Modern VIDAA 2.0 (`libmqttcrypt.so` / `Q0704`+ with XOR mask and Modern salt `h!i@s#$v%i^d&a*a`) and Legacy RemoteNOW (`h*i&s%e!r^v0i1c9` salt), alongside automatic profile detection and selective certificate resolution (`vidaa_2024_*`, `remotenow_2018_*`, and `cert.pem`).

### Fixed
- **INSTANT 1ST-ATTEMPT PAIRING**: Resolved race condition during initial pairing where the TV challenge response arrived before the MQTT subscription was acknowledged by adding a 500ms subscription settling delay and multi-attempt retry loop for `vidaa_app_connect`.
- **RECONNECTION STORM PROTECTION**: Added exponential reconnect backoff (`min_delay=2, max_delay=30`) and safe executor-based disconnection handling upon config entry unload.
- **GITHUB ACTIONS RELEASE WORKFLOW**: Fixed `actions/checkout` versioning and changelog extraction parser in CI release workflows.

## [1.5.0] - 2026-09-06

### Added
- **OPTIONS FLOW SUPPORT**: Added `OptionsFlowHandler` allowing full configuration of features and device behaviors via **Settings -> Devices & Services -> Configure** on existing TVs without re-pairing.
- **DEDICATED REMOTE ENTITY PLATFORM (`remote`)**: Added native `remote` entity (`remote.<tv_name>`) supporting D-pad navigation, numeric keypad, channel switching, media controls, color buttons, and app shortcuts.
- **MEDIA CONTROLS EXPANSION**: Added `PLAY`, `PAUSE`, `STOP`, `NEXT_TRACK`, `PREVIOUS_TRACK`, and `PLAY_MEDIA` support to the `media_player` entity.
- **SMART TV APPS IN SOURCE LIST**: Configurable option (`include_apps_in_sources`) to dynamically include installed Smart TV apps (Netflix, YouTube, Prime, Plex, etc.) in the `media_player` source dropdown alongside hardware HDMI/TV inputs.
- **WAKE-ON-LAN POWER ON**: Configurable option (`enable_wol`) to broadcast a UDP magic packet on `turn_on` to wake TVs from deep standby.
- **KEY ALIAS RESOLUTION**: Added alias normalizer supporting friendly command names (`up`, `down`, `home`, `menu`, `back`, `netflix`, `youtube`, etc.) across `remote.send_command` and CLI `test_client.py`.

## [1.4.2] - 2026-09-06

### Added
- **DYNAMIC TV DEVICE & ENTITY NAMING**: Config flow now automatically detects the TV's broadcast friendly name (e.g. `Smart TV`, custom name from TV settings, or model code) via UPnP/mDNS and names the Home Assistant device and entity accordingly upon pairing.

## [1.4.1] - 2026-09-06

### Added
- **GITHUB ISSUE DIAGNOSTIC REPORT (`report`)**: Added `python3 test_client.py report --ip <IP>` command generating a pre-formatted, redacted Markdown diagnostic block with hardware specs, firmware indicators, and auth capabilities ready to paste into GitHub issues.
- **ACTIVE MULTI-TIER AUTH PROBING**: Enhanced `ping` and `report` with live compatibility testing for standard dynamic (`his$<timestamp>`), modern dynamic (XOR), and legacy static (`hisenseservice`) pairing handshakes.
- **AUTOMATED DEVICE FINGERPRINTING**: Added UPnP/DLNA XML parser and mDNS discovery to automatically identify TV model names, VIDAA platform capabilities, and Wi-Fi / Ethernet MAC addresses.

## [1.4.0] - 2026-09-06

### Added
- **NEW VIDAA FIRMWARE AUTHENTICATION FALLBACK**: Added support for newer VIDAA OS firmware versions (e.g. `V0000.09.09U.P1027`) where the internal broker rejects pairing with MQTT `rc: 5`. The integration now automatically falls back to XOR timestamp credential hashing (`his${timestamp ^ 6239759785777146216}`) on `rc: 5` pairing failures.
- **IMPROVED CONNECTION CLEANUP**: Ensured MQTT client disconnect and loop termination on failed initial pairing attempts.

## [1.3.1] - 2026-09-04

### Changed
- **DOCUMENTATION & REPOSITORIES**: Updated references to legacy alternatives ([`sehaas/ha_hisense_tv`](https://github.com/sehaas/ha_hisense_tv) and [`Krazy998/mqtt-hisensetv`](https://github.com/Krazy998/mqtt-hisensetv/)).
- **PROBE MESSAGES**: Pointed diagnostic probe output in `client.py` directly to the README section for integration selection guidance.

## [1.3.0] - 2026-09-04

### Added
- **STANDARD HACS DIRECTORY STRUCTURE**: Relocated integration files into standard `custom_components/hisense_vidaa/` layout for seamless HACS installation and updates.
- **HACS BRANDING & ASSETS**: Included icon and logo brand assets inside the component directory for HACS validation.
- **MY HOME ASSISTANT BADGE**: Added 1-click installation badge and updated documentation for HACS Custom Repository setup.

### Changed
- **HACS CONFIGURATION**: Removed deprecated `content_in_root` attribute in `hacs.json`.
- **CI WORKFLOWS**: Streamlined Hassfest validation and HACS Action checks to run directly on the standard component directory.

## [1.2.0] - 2026-09-04

### Added
- **CONNECTIVITY & FIRMWARE PROBE (`ping`)**: Added a 3-tier diagnostic probe (TCP port, TLS handshake, and broker response) with automatic firmware detection (suggests legacy vs modern VIDAA integration).
- **SSL CERTIFICATE TESTING (`test-ssl`)**: Added dedicated `test-ssl` command and `test_ssl_connection()` method to verify TLSv1.2 cipher suites and certificate validity directly against port 36669.
- **CUSTOM CERTIFICATE PATHS**: Added support for explicit `--cert` and `--key` arguments with fallback search order (`custom` -> `certs/` -> `/config/certs/` -> `/config/ssl/`).
- **STANDALONE TEST SUITE (`test_client.py`)**: Unified testing utility sharing 100% of its backend logic with the Home Assistant `HisenseTvClient` integration code.
- **AUTOMATIC MAC ADDRESS DISCOVERY**: Removed manual MAC address input from the setup modal; the integration now automatically discovers and formats the hardware MAC address via ARP cache and binds it to the Home Assistant Device Registry.
- **DOCUMENTATION OF LEGACY ALTERNATIVES**: Added comprehensive guide in README referencing established legacy integrations (`ha_hisense_tv`, `hisensetv`, `mqtt-hisensetv`) for older static-credential models.

### Fixed
- **ENTITY NAMING DUPLICATION**: Fixed entity ID generation producing `media_player.hisense_tv_hisense_tv_...` by setting `_attr_has_entity_name = True` and removing redundant name overrides (Issue #5).
- **THREAD-STORM PREVENTION**: Added mutex locks and a 10-second minimum cooldown to prevent thread storms and runaway CPU usage during connection failures or network drops (Issue #6).
- **THREAD-SAFE ASYNC FUTURE COMPLETION**: Wrapped event loop futures with `call_soon_threadsafe` across Paho-MQTT network threads and asyncio loops to ensure instantaneous challenge PIN and token resolution.
- **STARTUP BLOCKING CALLS**: Offloaded certificate loading and MQTT client instantiation to `loop.run_in_executor` during async config flows.

## [1.1.0] - 2026-07-21

### Fixed
- **STANDBY WAKE-UP**: Switched `turn_on` method from Wake-on-LAN to direct MQTT `KEY_POWER` command, resolving standby power control issues.
- **STABLE BACKGROUND POLLING**: Fixed token expiration causing permanent disconnection after the TV was turned off for more than 2 hours. The integration now intercepts MQTT auth failures, asynchronously refreshes the access token, updates Paho credentials, and reconnects in the background.
- **NON-BLOCKING STARTUP**: Modified startup MQTT connection loop to be non-blocking. If the TV is powered down when Home Assistant boots, the integration setup succeeds and auto-connects as soon as the TV becomes reachable on the network.
- **DYNAMIC TOKEN STORAGE**: Refreshed tokens are now dynamically persisted back to the Config Entry in Home Assistant, surviving restarts.

### Removed
- **WAKE-ON-LAN**: Removed `wakeonlan` package dependency and UDP magic packet dispatching entirely. Retained MAC address configuration input solely for device registry binding.
- **MEDIA BROWSER**: Removed Home Assistant Media Browser and `PLAY_MEDIA` features to simplify integration and prevent diagnostic errors.

## [1.0.0] - 2026-07-19

### Added
- **Initial Release**: Full conversion of the standalone `hisense.py` Python control script into a native Home Assistant custom integration.
- **Direct Secure Connection**: Native connection directly to the TV's secure TLS MQTT broker on port `36669` using certificates packaged with the component. No Mosquitto configuration or systems-level bridges are required.
- **User-Friendly Setup**: Integrated Config Flow for simple step-by-step setup in the Home Assistant UI (IP, optional MAC, and automatic display-and-entry challenge PIN).
- **Core Controls**: Complete media player capabilities (Power toggle, volume adjustment, volume steps, mute/unmute).
- **Filtered Input Source List**: Cleaned up the input source selector to list only hardware interfaces (HDMI1, HDMI2, HDMI3, TV, AV) and ignore internal VIDAA app services, keeping the UI simplified.
- **Robust Connection Handlers**: 
  - Offloaded MQTT connections to a thread pool executor.
  - Used event-loop threadsafe hooks (`call_soon_threadsafe`) for UI state updates.
  - Added smart token refresh logic on startup to prevent session conflicts and infinite reloading loops.
