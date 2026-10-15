"""Tests for Hisense VIDAA config flow and auto-discovery."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from custom_components.hisense_vidaa.config_flow import HisenseVidaaConfigFlow
from custom_components.hisense_vidaa.const import (
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SW_VERSION,
    CONF_USE_SSL,
    DOMAIN,
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
    assert "power_network" in result["menu_options"]
    assert "playback_sources" in result["menu_options"]
    assert "features_remote" in result["menu_options"]
    assert "security" in result["menu_options"]

    # Test power_network step form and submission
    result_pwr_form = await handler.async_step_power_network()
    assert result_pwr_form["type"] == "form"
    assert result_pwr_form["step_id"] == "power_network"

    result_pwr_submit = await handler.async_step_power_network(
        user_input={
            "enable_wol": True,
            "secondary_mac_address": "AA:BB:CC:DD:EE:FF",
            "refresh_in_standby": True,
        }
    )
    assert result_pwr_submit["type"] == "create_entry"
    assert result_pwr_submit["data"]["enable_wol"] is True
    assert result_pwr_submit["data"]["secondary_mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert result_pwr_submit["data"]["refresh_in_standby"] is True

    # Test playback_sources step form and submission (including debounce)
    result_src_form = await handler.async_step_playback_sources()
    assert result_src_form["type"] == "form"
    assert result_src_form["step_id"] == "playback_sources"

    result_src_submit = await handler.async_step_playback_sources(
        user_input={
            "include_apps_in_sources": True,
            "enable_media_controls": True,
            "enable_cec_names": True,
            "playback_debounce": 0.5,
        }
    )
    assert result_src_submit["type"] == "create_entry"
    assert result_src_submit["data"]["enable_cec_names"] is True
    assert result_src_submit["data"]["playback_debounce"] == 0.5

    # Test features_remote step form and submission
    result_feat_form = await handler.async_step_features_remote()
    assert result_feat_form["type"] == "form"
    assert result_feat_form["step_id"] == "features_remote"

    result_feat_submit = await handler.async_step_features_remote(
        user_input={
            "enable_remote": False,
            "enable_notify": True,
            "enable_picture_controls": True,
            "enable_sound_controls": True,
            "enable_audio_only": True,
            "key_delay": 0.3,
            "key_repeat": 2,
        }
    )
    assert result_feat_submit["type"] == "create_entry"
    assert result_feat_submit["data"]["enable_remote"] is False
    assert result_feat_submit["data"]["enable_notify"] is True
    assert result_feat_submit["data"]["enable_picture_controls"] is True
    assert result_feat_submit["data"]["enable_sound_controls"] is True
    assert result_feat_submit["data"]["enable_audio_only"] is True
    assert result_feat_submit["data"]["key_delay"] == 0.3
    assert result_feat_submit["data"]["key_repeat"] == 2

    # Test security step with invalid non-existent paths
    result_sec_form = await handler.async_step_security()
    assert result_sec_form["type"] == "form"
    assert result_sec_form["step_id"] == "security"

    result_sec_invalid = await handler.async_step_security(
        user_input={
            "auth_profile": "auto",
            "use_ssl": True,
            "certfile": "/nonexistent/path/custom.crt",
            "keyfile": "/nonexistent/path/custom.key",
        }
    )
    assert result_sec_invalid["type"] == "form"
    assert result_sec_invalid["errors"]["certfile"] == "certs_not_found"

    # Test security step updating auth profile without custom paths
    result_profile_submit = await handler.async_step_security(
        user_input={
            "auth_profile": "middle",
            "use_ssl": True,
            "certfile": "",
            "keyfile": "",
        }
    )
    assert result_profile_submit["type"] == "create_entry"
    assert result_profile_submit["data"]["auth_profile"] == "middle"

    # Test security step with valid paths (monkeypatched check_certs_exist)
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.options_flow.check_certs_exist",
        lambda c, k: True,
    )
    result_sec_submit = await handler.async_step_security(
        user_input={
            "auth_profile": "modern",
            "use_ssl": True,
            "certfile": "/config/certs/custom.crt",
            "keyfile": "/config/certs/custom.key",
        }
    )
    assert result_sec_submit["type"] == "create_entry"
    assert result_sec_submit["data"]["certfile"] == "/config/certs/custom.crt"
    assert result_sec_submit["data"]["auth_profile"] == "modern"

    # Test backward-compatible alias methods
    alias_gen = await handler.async_step_general()
    assert alias_gen["step_id"] == "power_network"
    alias_src = await handler.async_step_sources()
    assert alias_src["step_id"] == "playback_sources"
    alias_ps = await handler.async_step_picture_sound()
    assert alias_ps["step_id"] == "features_remote"
    alias_keys = await handler.async_step_remote_keys()
    assert alias_keys["step_id"] == "features_remote"
    alias_certs = await handler.async_step_certs()
    assert alias_certs["step_id"] == "security"


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
    mock_entry.unique_id = "e8:51:77:ec:98:1c"
    mock_entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        "auth_profile": "legacy",
    }
    hass.config_entries.async_get_entry = MagicMock(return_value=mock_entry)
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": "test_entry_reconf"}

    # Regression: reconfigure must skip the duplicate-entry guard against its own
    # entry (real HA aborts with "Flow aborted: already_configured" otherwise).
    flow.async_set_unique_id = AsyncMock(return_value=None)
    flow._abort_if_unique_id_configured = MagicMock()

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )
    # Legacy/reconfigure now probes the static session for a PIN challenge;
    # return "no challenge" so the flow takes the unchanged no-PIN path.
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.config_flow.async_probe_pairing_challenge",
        AsyncMock(return_value=False),
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
    assert flow.async_set_unique_id.called is False
    assert flow._abort_if_unique_id_configured.called is False


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


@pytest.mark.anyio
async def test_finish_reauth_without_client():
    """Test _async_finish_reauth works when client is already None."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock(return_value=True)

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_456"
    mock_entry.data = {CONF_IP_ADDRESS: "192.168.50.12"}
    flow._reauth_entry = mock_entry
    flow.client = None

    result = await flow._async_finish_reauth(reason="reauth_successful")
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_reload.called


