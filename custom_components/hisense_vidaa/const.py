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
CONF_BRAND = "brand"
CONF_SW_VERSION = "sw_version"
CONF_SECONDARY_MAC_ADDRESS = "secondary_mac_address"

CONF_ENABLE_REMOTE = "enable_remote"
CONF_ENABLE_NOTIFY = "enable_notify"
CONF_ENABLE_WOL = "enable_wol"
CONF_INCLUDE_APPS_IN_SOURCES = "include_apps_in_sources"
CONF_ENABLE_MEDIA_CONTROLS = "enable_media_controls"
CONF_ENABLE_CEC_NAMES = "enable_cec_names"
CONF_ENABLE_PICTURE_CONTROLS = "enable_picture_controls"
CONF_ENABLE_SOUND_CONTROLS = "enable_sound_controls"
CONF_ENABLE_AUDIO_ONLY = "enable_audio_only"
CONF_KEY_DELAY = "key_delay"
CONF_KEY_REPEAT = "key_repeat"
CONF_REFRESH_IN_STANDBY = "refresh_in_standby"

DEFAULT_PORT = 36669
DEFAULT_NAME = "Hisense VIDAA TV"
DEFAULT_BRAND = "his"
DEFAULT_BRAND_OPTION = "auto"
DEFAULT_TIMEOUT = 10
DEFAULT_WOL_TIMEOUT = 30
DEFAULT_RECONNECT_INTERVAL = 15

DEFAULT_CERT_DIR = "ssl"
DEFAULT_CERT_FILENAME = "hisense.crt"
DEFAULT_KEY_FILENAME = "hisense.key"

DEFAULT_ENABLE_REMOTE = True
DEFAULT_ENABLE_NOTIFY = False
DEFAULT_ENABLE_WOL = False
DEFAULT_REFRESH_IN_STANDBY = False
DEFAULT_INCLUDE_APPS_IN_SOURCES = True
DEFAULT_ENABLE_MEDIA_CONTROLS = True
DEFAULT_ENABLE_CEC_NAMES = True
DEFAULT_ENABLE_PICTURE_CONTROLS = False
DEFAULT_ENABLE_SOUND_CONTROLS = False
DEFAULT_ENABLE_AUDIO_ONLY = False
DEFAULT_KEY_DELAY = 0.2
DEFAULT_KEY_REPEAT = 1
DEFAULT_AUTH_PROFILE = "auto"
DEFAULT_USE_SSL = True

CONF_PLAYBACK_DEBOUNCE = "playback_debounce"
DEFAULT_PLAYBACK_DEBOUNCE = 0.5

# Service Names & Attributes
SERVICE_SEND_KEY = "send_key"
SERVICE_SEND_KEY_SEQUENCE = "send_key_sequence"
SERVICE_CHANGE_CHANNEL = "change_channel"
SERVICE_LAUNCH_APP = "launch_app"
SERVICE_SET_PICTURE_SETTING = "set_picture_setting"
SERVICE_SET_SOUND_SETTING = "set_sound_setting"
SERVICE_SEND_TEXT_INPUT = "send_text_input"

ATTR_KEY = "key"
ATTR_REPEAT = "repeat"
ATTR_DELAY = "delay"
ATTR_SEQUENCE = "sequence"
ATTR_CHANNEL = "channel"
ATTR_CONFIRM = "confirm"
ATTR_APP = "app"
ATTR_APP_ID = "app_id"
ATTR_APP_NAME = "app_name"
ATTR_URL = "url"
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

from homeassistant.helpers import selector

AUTH_PROFILE_OPTIONS = [
    selector.SelectOptionDict(value="auto", label="Auto Detect (Recommended)"),
    selector.SelectOptionDict(value="modern", label="VIDAA 2.0 / 2024+ (vidaa_2024)"),
    selector.SelectOptionDict(value="middle", label="VIDAA 1.5 / Middle (3000–3285)"),
    selector.SelectOptionDict(value="remotenow", label="RemoteNOW / 2018–2023 (standard)"),
    selector.SelectOptionDict(value="legacy", label="Legacy Static (Pre-2022 / Static Credentials)"),
]

AUTH_PROFILE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=AUTH_PROFILE_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="auth_profile",
    )
)

