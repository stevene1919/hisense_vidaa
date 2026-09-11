"""Tests for Hisense VIDAA config flow and auto-discovery."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from custom_components.hisense_vidaa.config_flow import HisenseVidaaConfigFlow
from custom_components.hisense_vidaa.const import (
    CONF_IP_ADDRESS,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
)


@pytest.mark.anyio
async def test_ssdp_discovery_vidaa_tv(monkeypatch):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    # Mock set_unique_id and abort checks
    flow.async_set_unique_id = AsyncMock(return_value=None)
    flow._abort_if_unique_id_configured = MagicMock()

    discovery_info = SsdpServiceInfo(
        ssdp_usn="uuid:12345678-1234-5678-1234-567812345678::urn:schemas-upnp-org:device:MediaRenderer:1",
        ssdp_st="urn:schemas-upnp-org:device:MediaRenderer:1",
        ssdp_location="http://192.168.50.12:38400/MediaServer/rendererdevicedesc.xml",
        ssdp_headers={"_host": "192.168.50.12"},
        upnp={
            "friendlyName": "Living Room TV",
            "manufacturer": "Hisense",
            "modelName": "65U7G",
            "modelDescription": "vidaa_support=1\nbrand=his\nmacWifi=e8:51:77:ec:98:1c\n",
        },
    )

    result = await flow.async_step_ssdp(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_confirm"
    assert flow.ip_address == "192.168.50.12"
    assert flow.mac_address == "e8:51:77:ec:98:1c"
    assert flow.model == "65U7G"
    assert flow.manufacturer == "Hisense"


@pytest.mark.anyio
async def test_ssdp_discovery_non_vidaa_ignored():
    hass = MagicMock(spec=HomeAssistant)
    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = SsdpServiceInfo(
        ssdp_usn="uuid:sonos-1234::urn:schemas-upnp-org:device:MediaRenderer:1",
        ssdp_st="urn:schemas-upnp-org:device:MediaRenderer:1",
        ssdp_location="http://192.168.50.99:1400/xml/device_description.xml",
        ssdp_headers={"_host": "192.168.50.99"},
        upnp={
            "friendlyName": "Sonos Speaker",
            "manufacturer": "Sonos",
            "modelName": "Play:1",
            "modelDescription": "Sonos Smart Speaker",
        },
    )

    result = await flow.async_step_ssdp(discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "not_vidaa_tv"


@pytest.mark.anyio
async def test_options_step_creates_entry():
    hass = MagicMock(spec=HomeAssistant)
    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    flow.ip_address = "192.168.50.12"
    flow.mac_address = "e8:51:77:ec:98:1c"
    flow.discovered_title = "Hisense TV"
    flow.model = "65U7G"
    flow.manufacturer = "Hisense"
    flow.sw_version = "V1.0"

    mock_client = MagicMock()
    mock_client.client_id = "test_client_id"
    mock_client.username = "hisense"
    mock_client.password = "pass"
    mock_client.access_token = "token123"
    mock_client.access_token_time = 1700000000
    mock_client.access_token_duration = 3600
    mock_client.refresh_token = "reftoken123"
    mock_client.refresh_token_time = 1700000000
    mock_client.refresh_token_duration = 86400
    flow.client = mock_client

    result = await flow.async_step_options(
        user_input={"enable_remote": True, "enable_wol": True, "include_apps_in_sources": True}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Hisense TV"
    assert result["data"][CONF_IP_ADDRESS] == "192.168.50.12"
    assert result["data"][CONF_MAC_ADDRESS] == "e8:51:77:ec:98:1c"
    assert result["data"][CONF_MODEL] == "65U7G"
    assert result["data"][CONF_MANUFACTURER] == "Hisense"
    assert result["data"][CONF_SW_VERSION] == "V1.0"
    assert result["options"]["enable_remote"] is True


@pytest.mark.anyio
async def test_user_step_auto_certs_missing_routes_to_certs(monkeypatch):
    """When certificates are not present on disk, auto profile routes to certs step."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.config_flow.check_certs_exist",
        lambda c, k: False,
    )

    result = await flow.async_step_user(
        user_input={"ip_address": "192.168.50.12", "auth_profile": "auto"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "certs"


@pytest.mark.anyio
async def test_user_step_explicit_model_routes_to_certs():
    """When an explicit model profile is selected, it routes to certs step."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_user(
        user_input={"ip_address": "192.168.50.12", "auth_profile": "modern"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "certs"


@pytest.mark.anyio
async def test_certs_step_submission_valid(monkeypatch):
    """Submitting valid cert paths connects and transitions to auth step."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.ip_address = "192.168.50.12"
    flow.auth_profile = "modern"
    flow.async_set_unique_id = AsyncMock(return_value=None)
    flow._abort_if_unique_id_configured = MagicMock()

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.config_flow.check_certs_exist",
        lambda c, k: True,
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )

    result = await flow.async_step_certs(
        user_input={
            "use_ssl": True,
            "certfile": "/config/certs/vidaa_2024_cert.pem",
            "keyfile": "/config/certs/vidaa_2024_key.pem",
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "auth"


@pytest.mark.anyio
async def test_options_flow():
    """Test options flow handler."""
    from custom_components.hisense_vidaa.options_flow import HisenseVidaaOptionsFlowHandler

    config_entry = MagicMock()
    config_entry.options = {
        "enable_remote": True,
        "enable_wol": True,
        "include_apps_in_sources": True,
        "use_ssl": True,
        "certfile": "/config/certs/hisense.crt",
        "keyfile": "/config/certs/hisense.key",
    }
    config_entry.data = {}

    handler = HisenseVidaaOptionsFlowHandler()
    handler.config_entry = config_entry

    result = await handler.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result_submit = await handler.async_step_init(
        user_input={
            "enable_remote": False,
            "enable_wol": True,
            "include_apps_in_sources": True,
            "use_ssl": True,
            "certfile": "/config/certs/custom.crt",
            "keyfile": "/config/certs/custom.key",
        }
    )
    assert result_submit["type"] == "create_entry"
    assert result_submit["data"]["enable_remote"] is False
    assert result_submit["data"]["certfile"] == "/config/certs/custom.crt"
