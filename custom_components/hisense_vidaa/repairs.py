"""Repairs implementation for Hisense VIDAA TV."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

from .crypto import resolve_certificates


class CertificateMissingRepairFlow(RepairsFlow):
    """Handler for certificate missing repair flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of the fix flow."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirmation step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                cert, key = await self.hass.async_add_executor_job(resolve_certificates)
                if cert and key:
                    return self.async_create_entry(data={})
            except Exception:
                pass
            errors["base"] = "certificates_still_missing"

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create a repair fix flow for the issue."""
    if issue_id.startswith("certificate_missing"):
        return CertificateMissingRepairFlow()
    return CertificateMissingRepairFlow()
