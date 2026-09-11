DOMAIN = "hisense_vidaa"

CONF_IP_ADDRESS = "ip_address"
CONF_MAC_ADDRESS = "mac_address"
CONF_CLIENT_ID = "client_id"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCESS_TOKEN = "access_token"
CONF_ACCESS_TOKEN_TIME = "access_token_time"
CONF_ACCESS_TOKEN_DURATION = "access_token_duration"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_TIME = "refresh_token_time"
CONF_REFRESH_TOKEN_DURATION = "refresh_token_duration"

DEFAULT_NAME = "Hisense TV"

CONF_ENABLE_REMOTE = "enable_remote"
CONF_ENABLE_WOL = "enable_wol"
CONF_INCLUDE_APPS_IN_SOURCES = "include_apps_in_sources"
CONF_AUTH_PROFILE = "auth_profile"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_version"
CONF_MANUFACTURER = "manufacturer"
CONF_CERTFILE = "certfile"
CONF_KEYFILE = "keyfile"
CONF_USE_SSL = "use_ssl"

DEFAULT_USE_SSL = True
DEFAULT_CERT_DIR = "certs"
DEFAULT_CERT_FILENAME = "hisense.crt"
DEFAULT_KEY_FILENAME = "hisense.key"

SERVICE_SEND_KEY = "send_key"
SERVICE_LAUNCH_APP = "launch_app"
ATTR_KEY = "key"
ATTR_APP = "app"
ATTR_REPEAT = "repeat"
ATTR_DELAY = "delay"

DEFAULT_ENABLE_REMOTE = True
DEFAULT_ENABLE_WOL = False
DEFAULT_INCLUDE_APPS_IN_SOURCES = True
DEFAULT_AUTH_PROFILE = "auto"

AUTH_PROFILES = {
    "auto": "Auto Detect (Recommended)",
    "modern": "VIDAA 2.0 (Newer Firmware / 2024+)",
    "remotenow": "RemoteNOW (Standard / 2018–2023)",
    "legacy": "Legacy Static (Pre-2022 / Static Credentials)",
}

KEY_ALIASES = {
    "power": "KEY_POWER",
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
    "ok": "KEY_OK",
    "enter": "KEY_OK",
    "select": "KEY_OK",
    "back": "KEY_RETURNS",
    "return": "KEY_RETURNS",
    "returns": "KEY_RETURNS",
    "home": "KEY_HOME",
    "menu": "KEY_MENU",
    "exit": "KEY_EXIT",
    "info": "KEY_INFO",
    "volume_up": "KEY_VOLUMEUP",
    "volumeup": "KEY_VOLUMEUP",
    "volume_down": "KEY_VOLUMEDOWN",
    "volumedown": "KEY_VOLUMEDOWN",
    "mute": "KEY_MUTE",
    "channel_up": "KEY_CHANNELUP",
    "channelup": "KEY_CHANNELUP",
    "channel_down": "KEY_CHANNELDOWN",
    "channeldown": "KEY_CHANNELDOWN",
    "play": "KEY_PLAY",
    "pause": "KEY_PAUSE",
    "stop": "KEY_STOP",
    "fast_forward": "KEY_FORWARDS",
    "fastforward": "KEY_FORWARDS",
    "forwards": "KEY_FORWARDS",
    "rewind": "KEY_BACK",
    "subtitle": "KEY_SUBTITLE",
    "subtitles": "KEY_SUBTITLE",
    "guide": "KEY_EPG",
    "epg": "KEY_EPG",
    "red": "KEY_RED",
    "green": "KEY_GREEN",
    "yellow": "KEY_YELLOW",
    "blue": "KEY_BLUE",
    "netflix": "KEY_NETFLIX",
    "youtube": "KEY_YOUTUBE",
    "prime": "KEY_PRIME",
    "ok_long": "KEY_OK_LONG_PRESS",
    "mute_long": "KEY_MUTE_LONG_PRESS",
    "mouse": "KEY_LEFTMOUSEKEYS",
    "left_mouse": "KEY_LEFTMOUSEKEYS",
    "zoom_in": "KEY_ZOOMIN",
    "zoomin": "KEY_ZOOMIN",
    "zoom_out": "KEY_ZOOMOUT",
    "zoomout": "KEY_ZOOMOUT",
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
}
