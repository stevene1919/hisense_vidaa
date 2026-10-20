"""Callback registry and event dispatcher mixin for Hisense VIDAA TV client."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .state import (
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

    def _register_callback(self, event: str, callback: Callable) -> None:
        if not hasattr(self, "_callbacks"):
            self._init_callbacks()
        if callback not in self._callbacks[event]:
            self._callbacks[event].append(callback)

    def _unregister_callback(self, event: str, callback: Callable) -> None:
        if hasattr(self, "_callbacks") and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _dispatch(self, event: str, *args: Any) -> None:
        if not hasattr(self, "_callbacks"):
            return
        for callback in list(self._callbacks[event]):
            try:
                callback(*args)
            except Exception as error:
                _LOGGER.error("Error in callback for %s: %s", event, error)

    def register_state_callback(self, callback: Callable) -> None:
        self._register_callback("state", callback)

    def unregister_state_callback(self, callback: Callable) -> None:
        self._unregister_callback("state", callback)

    def register_volume_callback(self, callback: Callable) -> None:
        self._register_callback("volume", callback)

    def unregister_volume_callback(self, callback: Callable) -> None:
        self._unregister_callback("volume", callback)

    def register_sourcelist_callback(self, callback: Callable) -> None:
        self._register_callback("sourcelist", callback)

    def unregister_sourcelist_callback(self, callback: Callable) -> None:
        self._unregister_callback("sourcelist", callback)

    def register_applist_callback(self, callback: Callable) -> None:
        self._register_callback("applist", callback)

    def unregister_applist_callback(self, callback: Callable) -> None:
        self._unregister_callback("applist", callback)

    def register_connected_callback(self, callback: Callable) -> None:
        self._register_callback("connected", callback)

    def unregister_connected_callback(self, callback: Callable) -> None:
        self._unregister_callback("connected", callback)

    def register_disconnected_callback(self, callback: Callable) -> None:
        self._register_callback("disconnected", callback)

    def unregister_disconnected_callback(self, callback: Callable) -> None:
        self._unregister_callback("disconnected", callback)

    def register_token_refreshed_callback(self, callback: Callable) -> None:
        self._register_callback("token_refreshed", callback)

    def unregister_token_refreshed_callback(self, callback: Callable) -> None:
        self._unregister_callback("token_refreshed", callback)

    def register_auth_failed_callback(self, callback: Callable) -> None:
        self._register_callback("auth_failed", callback)

    def unregister_auth_failed_callback(self, callback: Callable) -> None:
        self._unregister_callback("auth_failed", callback)

    def register_picture_callback(self, callback: Callable) -> None:
        self._register_callback("picture", callback)

    def unregister_picture_callback(self, callback: Callable) -> None:
        self._unregister_callback("picture", callback)

    def register_sound_callback(self, callback: Callable) -> None:
        self._register_callback("sound", callback)

    def unregister_sound_callback(self, callback: Callable) -> None:
        self._unregister_callback("sound", callback)

    def register_device_info_callback(self, callback: Callable) -> None:
        self._register_callback("device_info", callback)

    def unregister_device_info_callback(self, callback: Callable) -> None:
        self._unregister_callback("device_info", callback)

    def register_clock_drift_callback(self, callback: Callable) -> None:
        self._register_callback("clock_drift", callback)

    def unregister_clock_drift_callback(self, callback: Callable) -> None:
        self._unregister_callback("clock_drift", callback)

    def _dispatch_clock_drift_update(self, offset: int) -> None:
        self._dispatch("clock_drift", offset)

    def _dispatch_auth_failed(self) -> None:
        self._dispatch("auth_failed", self)

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
        if isinstance(self.sources, list):
            for source in self.sources:
                if isinstance(source, dict) and (
                    source.get("is_signal") in ("1", 1, True)
                    or source.get("is_active")
                    or source.get("isactive")
                    or source.get("active")
                ):
                    src_name = (
                        source.get("sourcename")
                        or source.get("sourceName")
                        or source.get("displayname")
                        or source.get("name")
                    )
                    if src_name:
                        self.is_on = True
                        if not self.current_source:
                            self.current_source = src_name
                    break
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
        self._dispatch("token_refreshed", self)