# ---------------------------------------------------------------------------
# HA-surface fix leg: F3-leg2 (reauth transport settings), F4-leg2/F5-leg6
# (issue lifecycle), F7-leg6 (reconfigure duplicate guard).
# ---------------------------------------------------------------------------


def _reauth_flow(hass, entry, entry_id):
    """Build a config flow wired up for a reauth/reconfigure of `entry`."""
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    hass.config_entries.async_entries = MagicMock(return_value=[entry])
    hass.config_entries.async_update_entry = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": entry_id}
    return flow


@pytest.mark.anyio
async def test_reauth_keeps_entry_transport_settings(monkeypatch):
    """[F3-leg2] a legacy (non-TLS) entry must stay use_ssl=False through reauth."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock()
    entry.entry_id = "legacy_entry"
    entry.unique_id = "e8:51:77:ec:98:1c"
    entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_AUTH_PROFILE: "legacy",
        CONF_USE_SSL: False,
    }
    flow = _reauth_flow(hass, entry, "legacy_entry")
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )

    await flow.async_step_reauth(entry.data)
    assert flow.use_ssl is False
    assert flow.certfile is None

    result = await flow.async_step_reauth_confirm(user_input={})
    assert result["reason"] == "reauth_successful"

    written = hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert written[CONF_USE_SSL] is False
    assert written[CONF_IP_ADDRESS] == "192.168.50.12"


@pytest.mark.anyio
async def test_reauth_seeds_certificates_from_entry(monkeypatch):
    """[F3-leg2] reauth must reuse the entry's cert/key paths, not flow defaults."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock()
    entry.entry_id = "tls_entry"
    entry.unique_id = "e8:51:77:ec:98:1c"
    entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_AUTH_PROFILE: "modern",
        CONF_USE_SSL: True,
        CONF_CERTFILE: "/config/ssl/hisense.crt",
        CONF_KEYFILE: "/config/ssl/hisense.key",
    }
    flow = _reauth_flow(hass, entry, "tls_entry")
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )

    await flow.async_step_reauth(entry.data)
    assert flow.use_ssl is True
    assert flow.certfile == "/config/ssl/hisense.crt"
    assert flow.keyfile == "/config/ssl/hisense.key"

    await flow.async_step_reauth_confirm(user_input={})
    flow.client.access_token = "fresh_access_token"
    await flow._async_finish_reauth(reason="reauth_successful")

    written = hass.config_entries.async_update_entry.call_args.kwargs["data"]
    assert written[CONF_USE_SSL] is True
    assert written[CONF_CERTFILE] == "/config/ssl/hisense.crt"
    assert written[CONF_KEYFILE] == "/config/ssl/hisense.key"


