from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_CERTFILE,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_KEYFILE,
    CONF_USE_SSL,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_USE_SSL,
)


class HisenseVidaaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Hisense VIDAA options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_ENABLE_REMOTE,
                    default=options.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_WOL,
                    default=options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_APPS_IN_SOURCES,
                    default=options.get(
                        CONF_INCLUDE_APPS_IN_SOURCES,
                        DEFAULT_INCLUDE_APPS_IN_SOURCES,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_MEDIA_CONTROLS,
                    default=options.get(
                        CONF_ENABLE_MEDIA_CONTROLS,
                        DEFAULT_ENABLE_MEDIA_CONTROLS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_USE_SSL,
                    default=options.get(
                        CONF_USE_SSL, data.get(CONF_USE_SSL, DEFAULT_USE_SSL)
                    ),
                ): bool,
                vol.Optional(
                    CONF_CERTFILE,
                    default=options.get(
                        CONF_CERTFILE, data.get(CONF_CERTFILE, "")
                    ),
                ): str,
                vol.Optional(
                    CONF_KEYFILE,
                    default=options.get(
                        CONF_KEYFILE, data.get(CONF_KEYFILE, "")
                    ),
                ): str,
            }),
        )
