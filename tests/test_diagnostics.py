"""Tests for Hisense VIDAA diagnostics platform."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.const import DOMAIN
from custom_components.hisense_vidaa.diagnostics import async_get_config_entry_diagnostics


@pytest.mark.anyio
async def test_diagnostics_redaction():
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.version = 1
    entry.title = "Living Room TV"
    entry.data = {
        "ip_address": "192.168.50.12",
        "mac_address": "e8:51:77:ec:98:1c",
        "auth_profile": "modern",
        "password": "supersecretpassword",
        "access_token": "secret_access_token_12345",
        "refresh_token": "secret_refresh_token_67890",
    }
    entry.options = {"enable_remote": True, "enable_wol": True}

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.current_source = "HDMI 1"
    mock_client.current_app = "Netflix"
    mock_client.volume = 20
    mock_client.muted = False
    mock_client.state = "on"
    mock_client.client_id = "hisense_client_1"
    mock_client.auth_profile = "modern"
    mock_client.access_token_time = 1700000000
    mock_client.access_token_duration = 3600
    mock_client.refresh_token_time = 1700000000
    mock_client.refresh_token_duration = 86400
    mock_client.get_device_fingerprint.return_value = {
        "model_name": "65U7G",
        "manufacturer": "Hisense",
        "firmware_version": "V0000.01.00a.N0120",
    }

    hass.data = {
        DOMAIN: {
            "test_entry_id": {
                "client": mock_client
            }
        }
    }
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry"]["title"] == "Living Room TV"
    assert diag["entry"]["data"]["password"] == "**REDACTED**"
    assert diag["entry"]["data"]["access_token"] == "**REDACTED**"
    assert diag["entry"]["data"]["refresh_token"] == "**REDACTED**"
    assert diag["entry"]["data"]["ip_address"] == "192.168.50.12"

    assert diag["client"]["connected"] is True
    assert diag["client"]["source"] == "HDMI 1"
    assert diag["client"]["current_app"] == "Netflix"
    assert diag["device_fingerprint"]["model_name"] == "65U7G"


# ---------------------------------------------------------------------------
# HA-surface fix leg: F6-leg2/F1-leg6 (crash on unloaded entries) and
# F12-leg2/F8-leg6 (fingerprint + MAC-derived topic leaks).
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_diagnostics_for_unloaded_entry_does_not_raise():
    """[F6-leg2/F1-leg6] an entry absent from hass.data must still produce diagnostics."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "not_loaded_entry"
    entry.domain = DOMAIN
    entry.version = 1
    entry.title = "Living Room TV"
    entry.data = {}
    entry.options = {}
    hass.data = {DOMAIN: {}}

    diag = await async_get_config_entry_diagnostics(hass, entry)

    assert diag["entry"]["title"] == "Living Room TV"
    assert diag["client"] is None
    assert diag["device_fingerprint"] is None


@pytest.mark.anyio
async def test_diagnostics_redacts_fingerprint_and_topic_client_id():
    """[F12-leg2/F8-leg6] MAC/serial values and MAC-derived topics must never leak."""
    mac = "e8:51:77:ec:98:1c"
    client_id = "e85177ec981c"
    serial = "SN-9471-ABCD"

    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "tls_entry"
    entry.domain = DOMAIN
    entry.version = 1
    entry.title = "Living Room TV"
    entry.data = {"ip_address": "192.168.50.12"}
    entry.options = {}

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.auth_profile = "modern"
    mock_client.current_source = "HDMI 1"
    mock_client.current_app = "Netflix"
    mock_client.volume = 20
    mock_client.muted = False
    mock_client.state = "on"
    mock_client.access_token_time = 1700000000
    mock_client.access_token_duration = 3600
    mock_client.refresh_token = "secret_refresh_token"
    mock_client.refresh_token_duration = 86400
    mock_client.topicTVUIBasepath = f"ui_service/{client_id}/"
    mock_client.topicTVPSBasepath = f"platform_service/{client_id}/"
    mock_client.topicMobiBasepath = f"mobile/{client_id}/"
    mock_client.get_device_fingerprint.return_value = {
        "model_name": "65U7G",
        "mac_wifi": mac,
        "mac_ethernet": mac,
        "serial_number": serial,
    }

    hass.data = {DOMAIN: {entry.entry_id: {"client": mock_client}}}
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    diag = await async_get_config_entry_diagnostics(hass, entry)

    payload = json.dumps(diag)
    assert mac not in payload
    assert serial not in payload
    assert client_id not in payload

    assert diag["device_fingerprint"]["mac_wifi"] == "**REDACTED**"
    assert diag["device_fingerprint"]["mac_ethernet"] == "**REDACTED**"
    assert diag["device_fingerprint"]["serial_number"] == "**REDACTED**"
    assert diag["client"]["topic_tv_ui"] == "**REDACTED**"
    assert diag["client"]["topic_tv_ps"] == "**REDACTED**"
    assert diag["client"]["topic_mobile"] == "**REDACTED**"
    # non-sensitive device info is still reported
    assert diag["device_fingerprint"]["model_name"] == "65U7G"

