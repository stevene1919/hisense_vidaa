import asyncio
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    AUTH_PROFILE_SELECTOR,
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_ENABLE_AUDIO_ONLY,
    CONF_ENABLE_CEC_NAMES,
    CONF_ENABLE_MEDIA_CONTROLS,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_ENABLE_SOUND_CONTROLS,
    CONF_ENABLE_WOL,
    CONF_INCLUDE_APPS_IN_SOURCES,
    CONF_KEY_DELAY,
    CONF_KEY_REPEAT,
    CONF_KEYFILE,
    CONF_PLAYBACK_DEBOUNCE,
    CONF_REFRESH_IN_STANDBY,
    CONF_SECONDARY_MAC_ADDRESS,
    CONF_USE_SSL,
    DEFAULT_AUTH_PROFILE,
    DEFAULT_ENABLE_AUDIO_ONLY,
    DEFAULT_ENABLE_CEC_NAMES,
    DEFAULT_ENABLE_MEDIA_CONTROLS,
    DEFAULT_ENABLE_NOTIFY,
    DEFAULT_ENABLE_PICTURE_CONTROLS,
    DEFAULT_ENABLE_REMOTE,
    DEFAULT_ENABLE_SOUND_CONTROLS,
    DEFAULT_ENABLE_WOL,
    DEFAULT_INCLUDE_APPS_IN_SOURCES,
    DEFAULT_KEY_DELAY,
    DEFAULT_KEY_REPEAT,
    DEFAULT_PLAYBACK_DEBOUNCE,
    DEFAULT_REFRESH_IN_STANDBY,
    DEFAULT_USE_SSL,
)
from .crypto import check_certs_exist


class HisenseVidaaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle categorized Hisense VIDAA options with intuitive menu navigation."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Present categorized options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "power_network",
                "playback_sources",
                "features_remote",
                "security",
            ],
        )

    async def async_step_power_network(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Power, Wake-on-LAN and network options."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="power_network",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_ENABLE_WOL,
                    default=options.get(CONF_ENABLE_WOL, DEFAULT_ENABLE_WOL),
                ): bool,
                vol.Optional(
                    CONF_SECONDARY_MAC_ADDRESS,
                    default=options.get(CONF_SECONDARY_MAC_ADDRESS, ""),
                ): str,
                vol.Optional(
                    CONF_REFRESH_IN_STANDBY,
                    default=options.get(CONF_REFRESH_IN_STANDBY, DEFAULT_REFRESH_IN_STANDBY),
                ): bool,
            }),
        )

    async def async_step_playback_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Input sources and media playback options."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="playback_sources",
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
                vol.Optional(
                    CONF_PLAYBACK_DEBOUNCE,
                    default=options.get(
                        CONF_PLAYBACK_DEBOUNCE,
                        DEFAULT_PLAYBACK_DEBOUNCE,
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0,
                        max=5.0,
                        step=0.05,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
            }),
        )

    async def async_step_features_remote(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Entities, device features, and remote timing controls."""
        if user_input is not None:
            updated_options = {**self.config_entry.options, **user_input}
            return self.async_create_entry(title="", data=updated_options)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="features_remote",
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
                    CONF_ENABLE_PICTURE_CONTROLS,
                    default=options.get(
                        CONF_ENABLE_PICTURE_CONTROLS,
                        DEFAULT_ENABLE_PICTURE_CONTROLS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_SOUND_CONTROLS,
                    default=options.get(
                        CONF_ENABLE_SOUND_CONTROLS,
                        DEFAULT_ENABLE_SOUND_CONTROLS,
                    ),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_AUDIO_ONLY,
                    default=options.get(
                        CONF_ENABLE_AUDIO_ONLY,
                        DEFAULT_ENABLE_AUDIO_ONLY,
                    ),
                ): bool,
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

    async def async_step_security(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """SSL / TLS encryption, auth profile, and client certificate paths."""
        errors: dict[str, str] = {}
        options = self.config_entry.options
        data = self.config_entry.data

        current_profile = options.get(
            CONF_AUTH_PROFILE, data.get(CONF_AUTH_PROFILE, DEFAULT_AUTH_PROFILE)
        )
        current_use_ssl = options.get(
            CONF_USE_SSL, data.get(CONF_USE_SSL, DEFAULT_USE_SSL)
        )
        current_cert = options.get(CONF_CERTFILE, data.get(CONF_CERTFILE, ""))
        current_key = options.get(CONF_KEYFILE, data.get(CONF_KEYFILE, ""))

        if user_input is not None:
            new_cert = (user_input.get(CONF_CERTFILE) or "").strip()
            new_key = (user_input.get(CONF_KEYFILE) or "").strip()

            if new_cert or new_key:
                async def _check_exist(c: str | None, k: str | None) -> bool:
                    if hasattr(self, "hass") and self.hass:
                        return await self.hass.async_add_executor_job(check_certs_exist, c, k)
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(None, check_certs_exist, c, k)

                certs_exist = await _check_exist(new_cert, new_key)
                if not certs_exist:
                    cert_exists = await _check_exist(new_cert, new_cert) if new_cert else False
                    key_exists = await _check_exist(new_key, new_key) if new_key else False

                    if new_cert and not cert_exists:
                        errors[CONF_CERTFILE] = "certs_not_found"
                    elif new_key and not key_exists:
                        errors[CONF_KEYFILE] = "certs_not_found"
                    else:
                        errors["base"] = "certs_not_found"

            if not errors:
                updated_options = {**self.config_entry.options, **user_input}
                return self.async_create_entry(title="", data=updated_options)

        return self.async_show_form(
            step_id="security",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_AUTH_PROFILE,
                    default=current_profile,
                ): AUTH_PROFILE_SELECTOR,
                vol.Optional(
                    CONF_USE_SSL,
                    default=current_use_ssl,
                ): bool,
                vol.Optional(
                    CONF_CERTFILE,
                    default=current_cert,
                ): str,
                vol.Optional(
                    CONF_KEYFILE,
                    default=current_key,
                ): str,
            }),
            errors=errors,
        )

    # --------------------------------------------------------------------------
    # Backward compatibility aliases
    # --------------------------------------------------------------------------
    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Backward-compatible alias for power_network."""
        return await self.async_step_power_network(user_input)

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Backward-compatible alias for playback_sources."""
        return await self.async_step_playback_sources(user_input)

    async def async_step_picture_sound(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Backward-compatible alias for features_remote."""
        return await self.async_step_features_remote(user_input)

    async def async_step_remote_keys(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Backward-compatible alias for features_remote."""
        return await self.async_step_features_remote(user_input)

    async def async_step_certs(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Backward-compatible alias for security."""
        return await self.async_step_security(user_input)
