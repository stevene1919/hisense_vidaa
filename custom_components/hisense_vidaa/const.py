"""Constants for the Hisense VIDAA TV integration."""

DOMAIN = "hisense_vidaa"

CONF_IP_ADDRESS = "ip_address"
CONF_MAC_ADDRESS = "mac_address"
CONF_NAME = "name"
CONF_CERTFILE = "certfile"
CONF_KEYFILE = "keyfile"
CONF_USE_SSL = "use_ssl"
CONF_AUTH_PROFILE = "auth_profile"
CONF_CLIENT_ID = "client_id"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCESS_TOKEN = "access_token"
CONF_ACCESS_TOKEN_TIME = "access_token_time"
CONF_ACCESS_TOKEN_DURATION = "access_token_duration"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_TIME = "refresh_token_time"
CONF_REFRESH_TOKEN_DURATION = "refresh_token_duration"
CONF_MODEL = "model"
CONF_MANUFACTURER = "manufacturer"
CONF_SW_VERSION = "sw_version"
CONF_SECONDARY_MAC_ADDRESS = "secondary_mac_address"

# Integration Options
CONF_ENABLE_REMOTE = "enable_remote"
CONF_ENABLE_NOTIFY = "enable_notify"
CONF_ENABLE_WOL = "enable_wol"
CONF_INCLUDE_APPS_IN_SOURCES = "include_apps_in_sources"
CONF_ENABLE_MEDIA_CONTROLS = "enable_media_controls"
CONF_ENABLE_CEC_NAMES = "enable_cec_names"
CONF_KEY_DELAY = "key_delay"
CONF_KEY_REPEAT = "key_repeat"

DEFAULT_PORT = 36669
DEFAULT_NAME = "Hisense VIDAA TV"
DEFAULT_TIMEOUT = 10
DEFAULT_WOL_TIMEOUT = 30
DEFAULT_RECONNECT_INTERVAL = 15

DEFAULT_CERT_DIR = "certs"
DEFAULT_CERT_FILENAME = "hisense.crt"
DEFAULT_KEY_FILENAME = "hisense.key"

DEFAULT_ENABLE_REMOTE = True
DEFAULT_ENABLE_NOTIFY = False
DEFAULT_ENABLE_WOL = False
DEFAULT_INCLUDE_APPS_IN_SOURCES = True
DEFAULT_ENABLE_MEDIA_CONTROLS = True
DEFAULT_ENABLE_CEC_NAMES = True
DEFAULT_KEY_DELAY = 0.2
DEFAULT_KEY_REPEAT = 1
DEFAULT_AUTH_PROFILE = "auto"
DEFAULT_USE_SSL = True

# Service Names & Attributes
SERVICE_SEND_KEY = "send_key"
SERVICE_LAUNCH_APP = "launch_app"

ATTR_KEY = "key"
ATTR_REPEAT = "repeat"
ATTR_DELAY = "delay"
ATTR_APP = "app"

AUTH_PROFILES = {
    "auto": "Auto Detect (Recommended)",
    "modern": "VIDAA 2.0 (Newer Firmware / 2024+)",
    "remotenow": "RemoteNOW (Standard / 2018–2023)",
    "legacy": "Legacy Static (Pre-2022 / Static Credentials)",
}

