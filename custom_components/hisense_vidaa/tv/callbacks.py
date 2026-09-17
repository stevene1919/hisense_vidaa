"""Callback registry and event dispatcher mixin for Hisense VIDAA TV client."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

try:
    from .state import (
        apply_device_info_update,
        apply_picture_update,
        apply_sound_update,
        apply_state_update,
        apply_volume_update,
    )
except (ImportError, ValueError):
    from tv.state import (
        apply_device_info_update,
        apply_picture_update,
        apply_sound_update,
        apply_state_update,
        apply_volume_update,
    )

_LOGGER = logging.getLogger(__name__)

__all__ = ["CallbackRegistryMixin"]


class CallbackRegistryMixin:
    """Mixin managing event subscription callbacks and dispatching for HisenseTvClient."""

    _callbacks: dict[str, list[Callable]]

    def _init_callbacks(self) -> None:
        """Initializes callback storage dictionary."""
        self._callbacks = defaultdict(list)

    def _register_callback(self, event: str, cb: Callable) -> None:
        if not hasattr(self, "_callbacks"):
            self._init_callbacks()
        if cb not in self._callbacks[event]:
            self._callbacks[event].append(cb)

    def _unregister_callback(self, event: str, cb: Callable) -> None:
        if hasattr(self, "_callbacks") and cb in self._callbacks[event]:
            self._callbacks[event].remove(cb)

    def _dispatch(self, event: str, *args: Any) -> None:
        if not hasattr(self, "_callbacks"):
            return
        for cb in list(self._callbacks[event]):
            try:
                cb(*args)
            except Exception as e:
                _LOGGER.error("Error in callback for %s: %s", event, e)

    def register_state_callback(self, cb: Callable) -> None:
        self._register_callback("state", cb)

    def unregister_state_callback(self, cb: Callable) -> None:
        self._unregister_callback("state", cb)

    def register_volume_callback(self, cb: Callable) -> None:
        self._register_callback("volume", cb)

    def unregister_volume_callback(self, cb: Callable) -> None:
        self._unregister_callback("volume", cb)

    def register_sourcelist_callback(self, cb: Callable) -> None:
        self._register_callback("sourcelist", cb)

    def unregister_sourcelist_callback(self, cb: Callable) -> None:
        self._unregister_callback("sourcelist", cb)

    def register_applist_callback(self, cb: Callable) -> None:
        self._register_callback("applist", cb)

    def unregister_applist_callback(self, cb: Callable) -> None:
        self._unregister_callback("applist", cb)

    def register_connected_callback(self, cb: Callable) -> None:
        self._register_callback("connected", cb)

    def unregister_connected_callback(self, cb: Callable) -> None:
        self._unregister_callback("connected", cb)

    def register_disconnected_callback(self, cb: Callable) -> None:
        self._register_callback("disconnected", cb)

    def unregister_disconnected_callback(self, cb: Callable) -> None:
        self._unregister_callback("disconnected", cb)

    def register_token_refreshed_callback(self, cb: Callable) -> None:
        self._register_callback("token_refreshed", cb)

    def unregister_token_refreshed_callback(self, cb: Callable) -> None:
        self._unregister_callback("token_refreshed", cb)

    def register_auth_failed_callback(self, cb: Callable) -> None:
        self._register_callback("auth_failed", cb)

    def unregister_auth_failed_callback(self, cb: Callable) -> None:
        self._unregister_callback("auth_failed", cb)

    def register_picture_callback(self, cb: Callable) -> None:
        self._register_callback("picture", cb)

    def unregister_picture_callback(self, cb: Callable) -> None:
        self._unregister_callback("picture", cb)

    def register_sound_callback(self, cb: Callable) -> None:
        self._register_callback("sound", cb)

    def unregister_sound_callback(self, cb: Callable) -> None:
        self._unregister_callback("sound", cb)

    def register_device_info_callback(self, cb: Callable) -> None:
        self._register_callback("device_info", cb)

    def unregister_device_info_callback(self, cb: Callable) -> None:
        self._unregister_callback("device_info", cb)

    def _dispatch_auth_failed(self) -> None:
        self._dispatch("auth_failed")

    def _dispatch_connected(self) -> None:
        self._dispatch("connected")

    def _dispatch_disconnected(self) -> None:
        self._dispatch("disconnected")

    def _dispatch_state_update(self, data: Any) -> None:
        apply_state_update(self, data)
        self._dispatch("state", data)

    def _dispatch_device_info_update(self, data: Any) -> None:
        apply_device_info_update(self, data)
        self._dispatch("device_info", data)

    def _dispatch_volume_update(self, data: Any) -> None:
        apply_volume_update(self, data)
        self._dispatch("volume", data)

    def _dispatch_sourcelist_update(self, data: Any) -> None:
        if isinstance(data, list):
            self.sources = data
        elif isinstance(data, dict) and "sourcelist" in data:
            self.sources = data["sourcelist"]
        self._dispatch("sourcelist", self.sources)

    def _dispatch_applist_update(self, data: Any) -> None:
        if isinstance(data, list):
            self.apps = data
        elif isinstance(data, dict) and "applist" in data:
            self.apps = data["applist"]
        self._dispatch("applist", self.apps)

    def _dispatch_picture_update(self, data: Any) -> None:
        apply_picture_update(self, data)
        self._dispatch("picture", data)

    def _dispatch_sound_update(self, data: Any) -> None:
        apply_sound_update(self, data)
        self._dispatch("sound", data)

    def _dispatch_token_refreshed(self) -> None:
        self._dispatch(
            "token_refreshed",
            {
                "access_token": self.access_token,
                "access_token_time": self.access_token_time,
                "access_token_duration": self.access_token_duration,
                "refresh_token": self.refresh_token,
                "refresh_token_time": self.refresh_token_time,
                "refresh_token_duration": self.refresh_token_duration,
            },
        )