BRAND_OPTIONS = [
    selector.SelectOptionDict(value="auto", label="Auto Detect (Recommended)"),
    selector.SelectOptionDict(value="his", label="Hisense"),
    selector.SelectOptionDict(value="tos", label="Toshiba"),
    selector.SelectOptionDict(value="loe", label="Loewe"),
    selector.SelectOptionDict(value="tpv", label="TPV / Philips / AOC"),
    selector.SelectOptionDict(value="shp", label="Sharp"),
    selector.SelectOptionDict(value="jvc", label="JVC"),
    selector.SelectOptionDict(value="sch", label="Schneider"),
    selector.SelectOptionDict(value="aka", label="Akai"),
    selector.SelectOptionDict(value="bek", label="Beko"),
    selector.SelectOptionDict(value="tel", label="Telefunken"),
    selector.SelectOptionDict(value="bus", label="Bush"),
    selector.SelectOptionDict(value="vic", label="Vizio"),
    selector.SelectOptionDict(value="phi", label="Philco"),
    selector.SelectOptionDict(value="nob", label="Noblex"),
    selector.SelectOptionDict(value="san", label="Sansei"),
    selector.SelectOptionDict(value="rca", label="RCA"),
    selector.SelectOptionDict(value="sin", label="Sinotec"),
    selector.SelectOptionDict(value="ves", label="Vestel"),
    selector.SelectOptionDict(value="bra", label="Brandt"),
    selector.SelectOptionDict(value="met", label="Metz"),
    selector.SelectOptionDict(value="lei", label="Leica"),
    selector.SelectOptionDict(value="tpo", label="TOPTRO"),
]

BRAND_PROFILES: dict[str, str] = {
    opt["value"]: opt["label"] for opt in BRAND_OPTIONS
}

BRAND_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=BRAND_OPTIONS,
        mode=selector.SelectSelectorMode.DROPDOWN,
        translation_key="brand",
    )
)

GENERIC_MANUFACTURERS: set[str] = {
    "",
    "smarttv",
    "smart tv",
    "smarttv.com",
    "http://www.smarttv.com",
    "https://www.smarttv.com",
    "unknown",
}

BRAND_MAP: dict[str, str] = {
    "his": "Hisense",
    "hisense": "Hisense",
    "tos": "Toshiba",
    "toshiba": "Toshiba",
    "loe": "Loewe",
    "loewe": "Loewe",
    "tpv": "TPV",
    "philips": "Philips",
    "aoc": "AOC",
    "shp": "Sharp",
    "sharp": "Sharp",
    "jvc": "JVC",
    "sch": "Schneider",
    "schneider": "Schneider",
    "aka": "Akai",
    "akai": "Akai",
    "bek": "Beko",
    "beko": "Beko",
    "tel": "Telefunken",
    "telefunken": "Telefunken",
    "bus": "Bush",
    "bush": "Bush",
    "vic": "Vizio",
    "vizio": "Vizio",
    "phi": "Philco",
    "philco": "Philco",
    "nob": "Noblex",
    "noblex": "Noblex",
    "san": "Sansei",
    "sansei": "Sansei",
    "ilo": "iLo",
    "pio": "Pioneer",
    "pioneer": "Pioneer",
    "sei": "Seiki",
    "seiki": "Seiki",
    "ton": "Tonomac",
    "tonomac": "Tonomac",
    "psc": "Panasonic",
    "panasonic": "Panasonic",
    "sma": "Smart",
    "qua": "Quantum",
    "quantum": "Quantum",
    "adi": "Admiral",
    "admiral": "Admiral",
    "rca": "RCA",
    "sin": "Sinotec",
    "sinotec": "Sinotec",
    "ves": "Vestel",
    "vestel": "Vestel",
    "bra": "Brandt",
    "brandt": "Brandt",
    "met": "Metz",
    "metz": "Metz",
    "lei": "Leica",
    "leica": "Leica",
    "tpo": "TOPTRO",
    "toptro": "TOPTRO",
}

BRAND_CODE_MAP: dict[str, str] = {
    "his": "his",
    "hisense": "his",
    "tos": "tos",
    "toshiba": "tos",
    "loe": "loe",
    "loewe": "loe",
    "tpv": "tpv",
    "philips": "tpv",
    "aoc": "tpv",
    "shp": "shp",
    "sharp": "shp",
    "jvc": "jvc",
    "sch": "sch",
    "schneider": "sch",
    "aka": "aka",
    "akai": "aka",
    "bek": "bek",
    "beko": "bek",
    "tel": "tel",
    "telefunken": "tel",
    "bus": "bus",
    "bush": "bus",
    "vic": "vic",
    "vizio": "vic",
    "phi": "phi",
    "philco": "phi",
    "nob": "nob",
    "noblex": "nob",
    "san": "san",
    "sansei": "san",
    "ilo": "ilo",
    "pio": "pio",
    "pioneer": "pio",
    "sei": "sei",
    "seiki": "sei",
    "ton": "ton",
    "tonomac": "ton",
    "psc": "psc",
    "panasonic": "psc",
    "sma": "sma",
    "qua": "qua",
    "quantum": "qua",
    "adi": "adi",
    "admiral": "adi",
    "rca": "rca",
    "sin": "sin",
    "sinotec": "sin",
    "ves": "ves",
    "vestel": "ves",
    "bra": "bra",
    "brandt": "bra",
    "met": "met",
    "metz": "met",
    "lei": "lei",
    "leica": "lei",
    "tpo": "tpo",
    "toptro": "tpo",
}
