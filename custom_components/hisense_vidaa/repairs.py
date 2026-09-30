"""Repairs implementation for Hisense VIDAA TV."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant

from .crypto import check_certs_exist, resolve_certificates


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
                if cert and key and check_certs_exist(cert, key):
                    return self.async_create_entry(data={})
            except Exception:
                pass
            errors["base"] = "certificates_still_missing"

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            errors=errors,
        )


class AuthTokenInvalidatedRepairFlow(RepairsFlow):
    """Repair flow shown when the TV broker has rejected all stored tokens.

    This happens when the TV invalidates its token store out-of-band, e.g.
    after a firmware update or a hard mains power-cycle.  The only recovery
    path is to re-run the pairing flow to obtain a fresh credential set.
    """

    def __init__(self, entry_id: str | None = None) -> None:
        """Initialize the flow with the config entry that needs re-pairing."""
        super().__init__()
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Prompt the user to reconfigure the integration."""
        if user_input is not None:
            # [F5-leg2/F6-leg6]: dismissing the card alone hides a still-broken
            # TV (the client stops dispatching auth_failed after the rejection),
            # so the advertised re-pairing must actually be started.
            entry = (
                self.hass.config_entries.async_get_entry(self._entry_id)
                if self._entry_id
                else None
            )
            if entry is not None:
                entry.async_start_reauth(self.hass)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


def _entry_id_for_issue(issue_id: str, data: dict[str, Any] | None) -> str | None:
    """Return the config entry id a persistent issue belongs to."""
    if isinstance(data, dict) and data.get("entry_id"):
        return str(data["entry_id"])
    prefix = "auth_token_invalidated_"
    if issue_id.startswith(prefix):
        return issue_id[len(prefix):] or None
    return None


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create a repair fix flow for the issue."""
    if issue_id.startswith("certificate_missing"):
        return CertificateMissingRepairFlow()
    if issue_id.startswith("auth_token_invalidated"):
        return AuthTokenInvalidatedRepairFlow(
            entry_id=_entry_id_for_issue(issue_id, data)
        )
    return CertificateMissingRepairFlow()

