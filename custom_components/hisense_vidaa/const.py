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

DEFAULT_CERT_DIR = "ssl"
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
SERVICE_SET_PICTURE_SETTING = "set_picture_setting"
SERVICE_SET_SOUND_SETTING = "set_sound_setting"
SERVICE_SEND_TEXT_INPUT = "send_text_input"

ATTR_KEY = "key"
ATTR_REPEAT = "repeat"
ATTR_DELAY = "delay"
ATTR_APP = "app"
ATTR_MENU_ID = "menu_id"
ATTR_MENU_VALUE = "menu_value"
ATTR_TEXT = "text"
ATTR_ACTION = "action"

AUTH_PROFILES = {
    "auto": "Auto Detect (Recommended)",
    "modern": "VIDAA 2.0 (Newer Firmware / 2024+)",
    "middle": "VIDAA 1.5 / Middle (3000–3285)",
    "remotenow": "RemoteNOW (Standard / 2018–2023)",
    "legacy": "Legacy Static (Pre-2022 / Static Credentials)",
}

try:
    from .tv.aliases import ALL_KEY_AND_APP_ALIASES as KEY_ALIASES
except (ImportError, ValueError):
    from tv.aliases import ALL_KEY_AND_APP_ALIASES as KEY_ALIASES  # noqa: F401
