"""Backward-compatible re-exports for navigation module.

Logic has moved to `features.navigation`.
"""

from __future__ import annotations

try:
    from .features.navigation import (
        KEY_ALIASES,
        change_source_by_name_or_id,
        cycle_tv_source,
        get_next_cycled_source,
        launch_app_by_name,
        match_app,
        normalize_string,
        resolve_command_key,
        resolve_source,
    )
except (ImportError, ValueError):
    from features.navigation import (
        KEY_ALIASES,
        change_source_by_name_or_id,
        cycle_tv_source,
        get_next_cycled_source,
        launch_app_by_name,
        match_app,
        normalize_string,
        resolve_command_key,
        resolve_source,
    )

__all__ = [
    "KEY_ALIASES",
    "change_source_by_name_or_id",
    "cycle_tv_source",
    "get_next_cycled_source",
    "launch_app_by_name",
    "match_app",
    "normalize_string",
    "resolve_command_key",
    "resolve_source",
]
