"""Service schema definitions for Hisense VIDAA TV."""

from __future__ import annotations

import voluptuous as vol

from ..const import (
    ATTR_ACTION,
    ATTR_APP,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_CHANNEL,
    ATTR_CONFIRM,
    ATTR_DELAY,
    ATTR_KEY,
    ATTR_MENU_ID,
    ATTR_MENU_VALUE,
    ATTR_REPEAT,
    ATTR_SEQUENCE,
    ATTR_TEXT,
    ATTR_URL,
)
from .target import _target_selector_fields, _validate_launch_app_data

SERVICE_SEND_KEY_SCHEMA = vol.Schema({
    **_target_selector_fields(),
    vol.Required(ATTR_KEY): str,
    vol.Optional(ATTR_REPEAT, default=1): vol.Coerce(int),
    vol.Optional(ATTR_DELAY, default=0.2): vol.Coerce(float),
})

SERVICE_SEND_KEY_SEQUENCE_SCHEMA = vol.Schema({
    **_target_selector_fields(),
    vol.Required(ATTR_SEQUENCE): vol.Any([str], str),
    vol.Optional(ATTR_DELAY, default=0.3): vol.Coerce(float),
})

SERVICE_CHANGE_CHANNEL_SCHEMA = vol.Schema({
    **_target_selector_fields(),
    vol.Required(ATTR_CHANNEL): vol.Any(int, str),
    vol.Optional(ATTR_CONFIRM, default=True): vol.Coerce(bool),
    vol.Optional(ATTR_DELAY, default=0.25): vol.Coerce(float),
})

SERVICE_LAUNCH_APP_SCHEMA = vol.Schema(
    vol.All(
        {
            **_target_selector_fields(),
            vol.Optional(ATTR_APP): str,
            vol.Optional(ATTR_APP_ID): vol.Coerce(str),
            vol.Optional(ATTR_APP_NAME): str,
            vol.Optional(ATTR_URL): str,
        },
        _validate_launch_app_data,
    )
)

SERVICE_SET_PICTURE_SETTING_SCHEMA = vol.Schema({
    **_target_selector_fields(),
    vol.Required(ATTR_MENU_ID): vol.Coerce(int),
    vol.Required(ATTR_MENU_VALUE): vol.Coerce(str),
})

SERVICE_SET_SOUND_SETTING_SCHEMA = vol.Schema({
    **_target_selector_fields(),
    vol.Required(ATTR_MENU_ID): vol.Coerce(int),
    vol.Required(ATTR_MENU_VALUE): vol.Coerce(str),
})

SERVICE_SEND_TEXT_INPUT_SCHEMA = vol.Schema({
    **_target_selector_fields(),
    vol.Required(ATTR_TEXT): str,
    vol.Optional(ATTR_ACTION, default="insert"): str,
})
