from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_CERTFILE,
    CONF_ENABLE_CEC_NAMES,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_KEY_DELAY,
    CONF_KEY_REPEAT,
    CONF_KEYFILE,
    CONF_SECONDARY_MAC_ADDRESS,
    CONF_USE_SSL,
    DEFAULT_ENABLE_CEC_NAMES,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_NOTIFY,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_KEY_DELAY,
    DEFAULT_KEY_REPEAT,
    DEFAULT_USE_SSL,
)


class HisenseVidaaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle categorized Hisense VIDAA options with tabbed menu navigation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Present categorized options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "sources",
                "remote_keys",
                "certs",
            ],
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """General, Power & Network options."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options
        data = self.config_entry.data

        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_ENABLE_REMOTE,
                    default=options.get(CONF_ENABLE_REMOTE, DEFAULT_ENABLE_REMOTE),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_NOTIFY,
                    default=options.get(CONF_ENABLE_NOTIFY, DEFAULT_ENABLE_NOTIFY),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_WOL,
                    default=options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL),
                ): bool,
                vol.Optional(
                    CONF_SECONDARY_MAC_ADDRESS,
                    default=options.get(CONF_SECONDARY_MAC_ADDRESS, ""),
                ): str,
                vol.Optional(
                    CONF_USE_SSL,
                    default=options.get(
                        CONF_USE_SSL, data.get(CONF_USE_SSL, DEFAULT_USE_SSL)
                    ),
                ): bool,
            }),
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Input sources and media playback options."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="sources",
            data_schema=vol.Schema({
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
                    CONF_ENABLE_CEC_NAMES,
                    default=options.get(
                        CONF_ENABLE_CEC_NAMES,
                        DEFAULT_ENABLE_CEC_NAMES,
                    ),
                ): bool,
            }),
        )

    async def async_step_remote_keys(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remote control key timing and repeat options."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="remote_keys",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_KEY_DELAY,
                    default=options.get(CONF_KEY_DELAY, DEFAULT_KEY_DELAY),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.05,
                        max=2.0,
                        step=0.05,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional(
                    CONF_KEY_REPEAT,
                    default=options.get(CONF_KEY_REPEAT, DEFAULT_KEY_REPEAT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=10,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }),
        )

    async def async_step_certs(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """SSL / TLS client certificate configuration."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options
        data = self.config_entry.data

        return self.async_show_form(
            step_id="certs",
            data_schema=vol.Schema({
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
