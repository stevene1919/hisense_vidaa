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
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
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
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
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
        user_input={
            "enable_remote": True,
            "enable_wol": True,
            "include_apps_in_sources": True,
            "enable_picture_controls": False,
            "enable_sound_controls": False,
            "enable_audio_only": False,
        }
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Hisense TV"
    assert result["data"][CONF_IP_ADDRESS] == "192.168.50.12"
    assert result["data"][CONF_MAC_ADDRESS] == "e8:51:77:ec:98:1c"
    assert result["data"][CONF_MODEL] == "65U7G"
    assert result["data"][CONF_MANUFACTURER] == "Hisense"
    assert result["data"][CONF_SW_VERSION] == "V1.0"
    assert result["options"]["enable_remote"] is True
    assert result["options"]["enable_picture_controls"] is False
    assert result["options"]["enable_sound_controls"] is False
    assert result["options"]["enable_audio_only"] is False
    assert mock_client.disconnect.called
    assert flow.client is None


@pytest.mark.anyio
async def test_capability_probing_in_config_flow(monkeypatch):
    """Test capability probing dynamically updates option defaults."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    flow.ip_address = "192.168.50.12"
    flow.mac_address = "e8:51:77:ec:98:1c"
    flow.discovered_title = "Hisense TV"

    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.picture_settings = {"91": MagicMock()}
    mock_client.sound_settings = {}
    mock_client.get_picture_settings = MagicMock()
    mock_client.get_sound_settings = MagicMock()
    flow.client = mock_client

    await flow._async_probe_device_capabilities()
    assert mock_client.get_picture_settings.called
    assert mock_client.get_sound_settings.called

    form_result = await flow.async_step_options()
    assert form_result["type"] == "form"
    assert form_result["step_id"] == "options"


@pytest.mark.anyio
async def test_user_step_auto_certs_missing_routes_to_certs(monkeypatch):
    """When certificates are not present on disk, auto profile routes to certs step."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.crypto.check_certs_exist",
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
        "custom_components.hisense_vidaa.crypto.check_certs_exist",
        lambda c, k: True,
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_certs.check_certs_exist",
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
async def test_zeroconf_discovery(monkeypatch):
    """Test mDNS / Zeroconf discovery handling."""
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.async_set_unique_id = AsyncMock(return_value=None)
    flow._abort_if_unique_id_configured = MagicMock()

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_helpers.get_arp_mac",
        lambda host: "e8:51:77:ec:98:1c",
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.discovery.get_arp_mac",
        lambda host: "e8:51:77:ec:98:1c",
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.tv.fingerprint.get_arp_mac",
        lambda host: "e8:51:77:ec:98:1c",
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.168.50.12",
        ip_addresses=["192.168.50.12"],
        port=36669,
        hostname="hisensetv.local.",
        type="_vidaa._tcp.local.",
        name="Living Room TV._vidaa._tcp.local.",
        properties={},
    )

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "discovery_confirm"
    assert flow.ip_address == "192.168.50.12"
    assert flow.mac_address == "e8:51:77:ec:98:1c"


@pytest.mark.anyio
async def test_config_flow_async_remove_cleans_up_client():
    """Test async_remove disconnects running flow client."""
    hass = MagicMock(spec=HomeAssistant)
    # async_add_executor_job schedules the callable and returns a future: the flow
    # must hand that future to HA directly — wrapping it in async_create_task()
    # raises TypeError("a coroutine was expected") on real Home Assistant.
    hass.async_add_executor_job = MagicMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    mock_client = MagicMock()
    flow.client = mock_client

    flow.async_remove()
    assert hass.async_add_executor_job.called
    assert mock_client.disconnect.called
    assert flow.client is None


@pytest.mark.anyio
async def test_config_flow_async_remove_noop_without_client():
    """Test async_remove executes cleanly when client is None."""
    flow = HisenseVidaaConfigFlow()
    flow.client = None
    flow.async_remove()
    assert flow.client is None


@pytest.mark.anyio
async def test_config_flow_async_remove_without_hass():
    """Test async_remove calls disconnect synchronously if hass is not set."""
    flow = HisenseVidaaConfigFlow()
    flow.hass = None
    mock_client = MagicMock()
    flow.client = mock_client

    flow.async_remove()
    assert mock_client.disconnect.called
    assert flow.client is None

