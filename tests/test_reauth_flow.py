"""Unit tests for the reauthentication and reconfiguration flow handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.config_flow import HisenseVidaaConfigFlow
from custom_components.hisense_vidaa.const import (
    CONF_AUTH_PROFILE,
    CONF_CERTFILE,
    CONF_IP_ADDRESS,
    CONF_KEYFILE,
    CONF_MAC_ADDRESS,
    CONF_USE_SSL,
    DOMAIN,
)


def _reauth_flow(hass: MagicMock, entry: MagicMock, entry_id: str) -> HisenseVidaaConfigFlow:
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
async def test_reauth_flow_success(monkeypatch: pytest.MonkeyPatch) -> None:
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
async def test_reconfigure_flow_success(monkeypatch: pytest.MonkeyPatch) -> None:
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

    # Regression: reconfigure must skip the duplicate-entry guard against its own entry.
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
async def test_finish_reauth_disconnects_client() -> None:
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
async def test_finish_reauth_without_client() -> None:
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


@pytest.mark.anyio
async def test_reauth_keeps_entry_transport_settings(monkeypatch: pytest.MonkeyPatch) -> None:
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
async def test_reauth_seeds_certificates_from_entry(monkeypatch: pytest.MonkeyPatch) -> None:
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
async def test_reauth_success_deletes_auth_token_issue(monkeypatch: pytest.MonkeyPatch) -> None:
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
async def test_reconfigure_aborts_when_new_ip_belongs_to_another_tv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
async def test_reauth_confirm_disconnects_existing_running_client_before_start_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
