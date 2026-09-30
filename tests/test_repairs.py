"""Tests for Hisense VIDAA repairs platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.repairs import (
    AuthTokenInvalidatedRepairFlow,
    CertificateMissingRepairFlow,
    async_create_fix_flow,
)


@pytest.mark.anyio
async def test_repairs_flow_creation():
    hass = MagicMock(spec=HomeAssistant)
    flow = await async_create_fix_flow(hass, "certificate_missing_1234", None)
    assert isinstance(flow, CertificateMissingRepairFlow)


@pytest.mark.anyio
async def test_repairs_flow_confirm_missing_certs(monkeypatch):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.repairs.resolve_certificates",
        lambda: (None, None),
    )

    flow = CertificateMissingRepairFlow()
    flow.hass = hass

    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == "form"
    assert result["errors"] == {"base": "certificates_still_missing"}


@pytest.mark.anyio
async def test_repairs_flow_confirm_certs_found(monkeypatch):
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.repairs.resolve_certificates",
        lambda: ("/path/to/cert.pem", "/path/to/key.pem"),
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.repairs.check_certs_exist",
        lambda c, k: True,
    )

    flow = CertificateMissingRepairFlow()
    flow.hass = hass

    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == "create_entry"


# ---------------------------------------------------------------------------
# Fix 3: AuthTokenInvalidatedRepairFlow tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_creation():
    """async_create_fix_flow must return AuthTokenInvalidatedRepairFlow for the new issue type."""
    hass = MagicMock(spec=HomeAssistant)
    flow = await async_create_fix_flow(hass, "auth_token_invalidated_abc123", None)
    assert isinstance(flow, AuthTokenInvalidatedRepairFlow)


@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_shows_form_on_first_call():
    """Confirm step must show a form when no user_input is provided yet."""
    flow = AuthTokenInvalidatedRepairFlow()
    flow.hass = MagicMock(spec=HomeAssistant)

    result = await flow.async_step_confirm(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"


@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_creates_entry_on_submit():
    """Confirm step must create entry (complete the flow) when user submits."""
    flow = AuthTokenInvalidatedRepairFlow()
    flow.hass = MagicMock(spec=HomeAssistant)

    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == "create_entry"


@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_init_delegates_to_confirm():
    """async_step_init must delegate to async_step_confirm."""
    flow = AuthTokenInvalidatedRepairFlow()
    flow.hass = MagicMock(spec=HomeAssistant)

    # init with no input → shows form
    result = await flow.async_step_init(user_input=None)
    assert result["type"] == "form"

    # init with input → completes
    result = await flow.async_step_init(user_input={})
    assert result["type"] == "create_entry"


# ---------------------------------------------------------------------------
# HA-surface fix leg: F5-leg2 / F6-leg6 - the fix flow must actually start the
# reauth flow instead of only dismissing the issue.
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_starts_reauth():
    """[F5-leg2/F6-leg6] submitting the fix flow must start the entry's reauth flow."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock()
    entry.entry_id = "abc123"
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    flow = await async_create_fix_flow(
        hass, "auth_token_invalidated_abc123", {"entry_id": "abc123"}
    )
    flow.hass = hass

    result = await flow.async_step_confirm(user_input={})

    assert result["type"] == "create_entry"
    hass.config_entries.async_get_entry.assert_called_once_with("abc123")
    entry.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_recovers_entry_from_issue_id():
    """[F5-leg2/F6-leg6] the entry id also comes from the issue id (no issue data)."""
    hass = MagicMock(spec=HomeAssistant)
    entry = MagicMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)

    flow = await async_create_fix_flow(hass, "auth_token_invalidated_entry_9", None)
    flow.hass = hass

    await flow.async_step_confirm(user_input={})

    hass.config_entries.async_get_entry.assert_called_once_with("entry_9")
    entry.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.anyio
async def test_auth_token_invalidated_repair_flow_without_entry_does_not_raise():
    """[F5-leg2/F6-leg6] a stale issue pointing at a gone entry must not break the flow."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries.async_get_entry = MagicMock(return_value=None)

    flow = AuthTokenInvalidatedRepairFlow(entry_id="gone")
    flow.hass = hass

    result = await flow.async_step_confirm(user_input={})

    assert result["type"] == "create_entry"
