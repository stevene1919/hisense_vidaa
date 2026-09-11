"""Tests for Hisense VIDAA repairs platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hisense_vidaa.repairs import (
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

    flow = CertificateMissingRepairFlow()
    flow.hass = hass

    result = await flow.async_step_confirm(user_input={})
    assert result["type"] == "create_entry"
