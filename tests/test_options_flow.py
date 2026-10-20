"""Unit tests for the options flow handler."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hisense_vidaa.options_flow import HisenseVidaaOptionsFlowHandler


@pytest.mark.anyio
async def test_options_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test options flow handler menu, forms, and updates."""
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
