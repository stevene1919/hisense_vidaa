"""Feature probing, diagnostics collection, and report formatting for Hisense VIDAA TV."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from ..crypto import resolve_ca_certificate, resolve_certificates
    from ..discovery import get_arp_mac
    from ..protocol.auth import probe_tv_auth_methods
    from .settings import SettingMenuItem
except (ImportError, ValueError):
    from crypto import resolve_ca_certificate, resolve_certificates
    from discovery import get_arp_mac
    from protocol.auth import probe_tv_auth_methods
    from tv.settings import SettingMenuItem

_LOGGER = logging.getLogger(__name__)

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


@dataclass
class FeatureProbeResult:
    """Dataclass holding all discovered TV feature capabilities and live state."""

    connected: bool = False
    state: dict[str, Any] = field(default_factory=dict)
    volume: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    apps: list[dict[str, Any]] = field(default_factory=list)
    picture_settings: list[SettingMenuItem] = field(default_factory=list)
    sound_settings: list[SettingMenuItem] = field(default_factory=list)
    raw_payloads: dict[str, Any] = field(default_factory=dict)


def load_credentials_file(file_path: str = "credentials.json") -> dict[str, Any]:
    """Load credentials JSON dictionary from disk."""
    if os.path.isfile(file_path):
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.warning("Could not read credentials file %s: %s", file_path, e)
    return {}


def save_credentials_file(file_path: str, creds: dict[str, Any]) -> None:
    """Save credentials dictionary to disk."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=4)


def create_client_from_creds(
    creds: dict[str, Any],
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    auth_profile: str = "auto",
) -> Any:
    """Create a configured HisenseTvClient from credentials."""
    try:
        from ..client import HisenseTvClient
    except (ImportError, ValueError):
        from client import HisenseTvClient  # type: ignore

    resolved_cert, resolved_key = resolve_certificates(certfile, keyfile)
    resolved_ca = resolve_ca_certificate(ca_cert)

    return HisenseTvClient(
        ip=creds.get("ip_address"),
        mac=creds.get("mac_address"),
        client_id=creds.get("client_id"),
        username=creds.get("username"),
        password=creds.get("password"),
        access_token=creds.get("accesstoken") or creds.get("access_token"),
        access_token_time=int(creds.get("accesstoken_time") or creds.get("access_token_time", 0)),
        access_token_duration=int(creds.get("accesstoken_duration_day") or creds.get("access_token_duration", 2)),
        refresh_token=creds.get("refreshtoken") or creds.get("refresh_token"),
        refresh_token_time=int(creds.get("refreshtoken_time") or creds.get("refresh_token_time", 0)),
        refresh_token_duration=int(creds.get("refreshtoken_duration_day") or creds.get("refresh_token_duration", 30)),
        certfile=resolved_cert,
        keyfile=resolved_key,
        ca_cert=resolved_ca,
        verify_ssl=verify_ssl,
        auth_profile=auth_profile,
    )


def probe_tv_features(
    client: Any,
    wait_time: float = 2.5,
) -> FeatureProbeResult:
    """Connect to TV, query menu trees, sources, apps, and return probe results."""
    result = FeatureProbeResult()

    def on_state(d: dict[str, Any]) -> None:
        result.state = d

    def on_volume(d: dict[str, Any]) -> None:
        result.volume = d

    def on_sources(d: list[dict[str, Any]]) -> None:
        result.sources = d

    def on_apps(d: list[dict[str, Any]]) -> None:
        result.apps = d

    def on_picture(d: dict[str, Any]) -> None:
        result.picture_settings = getattr(client, "picture_settings", [])
        result.raw_payloads["picturesetting"] = d

    def on_sound(d: dict[str, Any]) -> None:
        result.sound_settings = getattr(client, "sound_settings", [])
        result.raw_payloads["soundsetting"] = d

    if hasattr(client, "register_state_callback"):
        client.register_state_callback(on_state)
        client.register_volume_callback(on_volume)
        client.register_sourcelist_callback(on_sources)
        client.register_applist_callback(on_apps)
        client.register_picture_callback(on_picture)
        client.register_sound_callback(on_sound)

    was_connected = getattr(client, "connected", False)
    if not was_connected:
        client.connect_and_run()
        for _ in range(30):
            if client.connected:
                break
            time.sleep(0.1)

    result.connected = bool(getattr(client, "connected", False))
    if not client.connected:
        return result

    client.query_initial_state()
    time.sleep(0.5)
    if hasattr(client, "get_picture_settings"):
        client.get_picture_settings()
    if hasattr(client, "get_sound_settings"):
        client.get_sound_settings()
    time.sleep(wait_time)

    result.picture_settings = getattr(client, "picture_settings", [])
    result.sound_settings = getattr(client, "sound_settings", [])
    result.apps = getattr(client, "apps", [])
    result.sources = getattr(client, "sources", [])

    if not was_connected:
        client.disconnect()

    return result