@pytest.mark.anyio
async def test_reauth_success_deletes_auth_token_issue(monkeypatch):
    """[F4-leg2/F5-leg6] a successful reauth must delete the persistent issue."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock()
    entry.entry_id = "issue_entry"
    entry.data = {CONF_IP_ADDRESS: "192.168.50.12"}
    flow = _reauth_flow(hass, entry, "issue_entry")
    flow._reauth_entry = entry

    deleted = []
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_reauth.ir.async_delete_issue",
        lambda hass_arg, domain, issue_id: deleted.append((domain, issue_id)),
    )

    await flow._async_finish_reauth(reason="reauth_successful")

    assert deleted == [(DOMAIN, "auth_token_invalidated_issue_entry")]


@pytest.mark.anyio
async def test_reconfigure_aborts_when_new_ip_belongs_to_another_tv(monkeypatch):
    """[F7-leg6] reconfigure must not repoint an entry at another configured TV."""
    hass = MagicMock(spec=HomeAssistant)
    own_entry = MagicMock()
    own_entry.entry_id = "own_entry"
    own_entry.unique_id = "e8:51:77:ec:98:1c"
    own_entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_AUTH_PROFILE: "legacy",
    }
    other_entry = MagicMock()
    other_entry.entry_id = "other_entry"
    other_entry.unique_id = "e8:51:77:ec:98:2d"

    flow = _reauth_flow(hass, own_entry, "own_entry")
    hass.config_entries.async_entries = MagicMock(return_value=[own_entry, other_entry])
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_reauth.async_resolve_mac",
        AsyncMock(return_value="e8:51:77:ec:98:2d"),
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_reauth.ReauthFlowMixin._async_finish_reauth",
        AsyncMock(return_value={"type": "abort", "reason": "reconfigure_successful"}),
    )

    result = await flow.async_step_reconfigure(
        user_input={CONF_IP_ADDRESS: "192.168.50.15", CONF_AUTH_PROFILE: "legacy"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert flow._async_finish_reauth.await_count == 0
    assert hass.config_entries.async_update_entry.called is False


@pytest.mark.anyio
async def test_reauth_confirm_disconnects_existing_running_client_before_start_auth(monkeypatch):
    """Test reauth_confirm disconnects running client to prevent MQTT client ID collisions."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_AUTH_PROFILE: "auto",
        CONF_USE_SSL: True,
    }

    running_client = MagicMock()
    running_client.ip = "192.168.50.12"
    running_client.mac = "e8:51:77:ec:98:1c"
    hass.data = {DOMAIN: {"test_entry": {"client": running_client}}}

    flow = _reauth_flow(hass, entry, "test_entry")
    flow.ip_address = "192.168.50.12"
    flow.mac_address = "e8:51:77:ec:98:1c"
    flow.auth_profile = "auto"
    flow.use_ssl = True

    events = []
    running_client.disconnect = MagicMock(side_effect=lambda: events.append("disconnect_existing"))

    async def mock_start_auth(self):
        events.append("start_auth")

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        mock_start_auth,
    )

    result = await flow.async_step_reauth_confirm(user_input={})
    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert events == ["disconnect_existing", "start_auth"]





