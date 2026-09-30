"""Tests for Hisense VIDAA config entry setup, unload, reauth callbacks, and options update filtering."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hisense_vidaa import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
    update_listener,
)
from custom_components.hisense_vidaa.const import (
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
)

ALL_SERVICES = [
    SERVICE_SEND_KEY,
    SERVICE_LAUNCH_APP,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
    SERVICE_SEND_TEXT_INPUT,
]


class FakeServices:
    """Minimal stand-in for hass.services that records register/unregister calls."""

    def __init__(self):
        self.registered = {}

    def has_service(self, domain, service):
        return (domain, service) in self.registered

    def async_register(self, domain, service, handler, **kwargs):
        self.registered[(domain, service)] = (handler, kwargs)

    def async_remove(self, domain, service):
        self.registered.pop((domain, service), None)


def _setup_hass(mock_entry, mock_client, monkeypatch):
    """Build a hass double that can run a full entry setup/unload cycle."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    hass.services = FakeServices()
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()
    mock_client.disconnect = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    mock_entry.options = {"enable_remote": True}
    return hass


@pytest.mark.anyio
async def test_services_are_registered_again_after_last_entry_is_reloaded(
    mock_entry, mock_client, monkeypatch
):
    """[F2-leg2/F2-leg4/F2-leg6] unloading the last entry unregisters the services; the next setup must restore them."""
    hass = _setup_hass(mock_entry, mock_client, monkeypatch)

    # 1. Entry setup registers every service (idempotent with async_setup)
    await async_setup_entry(hass, mock_entry)
    assert {service for _, service in hass.services.registered} == set(ALL_SERVICES)

    # 2. Removing the last entry tears the services down...
    assert await async_unload_entry(hass, mock_entry) is True
    assert hass.services.registered == {}

    # 3. ...so the next setup (an options-change reload) must register them again
    await async_setup_entry(hass, mock_entry)
    assert {service for _, service in hass.services.registered} == set(ALL_SERVICES)





@pytest.mark.anyio
async def test_entry_lifecycle_setup_and_unload(mock_entry, mock_client, monkeypatch):
    """Test that setting up and unloading an entry only unloads enabled platforms."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()
    mock_client.disconnect = MagicMock()

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    # 1. Setup entry with notify and picture_controls disabled
    mock_entry.options = {"enable_remote": True, "enable_notify": False}
    result = await async_setup_entry(hass, mock_entry)
    assert result is True

    # Forward entry setups should have received 7 platforms (excluding notify and number)
    expected_platforms = ["media_player", "sensor", "binary_sensor", "button", "switch", "select", "remote"]
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(mock_entry, expected_platforms)
    assert hass.data[DOMAIN][mock_entry.entry_id]["platforms"] == expected_platforms

    # 2. Unload entry
    unload_result = await async_unload_entry(hass, mock_entry)
    assert unload_result is True
    # Unload platforms must ONLY be called with the 7 loaded platforms, never all PLATFORMS
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(mock_entry, expected_platforms)
    mock_client.disconnect.assert_called_once()
    assert mock_entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.anyio
async def test_entry_auth_failed_callback_creates_repair_issue_and_starts_reauth(mock_entry, mock_client, monkeypatch):
    """Test that auth_failed callback creates a persistent Repairs issue and starts reauth."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock(side_effect=lambda func, *args: func(*args))

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()

    created_issues = {}

    def mock_create_issue(hass_arg, domain, issue_id, **kwargs):
        created_issues[issue_id] = kwargs

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.ir.async_create_issue",
        mock_create_issue,
    )

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    mock_entry.async_start_reauth = MagicMock()

    result = await async_setup_entry(hass, mock_entry)
    assert result is True

    # Find the callback registered with register_auth_failed_callback
    mock_client.register_auth_failed_callback.assert_called_once()
    auth_failed_cb = mock_client.register_auth_failed_callback.call_args[0][0]

    # Trigger the callback
    auth_failed_cb(mock_client)

    issue_id = f"auth_token_invalidated_{mock_entry.entry_id}"
    assert issue_id in created_issues
    assert created_issues[issue_id]["translation_key"] == "auth_token_invalidated"
    assert created_issues[issue_id]["translation_placeholders"] == {"ip_address": mock_client.ip}
    mock_entry.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.anyio
async def test_update_listener_options_filtering(mock_entry, mock_client, monkeypatch):
    """Test that update_listener only reloads if entry.options changed (ignoring entry.data token updates)."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()

    mock_entry.options = {"enable_remote": True}
    await async_setup_entry(hass, mock_entry)

    # 1. Trigger update_listener with unchanged options (e.g. entry.data updated with refreshed tokens)
    await update_listener(hass, mock_entry)
    hass.config_entries.async_reload.assert_not_called()

    # 2. Trigger update_listener with changed options
    mock_entry.options = {"enable_remote": False}
    await update_listener(hass, mock_entry)
    hass.config_entries.async_reload.assert_awaited_once_with(mock_entry.entry_id)