def generate_markdown_report(
    ip: str,
    ping_result: dict[str, Any],
    probe_result: FeatureProbeResult | None = None,
    mac: str | None = None,
    version: str = "Unknown",
) -> str:
    """Generate a GitHub Issue compatible Markdown report."""
    dev = ping_result.get("device_info") or {}
    auth_probe = ping_result.get("auth_probe") or {}
    arp_mac = mac or get_arp_mac(ip)

    lines = []
    lines.append("### 📺 Hardware & System Information")
    model_str = dev.get("model_code") or dev.get("model_name") or dev.get("friendly_name") or "Unknown"
    mfg_str = dev.get("manufacturer") or dev.get("brand") or "Hisense"
    fv_str = dev.get("firmware_version") or "N/A"
    lines.append(f"- **TV Model:** {mfg_str} {model_str}")
    if dev.get("model_number"):
        lines.append(f"- **Model Number:** {dev['model_number']}")
    if dev.get("platform"):
        lines.append(
            f"- **VIDAA Platform Indicator:** Platform {dev['platform']} (Voice: {dev.get('voice', 'N/A')}, Transport: {dev.get('transport_protocol', 'N/A')})"
        )
    lines.append(f"- **Discovered Firmware Build:** {fv_str}")
    if arp_mac:
        lines.append(f"- **Discovered MAC (ARP):** `{arp_mac}`")
    if dev.get("mac_wifi"):
        lines.append(f"- **Wi-Fi MAC (UPnP):** `{dev['mac_wifi']}`")
    if dev.get("mac_ethernet"):
        lines.append(f"- **Ethernet MAC (UPnP):** `{dev['mac_ethernet']}`")

    lines.append("\n### 📡 Connectivity & TLS Status")
    tcp_status = "✅ OPEN" if ping_result.get("tcp_port_open") else "❌ CLOSED"
    tls_status = "✅ SUCCESS" if ping_result.get("tls_handshake") else "❌ FAILED"
    lines.append(f"- **Port 36669 (TCP):** {tcp_status}")
    lines.append(f"- **TLS Handshake:** {tls_status} ({ping_result.get('tls_version') or 'N/A'}, {ping_result.get('cipher') or 'N/A'})")

    lines.append("\n### 🔐 MQTT Authentication Capabilities")
    legacy = auth_probe.get("legacy_static", {})
    std = auth_probe.get("standard_dynamic", {})
    middle = auth_probe.get("middle_dynamic", {})
    modern = auth_probe.get("modern_dynamic", {})

    leg_str = "✅ ACCEPTED (rc=0)" if legacy.get("supported") else f"❌ REJECTED (rc={legacy.get('rc')})"
    std_str = "✅ ACCEPTED (rc=0)" if std.get("supported") else f"❌ REJECTED (rc={std.get('rc')})"
    mid_str = "✅ ACCEPTED (rc=0)" if middle.get("supported") else f"❌ REJECTED (rc={middle.get('rc')})"
    mod_str = "✅ ACCEPTED (rc=0)" if modern.get("supported") else f"❌ REJECTED (rc={modern.get('rc')})"

    lines.append(f"- **Legacy Static Auth (`hisenseservice`):** {leg_str}")
    lines.append(f"- **Standard Dynamic Auth (`his$<timestamp>`):** {std_str}")
    lines.append(f"- **Middle Dynamic Auth (`his$<timestamp ^ XOR>` / Standard Salt):** {mid_str}")
    lines.append(f"- **Modern Dynamic Auth (`his$<timestamp ^ XOR>` / Modern Salt):** {mod_str}")

    if not legacy.get("supported") and not std.get("supported") and not middle.get("supported") and not modern.get("supported"):
        lines.append(
            "\n> [!WARNING]\n"
            "> **All standard authentication profiles rejected (rc=5)**: The TV broker accepted the TLS handshake but rejected initial MQTT credentials. "
            "This typically indicates the TV is running a newer firmware generation (e.g. VIDAA U7+ / build Q0704+ / App v1.09+) with updated credential hashing or pairing handshakes."
        )

    if ping_result.get("mqtt_rc") is not None:
        stored_str = "✅ ACCEPTED (rc=0)" if ping_result.get("mqtt_connected") else f"❌ REJECTED (rc={ping_result.get('mqtt_rc')})"
        lines.append(f"- **Stored Credentials Auth:** {stored_str}")

    if probe_result and probe_result.connected:
        lines.append("\n### 🎛️ Feature & Control Capabilities")

        # Dynamic Picture / Sound Menu Controls
        lines.append("#### 🖼️ Dynamic Calibration & Menu Trees")
        if probe_result.picture_settings:
            lines.append("<details><summary><b>✅ Dynamic Picture Settings Discovered</b> (Click to expand)</summary>\n")
            for item in probe_result.picture_settings:
                opts = f" (Options: {', '.join(item.options)})" if item.options else ""
                val = f" [Current: {item.value}]" if item.value is not None else ""
                lines.append(f"- **{item.name}** (ID: `{item.menu_id}`){val}{opts}")
            lines.append("\n</details>")
        else:
            lines.append("- **Picture Settings:** ⚠️ Not exposed over MQTT (Firmware uses internal OSD; dynamic picture mode/sliders not instantiated)")

        if probe_result.sound_settings:
            lines.append("<details><summary><b>✅ Dynamic Sound Settings Discovered</b> (Click to expand)</summary>\n")
            for item in probe_result.sound_settings:
                opts = f" (Options: {', '.join(item.options)})" if item.options else ""
                val = f" [Current: {item.value}]" if item.value is not None else ""
                lines.append(f"- **{item.name}** (ID: `{item.menu_id}`){val}{opts}")
            lines.append("\n</details>")
        else:
            lines.append("- **Sound Settings:** ⚠️ Not exposed over MQTT (Firmware uses internal OSD; dynamic sound mode selects not instantiated)")

        # Interactive Media & App Controls
        lines.append("\n#### 🎮 Interactive Media & Navigation Controls")
        if probe_result.sources:
            lines.append(f"<details><summary><b>🔌 Controllable Input Sources ({len(probe_result.sources)})</b> (Click to expand)</summary>\n")
            for s in probe_result.sources:
                active = " [ACTIVE]" if s.get("is_signal") in ("1", 1, True) or s.get("is_active") else ""
                lines.append(f"- `{s.get('sourceid')}`: **{s.get('sourcename', 'Unknown')}**{active}")
            lines.append("\n</details>")
        else:
            lines.append("- **Input Sources:** 0 discovered")

        if probe_result.apps:
            lines.append(f"<details><summary><b>📱 Launchable Smart TV Apps ({len(probe_result.apps)})</b> (Click to expand)</summary>\n")
            for a in probe_result.apps:
                lines.append(f"- **{a.get('name') or a.get('appName', 'Unknown')}** (`appId`: `{a.get('appId')}`)")
            lines.append("\n</details>")
        else:
            lines.append("- **Installed Apps:** 0 discovered")

        # Telemetry & Diagnostic Sensors
        lines.append("\n#### 📊 Telemetry & Live State Sensors")
        lines.append("- `media_player.<tv>`: Power, Volume, Mute, Source Selection, Media Transport")
        lines.append("- `remote.<tv>`: Fast Direct Remote Key Commands (`KEY_POWER`, `KEY_HOME`, `KEY_BACK`, etc.)")
        lines.append("- `sensor.<tv>_active_source`: Live input tracking")
        lines.append("- `sensor.<tv>_active_app`: Live foreground app tracking")
        lines.append("- `select.<tv>_audio_output_mode`: TV Speakers / ARC / eARC routing")
        lines.append("- `sensor.<tv>_session_status`: Token session health & encryption status")
        lines.append("- `binary_sensor.<tv>_mqtt_connected`: Real-time broker connection status")

    lines.append("\n### 📦 Integration Environment")
    lines.append(f"- **Integration Version:** `{version}`")
    lines.append(f"- **Python Version:** `{sys.version.split()[0]}`")

    return "\n".join(lines)


format_probe_results_markdown = generate_markdown_report


def probe_tv_features_and_report(
    client: Any,
    ping_result: dict[str, Any],
    ip: str,
    mac: str | None = None,
    version: str = "Unknown",
    wait_time: float = 2.5,
) -> str:
    """Probes TV features and returns a formatted markdown report."""
    probe_res = probe_tv_features(client, wait_time=wait_time)
    return generate_markdown_report(
        ip=ip,
        ping_result=ping_result,
        probe_result=probe_res,
        mac=mac,
        version=version,
    )
