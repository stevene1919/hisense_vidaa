"""Backward-compatible re-exports for probe module.

Logic has moved to `features.probe`.
"""

from __future__ import annotations

try:
    from .features.probe import (
        FeatureProbeResult,
        create_client_from_creds,
        format_probe_results_markdown,
        generate_markdown_report,
        load_credentials_file,
        probe_tv_auth_methods,
        probe_tv_features,
        probe_tv_features_and_report,
        save_credentials_file,
    )
except (ImportError, ValueError):
    from features.probe import (
        FeatureProbeResult,
        create_client_from_creds,
        format_probe_results_markdown,
        generate_markdown_report,
        load_credentials_file,
        probe_tv_auth_methods,
        probe_tv_features,
        probe_tv_features_and_report,
        save_credentials_file,
    )

__all__ = [
    "FeatureProbeResult",
    "create_client_from_creds",
    "format_probe_results_markdown",
    "generate_markdown_report",
    "load_credentials_file",
    "probe_tv_auth_methods",
    "probe_tv_features",
    "probe_tv_features_and_report",
    "save_credentials_file",
]
