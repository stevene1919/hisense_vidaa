"""Tests for Hisense VIDAA config flow and auto-discovery."""

import asyncio
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
async def test_options_flow(monkeypatch):
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
    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert "general" in result["menu_options"]
    assert "sources" in result["menu_options"]
    assert "picture_sound" in result["menu_options"]
    assert "remote_keys" in result["menu_options"]
    assert "certs" in result["menu_options"]

    # Test general step form and submission
    result_gen_form = await handler.async_step_general()
    assert result_gen_form["type"] == "form"
    assert result_gen_form["step_id"] == "general"

    result_gen_submit = await handler.async_step_general(
        user_input={
            "enable_remote": False,
            "enable_wol": True,
            "secondary_mac_address": "AA:BB:CC:DD:EE:FF",
            "use_ssl": True,
        }
    )
    assert result_gen_submit["type"] == "create_entry"
    assert result_gen_submit["data"]["enable_remote"] is False
    assert result_gen_submit["data"]["secondary_mac_address"] == "AA:BB:CC:DD:EE:FF"

    # Test sources step
    result_src_submit = await handler.async_step_sources(
        user_input={
            "include_apps_in_sources": True,
            "enable_media_controls": True,
            "enable_cec_names": True,
        }
    )
    assert result_src_submit["type"] == "create_entry"
    assert result_src_submit["data"]["enable_cec_names"] is True

    # Test picture_sound step
    result_ps_form = await handler.async_step_picture_sound()
    assert result_ps_form["type"] == "form"
    assert result_ps_form["step_id"] == "picture_sound"

    result_ps_submit = await handler.async_step_picture_sound(
        user_input={
            "enable_picture_controls": True,
            "enable_sound_controls": True,
            "enable_audio_only": True,
        }
    )
    assert result_ps_submit["type"] == "create_entry"
    assert result_ps_submit["data"]["enable_picture_controls"] is True
    assert result_ps_submit["data"]["enable_sound_controls"] is True
    assert result_ps_submit["data"]["enable_audio_only"] is True

    # Test remote_keys step
    result_keys_submit = await handler.async_step_remote_keys(
        user_input={
            "key_delay": 0.3,
            "key_repeat": 2,
        }
    )
    assert result_keys_submit["type"] == "create_entry"
    assert result_keys_submit["data"]["key_delay"] == 0.3
    assert result_keys_submit["data"]["key_repeat"] == 2

    # Test certs step with invalid non-existent paths
    result_certs_invalid = await handler.async_step_certs(
        user_input={
            "auth_profile": "auto",
            "certfile": "/nonexistent/path/custom.crt",
            "keyfile": "/nonexistent/path/custom.key",
        }
    )
    assert result_certs_invalid["type"] == "form"
    assert result_certs_invalid["errors"]["certfile"] == "certs_not_found"

    # Test certs step updating auth profile without custom paths
    result_profile_submit = await handler.async_step_certs(
        user_input={
            "auth_profile": "middle",
            "certfile": "",
            "keyfile": "",
        }
    )
    assert result_profile_submit["type"] == "create_entry"
    assert result_profile_submit["data"]["auth_profile"] == "middle"

    # Test certs step with valid paths (monkeypatched check_certs_exist)
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.options_flow.check_certs_exist",
        lambda c, k: True,
    )
    result_certs_submit = await handler.async_step_certs(
        user_input={
            "auth_profile": "modern",
            "certfile": "/config/certs/custom.crt",
            "keyfile": "/config/certs/custom.key",
        }
    )
    assert result_certs_submit["type"] == "create_entry"
    assert result_certs_submit["data"]["certfile"] == "/config/certs/custom.crt"
    assert result_certs_submit["data"]["auth_profile"] == "modern"


@pytest.mark.anyio
async def test_reauth_flow_success(monkeypatch):
    """Test reauth flow prompts confirmation, triggers client auth, submits PIN, and updates entry."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_reauth"
    mock_entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        "auth_profile": "modern",
    }
    hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": "test_entry_reauth"}

    # Start reauth
    result_init = await flow.async_step_reauth(mock_entry.data)
    assert result_init["type"] == "form"
    assert result_init["step_id"] == "reauth_confirm"

    # Confirm reauth
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )
    result_confirm = await flow.async_step_reauth_confirm(user_input={})
    assert result_confirm["type"] == "form"
    assert result_confirm["step_id"] == "auth"

    # Submit PIN
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_submit_pin",
        AsyncMock(return_value=None),
    )
    flow.client.access_token = "new_access_token"
    flow.client.refresh_token = "new_refresh_token"

    result_auth = await flow.async_step_auth(user_input={"pin_code": "1234"})
    assert result_auth["type"] == "abort"
    assert result_auth["reason"] == "reauth_successful"
    assert hass.config_entries.async_update_entry.called
    assert hass.config_entries.async_reload.called


@pytest.mark.anyio
async def test_reconfigure_flow_success(monkeypatch):
    """Test reconfigure flow updates IP/profile and re-pairs or updates entry."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_reconf"
    mock_entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        "auth_profile": "legacy",
    }
    hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": "test_entry_reconf"}

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )

    result_reconf = await flow.async_step_reconfigure(
        user_input={
            CONF_IP_ADDRESS: "192.168.50.15",
            "auth_profile": "legacy",
        }
    )
    assert result_reconf["type"] == "abort"
    assert result_reconf["reason"] == "reconfigure_successful"
    assert hass.config_entries.async_update_entry.called


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
        "custom_components.hisense_vidaa.config_flow.get_arp_mac",
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
    tasks = []

    def mock_create_task(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    hass.async_create_task = MagicMock(side_effect=mock_create_task)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    mock_client = MagicMock()
    flow.client = mock_client

    flow.async_remove()
    if tasks:
        await asyncio.gather(*tasks)
    assert mock_client.disconnect.called
    assert flow.client is None



@pytest.mark.anyio
async def test_finish_reauth_disconnects_client():
    """Test _async_finish_reauth disconnects client before reloading entry."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock(return_value=True)

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_123"
    mock_entry.data = {CONF_IP_ADDRESS: "192.168.50.12"}
    flow._reauth_entry = mock_entry

    mock_client = MagicMock()
    mock_client.client_id = "reauth_client_id"
    mock_client.username = "hisense"
    mock_client.password = "pass"
    mock_client.access_token = "token_reauth"
    mock_client.access_token_time = 1700000000
    mock_client.access_token_duration = 3600
    mock_client.refresh_token = "reftoken_reauth"
    mock_client.refresh_token_time = 1700000000
    mock_client.refresh_token_duration = 86400
    flow.client = mock_client
    flow.ip_address = "192.168.50.12"

    result = await flow._async_finish_reauth(reason="reauth_successful")
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert mock_client.disconnect.called
    assert flow.client is None
    assert hass.config_entries.async_reload.called


