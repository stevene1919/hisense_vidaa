"""App matching, input source switching, and navigation helpers for Hisense VIDAA TV."""

from __future__ import annotations

import logging
import re
from typing import Any

try:
    from .const import KEY_ALIASES
except ImportError:
    from const import KEY_ALIASES

_LOGGER = logging.getLogger(__name__)


def normalize_string(s: str) -> str:
    """Normalizes a string by stripping non-alphanumeric characters and lowercasing."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def match_app(
    apps: list[dict[str, Any]],
    target: str,
) -> dict[str, str] | None:
    """Matches a target app string against a list of installed apps.

    Returns a dict with 'appId', 'name', 'url' if matched, or None.
    """
    if not target or not apps:
        return None

    clean_target = target.strip().lower()
    norm_target = normalize_string(target)

    # 1. Exact match on name or ID
    for app in apps:
        if isinstance(app, dict):
            aname = str(app.get("name") or app.get("appName") or "").strip().lower()
            aid = str(app.get("appId") or app.get("id") or "").strip().lower()
            if clean_target in (aname, aid):
                return {
                    "appId": str(app.get("appId") or app.get("id") or ""),
                    "name": str(app.get("name") or app.get("appName") or target),
                    "url": str(app.get("url") or app.get("appUrl") or ""),
                }

    # 2. Normalized alphanumeric match
    for app in apps:
        if isinstance(app, dict):
            aname = str(app.get("name") or app.get("appName") or "")
            aid = str(app.get("appId") or app.get("id") or "")
            if norm_target and (norm_target == normalize_string(aname) or norm_target == normalize_string(aid)):
                return {
                    "appId": str(app.get("appId") or app.get("id") or ""),
                    "name": aname or target,
                    "url": str(app.get("url") or app.get("appUrl") or ""),
                }

    # 3. Substring match
    for app in apps:
        if isinstance(app, dict):
            aname = str(app.get("name") or app.get("appName") or "").lower()
            if clean_target in aname or (norm_target and norm_target in normalize_string(aname)):
                return {
                    "appId": str(app.get("appId") or app.get("id") or ""),
                    "name": str(app.get("name") or app.get("appName") or target),
                    "url": str(app.get("url") or app.get("appUrl") or ""),
                }

    return None


def resolve_source(
    sources: list[dict[str, Any]],
    target: str,
) -> tuple[str, str | None]:
    """Resolves target source name or ID against list of available sources.

    Returns (source_id, source_name).
    """
    if not target:
        return "", None

    clean = target.strip().lower()
    if sources:
        for src in sources:
            if isinstance(src, dict):
                sname = str(src.get("sourcename") or "").strip()
                dname = str(src.get("displayname") or "").strip()
                sid = str(src.get("sourceid") or "").strip()
                if clean in (sname.lower(), dname.lower(), sid.lower()):
                    return sid or sname, sname or dname or sid

    return target.strip(), None


def get_next_cycled_source(
    sources: list[dict[str, Any]],
    current_source: str | None,
) -> tuple[str, str] | None:
    """Calculates the next source in the cycle order based on current source.

    Returns (source_id, source_name) or None if no valid sources.
    """
    if not sources:
        return None

    valid_sources = [
        s
        for s in sources
        if isinstance(s, dict)
        and (s.get("sourceid") is not None or s.get("sourcename") is not None)
    ]
    if not valid_sources:
        return None

    curr_clean = str(current_source or "").strip().lower()
    curr_idx = -1
    for idx, src in enumerate(valid_sources):
        sname = str(src.get("sourcename") or "").strip().lower()
        dname = str(src.get("displayname") or "").strip().lower()
        sid = str(src.get("sourceid") or "").strip().lower()
        if curr_clean and (curr_clean in (sname, dname, sid)):
            curr_idx = idx
            break

    next_idx = (curr_idx + 1) % len(valid_sources)
    next_source = valid_sources[next_idx]
    sid = str(next_source.get("sourceid") or next_source.get("sourcename") or "")
    sname = str(next_source.get("sourcename") or next_source.get("displayname") or sid)
    return sid, sname


def resolve_command_key(command: str) -> str:
    """Resolves command string or alias to TV remote key code."""
    cmd_clean = command.strip().lower()
    return KEY_ALIASES.get(cmd_clean, command.strip().upper())
