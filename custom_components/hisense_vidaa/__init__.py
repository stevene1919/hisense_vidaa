"""Shim for hisense_vidaa -> vidaa migration."""

from __future__ import annotations

from custom_components.vidaa import (
    async_migrate_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)

__all__ = [
    "async_migrate_entry",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]
