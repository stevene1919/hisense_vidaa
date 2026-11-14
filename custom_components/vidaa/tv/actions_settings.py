"""TV picture and sound settings action mixin for Hisense VIDAA TV."""

from __future__ import annotations

from .settings import (
    async_get_picture_settings,
    async_get_sound_settings,
    async_set_backlight,
    async_set_brightness,
    async_set_contrast,
    async_set_picture_mode,
    async_set_picture_setting,
    async_set_sound_mode,
    async_set_sound_setting,
    get_picture_settings,
    get_sound_settings,
    set_backlight,
    set_brightness,
    set_contrast,
    set_picture_mode,
    set_picture_setting,
    set_sound_mode,
    set_sound_setting,
)


class TvSettingsActionsMixin:
    """Mixin delegating picture calibration and sound mode configuration to settings handlers."""

    def get_picture_settings(self) -> None:
        """Requests current picture settings menu information from the TV."""
        get_picture_settings(self)  # type: ignore[arg-type]

    async def async_get_picture_settings(self) -> None:
        """Requests current picture settings menu information from the TV asynchronously."""
        await async_get_picture_settings(self)  # type: ignore[arg-type]

    def set_picture_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific picture setting value."""
        set_picture_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    async def async_set_picture_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific picture setting value asynchronously."""
        await async_set_picture_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    def set_picture_mode(self, mode: str) -> None:
        """Sets the TV picture mode preset."""
        set_picture_mode(self, mode=mode)  # type: ignore[arg-type]

    async def async_set_picture_mode(self, mode: str) -> None:
        """Sets the TV picture mode preset asynchronously."""
        await async_set_picture_mode(self, mode=mode)  # type: ignore[arg-type]

    def set_backlight(self, level: int) -> None:
        """Sets the TV backlight level (0–100)."""
        set_backlight(self, level=level)  # type: ignore[arg-type]

    async def async_set_backlight(self, level: int) -> None:
        """Sets the TV backlight level (0–100) asynchronously."""
        await async_set_backlight(self, level=level)  # type: ignore[arg-type]

    def set_brightness(self, level: int) -> None:
        """Sets the TV brightness level (0–100)."""
        set_brightness(self, level=level)  # type: ignore[arg-type]

    async def async_set_brightness(self, level: int) -> None:
        """Sets the TV brightness level (0–100) asynchronously."""
        await async_set_brightness(self, level=level)  # type: ignore[arg-type]

    def set_contrast(self, level: int) -> None:
        """Sets the TV contrast level (0–100)."""
        set_contrast(self, level=level)  # type: ignore[arg-type]

    async def async_set_contrast(self, level: int) -> None:
        """Sets the TV contrast level (0–100) asynchronously."""
        await async_set_contrast(self, level=level)  # type: ignore[arg-type]

    def get_sound_settings(self) -> None:
        """Requests current sound settings menu information from the TV."""
        get_sound_settings(self)  # type: ignore[arg-type]

    async def async_get_sound_settings(self) -> None:
        """Requests current sound settings menu information from the TV asynchronously."""
        await async_get_sound_settings(self)  # type: ignore[arg-type]

    def set_sound_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific sound setting value."""
        set_sound_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    async def async_set_sound_setting(self, menu_id: int, menu_value: str | int | float) -> None:
        """Changes a specific sound setting value asynchronously."""
        await async_set_sound_setting(self, menu_id=menu_id, menu_value=menu_value)  # type: ignore[arg-type]

    def set_sound_mode(self, mode: str) -> None:
        """Sets the TV sound mode preset."""
        set_sound_mode(self, mode=mode)  # type: ignore[arg-type]

    async def async_set_sound_mode(self, mode: str) -> None:
        """Sets the TV sound mode preset asynchronously."""
        await async_set_sound_mode(self, mode=mode)  # type: ignore[arg-type]
