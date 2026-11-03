"""Tests for flow guards: abort flow, duplicate guards, and clean disconnects."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.config_flow import HisenseVidaaConfigFlow

PROBE_PATH = "custom_components.hisense_vidaa.config_flow.async_probe_pairing_challenge"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _static_client() -> HisenseTvClient:
    """A static-session (legacy) client with its topic paths defined."""
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="legacy")
    client.client_id = "hisenseservice"
    client.username = "hisenseservice"
    client.password = "multimqttservice"
    client.update_topic_paths()
    return client


def _hass() -> MagicMock:
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.data = {}
    return hass


def _flow(hass: MagicMock, *, profile: str = "legacy") -> HisenseVidaaConfigFlow:
    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.ip_address = "192.168.50.12"
    flow.mac_address = "e8:51:77:ec:98:1c"
    flow.auth_profile = profile
    flow.async_set_unique_id = AsyncMock(return_value=None)
    flow._abort_if_unique_id_configured = MagicMock()
    return flow


@pytest.fixture
def no_network_start_auth(monkeypatch):
    """Keep the flow's client construction offline."""
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.get_device_fingerprint",
        MagicMock(return_value={}),
    )


# ---------------------------------------------------------------------------
# F1-leg2: AbortFlow must escape the generic cannot_connect handlers
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_duplicate_tv_aborts_with_already_configured(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="legacy")
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_helpers.get_arp_mac",
        lambda host: "e8:51:77:ec:98:1c",
    )

    with pytest.raises(AbortFlow) as exc:
        await flow.async_step_user(
            user_input={"ip_address": "192.168.50.12", "auth_profile": "legacy"}
        )
    assert exc.value.reason == "already_configured"


@pytest.mark.anyio
async def test_discovery_confirm_does_not_swallow_abort_flow(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="legacy")
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

    with pytest.raises(AbortFlow):
        await flow.async_step_discovery_confirm(user_input={})


@pytest.mark.anyio
async def test_certs_step_does_not_swallow_abort_flow(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="modern")
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_certs.check_certs_exist", lambda c, k: True
    )

    with pytest.raises(AbortFlow):
        await flow.async_step_certs(user_input={"use_ssl": False, "certfile": "", "keyfile": ""})


# ---------------------------------------------------------------------------
# F2-leg2: duplicate guard before disconnect; sibling scoping
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_duplicate_add_keeps_running_client_connected():
    hass = _hass()
    running = MagicMock()
    running.ip = "192.168.50.12"
    running.mac = "e8:51:77:ec:98:1c"
    hass.data = {"hisense_vidaa": {"entry_1": {"client": running}}}

    flow = _flow(hass)
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

    with pytest.raises(AbortFlow):
        await flow._async_init_client_and_auth()

    assert not running.disconnect.called and not running.async_disconnect.called


@pytest.mark.anyio
async def test_reauth_disconnects_only_its_own_client():
    hass = _hass()
    own = MagicMock()
    own.ip = "192.168.50.12"
    own.mac = "e8:51:77:ec:98:1c"
    own.async_disconnect = AsyncMock()
    sibling = MagicMock()
    sibling.ip = "192.168.50.12"  # same IP, different entry
    sibling.mac = "e8:51:77:ec:98:1d"
    sibling.async_disconnect = AsyncMock()
    hass.data = {"hisense_vidaa": {"entry_1": {"client": own}, "entry_2": {"client": sibling}}}

    flow = _flow(hass)
    flow._reauth_entry = MagicMock()
    flow._reauth_entry.entry_id = "entry_1"

    await flow._async_disconnect_existing_client()

    assert own.async_disconnect.called
    assert not sibling.async_disconnect.called


# ---------------------------------------------------------------------------
# F10-leg6: async_remove keeps and logs the background task future
# ---------------------------------------------------------------------------
def test_async_remove_registers_done_callback():
    flow = HisenseVidaaConfigFlow()
    fut = MagicMock()
    fut.cancelled.return_value = False
    fut.exception.return_value = RuntimeError("disconnect failed")
    hass = MagicMock()
    hass.async_create_background_task = MagicMock(return_value=fut)
    flow.hass = hass
    flow.client = MagicMock()

    flow.async_remove()

    assert fut.add_done_callback.called
    callback = fut.add_done_callback.call_args[0][0]
    callback(fut)  # must log and not raise