KEY_ALIASES = {
    # Power
    "power": "KEY_POWER",
    "pwr": "KEY_POWER",

    # D-Pad Navigation
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
    "ok": "KEY_OK",
    "enter": "KEY_OK",
    "select": "KEY_OK",
    "ok_long": "KEY_OK_LONG_PRESS",
    "enter_long": "KEY_OK_LONG_PRESS",
    "select_long": "KEY_OK_LONG_PRESS",

    # Menu & System
    "back": "KEY_RETURNS",
    "return": "KEY_RETURNS",
    "returns": "KEY_RETURNS",
    "home": "KEY_HOME",
    "menu": "KEY_MENU",
    "settings": "KEY_MENU",
    "exit": "KEY_EXIT",
    "cancel": "KEY_EXIT",
    "info": "KEY_INFO",
    "display": "KEY_INFO",

    # Volume & Mute
    "volume_up": "KEY_VOLUMEUP",
    "volumeup": "KEY_VOLUMEUP",
    "volup": "KEY_VOLUMEUP",
    "vol+": "KEY_VOLUMEUP",
    "volume+": "KEY_VOLUMEUP",
    "vol_up": "KEY_VOLUMEUP",
    "volume_down": "KEY_VOLUMEDOWN",
    "volumedown": "KEY_VOLUMEDOWN",
    "voldown": "KEY_VOLUMEDOWN",
    "vol-": "KEY_VOLUMEDOWN",
    "volume-": "KEY_VOLUMEDOWN",
    "vol_down": "KEY_VOLUMEDOWN",
    "mute": "KEY_MUTE",
    "silence": "KEY_MUTE",
    "mute_long": "KEY_MUTE_LONG_PRESS",

    # Voice Assistant
    "voice_up": "KEY_VOICEUP",
    "voiceup": "KEY_VOICEUP",
    "voice+": "KEY_VOICEUP",
    "voice_down": "KEY_VOICEDOWN",
    "voicedown": "KEY_VOICEDOWN",
    "voice-": "KEY_VOICEDOWN",

    # Free-to-Air Channel Rockers
    "channel_up": "KEY_CHANNELUP",
    "channelup": "KEY_CHANNELUP",
    "chup": "KEY_CHANNELUP",
    "ch+": "KEY_CHANNELUP",
    "channel+": "KEY_CHANNELUP",
    "ch_up": "KEY_CHANNELUP",
    "channel_down": "KEY_CHANNELDOWN",
    "channeldown": "KEY_CHANNELDOWN",
    "chdown": "KEY_CHANNELDOWN",
    "ch-": "KEY_CHANNELDOWN",
    "channel-": "KEY_CHANNELDOWN",
    "ch_down": "KEY_CHANNELDOWN",
    "dot": "KEY_CHANNELDOT",
    "channel_dot": "KEY_CHANNELDOT",
    "channeldot": "KEY_CHANNELDOT",
    "ch_dot": "KEY_CHANNELDOT",
    "dash": "KEY_CHANNELDOT",
    "period": "KEY_CHANNELDOT",

    # Media Playback Controls
    "play": "KEY_PLAY",
    "pause": "KEY_PAUSE",
    "play_pause": "KEY_PLAY",
    "playpause": "KEY_PLAY",
    "stop": "KEY_STOP",
    "fast_forward": "KEY_FORWARDS",
    "fastforward": "KEY_FORWARDS",
    "forward": "KEY_FORWARDS",
    "forwards": "KEY_FORWARDS",
    "ff": "KEY_FORWARDS",
    "fwd": "KEY_FORWARDS",
    "rewind": "KEY_BACK",
    "fast_rewind": "KEY_BACK",
    "fastrewind": "KEY_BACK",
    "rw": "KEY_BACK",
    "rev": "KEY_BACK",

    # Subtitles, EPG, Teletext, Channel List
    "subtitle": "KEY_SUBTITLE",
    "subtitles": "KEY_SUBTITLE",
    "sub": "KEY_SUBTITLE",
    "subs": "KEY_SUBTITLE",
    "cc": "KEY_SUBTITLE",
    "guide": "KEY_EPG",
    "epg": "KEY_EPG",
    "tv_guide": "KEY_EPG",
    "program_guide": "KEY_EPG",
    "chlist": "KEY_CHLIST",
    "channel_list": "KEY_CHLIST",
    "ch_list": "KEY_CHLIST",
    "channels": "KEY_CHLIST",
    "list": "KEY_CHLIST",
    "text": "KEY_TEXT",
    "teletext": "KEY_TEXT",
    "txt": "KEY_TEXT",
    "ttx": "KEY_TEXT",

    # Interactive Color Keys (Freeview / HbbTV)
    "red": "KEY_RED",
    "color_red": "KEY_RED",
    "green": "KEY_GREEN",
    "color_green": "KEY_GREEN",
    "yellow": "KEY_YELLOW",
    "color_yellow": "KEY_YELLOW",
    "blue": "KEY_BLUE",
    "color_blue": "KEY_BLUE",

    # Input & TV Source Controls
    "livetv": "KEY_LIVETV",
    "live_tv": "KEY_LIVETV",
    "tv": "KEY_LIVETV",
    "antenna": "KEY_LIVETV",
    "dtv": "KEY_LIVETV",
    "media": "KEY_MEDIA",
    "usb": "KEY_MEDIA",
    "media_center": "KEY_MEDIA",
    "apps": "KEY_APPS",
    "app_store": "KEY_APPS",
    "app_menu": "KEY_APPS",
    "input_menu": "KEY_MENU",
    "source_menu": "KEY_MENU",
    "key_input_menu": "KEY_MENU",
    "key_source_menu": "KEY_MENU",

    # Screen / Audio / Mouse / Zoom
    "audio_only": "KEY_AUDIO",
    "screen_off": "KEY_AUDIO",
    "screenoff": "KEY_AUDIO",
    "pic_off": "KEY_AUDIO",
    "picoff": "KEY_AUDIO",
    "audio": "KEY_AUDIO",
    "mouse": "KEY_LEFTMOUSEKEYS",
    "left_mouse": "KEY_LEFTMOUSEKEYS",
    "mouse_click": "KEY_LEFTMOUSEKEYS",
    "mouse_up": "KEY_UDULEFTMOUSEKEYS",
    "mouse_down": "KEY_UDDLEFTMOUSEKEYS",
    "zoom_in": "KEY_ZOOMIN",
    "zoomin": "KEY_ZOOMIN",
    "zoom+": "KEY_ZOOMIN",
    "zoom_out": "KEY_ZOOMOUT",
    "zoomout": "KEY_ZOOMOUT",
    "zoom-": "KEY_ZOOMOUT",

    # Number Pad
    "0": "KEY_0",
    "1": "KEY_1",
    "2": "KEY_2",
    "3": "KEY_3",
    "4": "KEY_4",
    "5": "KEY_5",
    "6": "KEY_6",
    "7": "KEY_7",
    "8": "KEY_8",
    "9": "KEY_9",

    # Direct Hardware App Buttons
    "netflix": "KEY_NETFLIX",
    "youtube": "KEY_YOUTUBE",
    "prime": "KEY_PRIME",
    "prime_video": "KEY_PRIME",
    "amazon_prime": "KEY_PRIME",

    # --------------------------------------------------------------------------
    # Worldwide Smart App Shortcuts (Auto-Mapped to Installed Apps)
    # --------------------------------------------------------------------------
    # Global Services
    "disney": "app:Disney+",
    "disneyplus": "app:Disney+",
    "disney+": "app:Disney+",
    "apple_tv": "app:Apple TV",
    "appletv": "app:Apple TV",
    "apple_tv+": "app:Apple TV",
    "apple": "app:Apple TV",
    "max": "app:HBO Max",
    "hbo_max": "app:HBO Max",
    "hbomax": "app:HBO Max",
    "hbo": "app:HBO Max",
    "paramount": "app:Paramount+",
    "paramountplus": "app:Paramount+",
    "paramount+": "app:Paramount+",
    "spotify": "app:Spotify",
    "amazon_music": "app:Amazon Music",
    "deezer": "app:DEEZER",
    "tidal": "app:Tidal",
    "plex": "app:Plex",
    "crunchyroll": "app:Crunchyroll",
    "dazn": "app:DAZN",
    "twitch": "app:Twitch",
    "tubi": "app:tubi",
    "tubitv": "app:tubi",
    "pluto": "app:Pluto TV",
    "plutotv": "app:Pluto TV",
    "pluto_tv": "app:Pluto TV",
    "rakuten": "app:Rakuten TV",
    "rakutentv": "app:Rakuten TV",
    "rakuten_tv": "app:Rakuten TV",
    "redbull": "app:Red Bull TV",
    "redbulltv": "app:Red Bull TV",
    "red_bull_tv": "app:Red Bull TV",
    "mubi": "app:MUBI",
    "ufc": "app:UFC",
    "nba": "app:NBA",
    "uefa": "app:UEFA.tv",
    "uefatv": "app:UEFA.tv",
    "f1": "app:F1 TV",
    "f1tv": "app:F1 TV",
    "vidaa_tv": "app:VIDAA tv",
    "vidaatv": "app:VIDAA tv",
    "vidaa_free": "app:VIDAA tv",
    "vidaa_kids": "app:VIDAA   Kids",
    "vidaakids": "app:VIDAA   Kids",
    "kidoodle": "app:Kidoodle TV",
    "kidoodle_tv": "app:Kidoodle TV",
    "filmzie": "app:Filmzie",
    "wetv": "app:WeTV",
    "britbox": "app:Britbox",

    # Australia & New Zealand
    "stan": "app:Stan.",
    "kayo": "app:Kayo",
    "kayosports": "app:Kayo",
    "kayo_sports": "app:Kayo",
    "binge": "app:Binge",
    "foxtel": "app:Foxtel",
    "foxtel_now": "app:Foxtel",
    "foxtel_go": "app:Foxtel",
    "iview": "app:ABC iview",
    "abc_iview": "app:ABC iview",
    "abciview": "app:ABC iview",
    "sbs": "app:SBS ON DEMAND",
    "sbs_on_demand": "app:SBS ON DEMAND",
    "sbsondemand": "app:SBS ON DEMAND",
    "7plus": "app:7plus",
    "seven_plus": "app:7plus",
    "sevenplus": "app:7plus",
    "9now": "app:9Now",
    "nine_now": "app:9Now",
    "ninenow": "app:9Now",
    "10play": "app:10 play",
    "10_play": "app:10 play",
    "ten_play": "app:10 play",
    "tenplay": "app:10 play",
    "optus": "app:Optus Sport",
    "optus_sport": "app:Optus Sport",
    "tvnz": "app:TVNZ+",
    "tvnz+": "app:TVNZ+",
    "three_now": "app:ThreeNow",
    "threenow": "app:ThreeNow",
    "neon": "app:Neon",

    # UK & Europe
    "iplayer": "app:BBC iPlayer",
    "bbc_iplayer": "app:BBC iPlayer",
    "bbciplayer": "app:BBC iPlayer",
    "itvx": "app:ITVX",
    "itv_hub": "app:ITVX",
    "itv": "app:ITVX",
    "all4": "app:Channel 4",
    "channel4": "app:Channel 4",
    "c4": "app:Channel 4",
    "my5": "app:My5",
    "channel5": "app:My5",
    "nowtv": "app:NOW",
    "now_tv": "app:NOW",
    "discovery": "app:Discovery+",
    "discoveryplus": "app:Discovery+",
    "discovery+": "app:Discovery+",
    "viaplay": "app:Viaplay",
    "rtl": "app:RTL+",
    "rtlplus": "app:RTL+",
    "rtl+": "app:RTL+",
    "joyn": "app:Joyn",
    "zdf": "app:ZDFmediathek",
    "ard": "app:ARD Mediathek",
    "molotov": "app:Molotov",
    "raiplay": "app:RaiPlay",
    "rai": "app:RaiPlay",
    "mediaset": "app:Mediaset Infinity",
    "rtve": "app:RTVE Play",
    "movistar": "app:Movistar+",

    # North America
    "peacock": "app:Peacock",
    "peacocktv": "app:Peacock",
    "hulu": "app:Hulu",
    "sling": "app:Sling TV",
    "slingtv": "app:Sling TV",
    "fubo": "app:FuboTV",
    "fubotv": "app:FuboTV",
    "philo": "app:Philo",
    "roku": "app:The Roku Channel",
    "vudu": "app:Vudu",
    "crackle": "app:Crackle",
    "freevee": "app:Freevee",
    "cbc_gem": "app:CBC Gem",
    "gem": "app:CBC Gem",
    "crave": "app:Crave",
    "ctv": "app:CTV",
    "global_tv": "app:Global TV",
}
