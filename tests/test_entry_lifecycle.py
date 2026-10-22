"""Tests for Hisense VIDAA config entry setup, unload, reauth callbacks, and options update filtering."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.hisense_vidaa import (
    DOMAIN,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
    update_listener,
)
from custom_components.hisense_vidaa.const import (
    SERVICE_CHANGE_CHANNEL,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_KEY_SEQUENCE,
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
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_CHANGE_CHANNEL,
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

    loaded_entries = set()

    def fake_forward(entry, platforms):
        loaded_entries.add(entry)
        return True

    def fake_unload(entry, platforms):
        loaded_entries.discard(entry)
        return True

    hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=fake_forward)
    hass.config_entries.async_unload_platforms = AsyncMock(side_effect=fake_unload)
    hass.config_entries.async_loaded_entries = MagicMock(side_effect=lambda domain: list(loaded_entries))
    hass.config_entries.async_entries = MagicMock(side_effect=lambda domain: list(loaded_entries))
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
async def test_connect_failure_raises_config_entry_not_ready(
    mock_entry, mock_client, monkeypatch
):
    """[F10-leg2] a missing/invalid cert must fail setup cleanly, not leak a FileNotFoundError."""
    mock_entry.runtime_data = None
    hass = _setup_hass(mock_entry, mock_client, monkeypatch)
    mock_client.connect_and_run = MagicMock(
        side_effect=FileNotFoundError(2, "No such file or directory")
    )

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_entry)

    assert getattr(mock_entry, "runtime_data", None) is None


@pytest.mark.anyio
async def test_remove_entry_deletes_persistent_issues(mock_entry, monkeypatch):
    """[F4-leg2/F5-leg6] removing an entry must clear both persistent Repairs issues."""
    hass = MagicMock()
    deleted = []
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.ir.async_delete_issue",
        lambda hass_arg, domain, issue_id: deleted.append((domain, issue_id)),
    )

    await async_remove_entry(hass, mock_entry)

    assert deleted == [
        (DOMAIN, f"certificate_missing_{mock_entry.entry_id}"),
        (DOMAIN, f"auth_token_invalidated_{mock_entry.entry_id}"),
    ]


@pytest.mark.anyio
async def test_entry_lifecycle_setup_and_unload(mock_entry, mock_client, monkeypatch):
    """Test that setting up and unloading an entry only unloads enabled platforms."""
    hass = MagicMock()
    hass.data = {}
    hass.services = FakeServices()
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

    loaded_entries = set()

    def fake_forward(entry, platforms):
        loaded_entries.add(entry)
        return True

    def fake_unload(entry, platforms):
        loaded_entries.discard(entry)
        return True

    hass.config_entries.async_forward_entry_setups = AsyncMock(side_effect=fake_forward)
    hass.config_entries.async_unload_platforms = AsyncMock(side_effect=fake_unload)
    hass.config_entries.async_loaded_entries = MagicMock(side_effect=lambda domain: list(loaded_entries))
    hass.config_entries.async_entries = MagicMock(side_effect=lambda domain: list(loaded_entries))

    # 1. Setup entry with notify and picture_controls disabled
    mock_entry.options = {"enable_remote": True, "enable_notify": False}
    result = await async_setup_entry(hass, mock_entry)
    assert result is True

    # Forward entry setups should have received 7 platforms (excluding notify and number)
    expected_platforms = ["media_player", "sensor", "binary_sensor", "button", "switch", "select", "remote"]
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(mock_entry, expected_platforms)
    assert mock_entry.runtime_data.platforms == expected_platforms

    # 2. Unload entry
    unload_result = await async_unload_entry(hass, mock_entry)
    assert unload_result is True
    # Unload platforms must ONLY be called with the 7 loaded platforms, never all PLATFORMS
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(mock_entry, expected_platforms)
    mock_client.disconnect.assert_called_once()


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


@pytest.mark.anyio
async def test_periodic_and_wake_clock_sync(mock_entry, mock_client, monkeypatch):
    """Test periodic clock sync and wake transition sync registered during entry setup."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock(side_effect=lambda func, *args: func(*args))
    def mock_create_bg_task(coro, name):
        coro.close()
        return None

    hass.async_create_background_task = MagicMock(side_effect=mock_create_bg_task)

    scheduled_intervals = []

    def mock_track_time(hass_obj, action, interval):
        scheduled_intervals.append((action, interval))
        return MagicMock()

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.async_track_time_interval",
        mock_track_time,
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()
    mock_client.sync_clock = MagicMock(return_value=0)
    mock_client.connected = True
    mock_client.is_on = False

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    await async_setup_entry(hass, mock_entry)

    # Verify periodic interval was registered (2 hours)
    assert len(scheduled_intervals) == 1
    action, interval = scheduled_intervals[0]
    assert interval.total_seconds() == 7200

    # Trigger periodic callback while TV is off -> sync_clock should not be called
    await action()
    mock_client.sync_clock.assert_not_called()

    # Trigger periodic callback while TV is on -> sync_clock called
    mock_client.is_on = True
    await action()
    mock_client.sync_clock.assert_called_once_with(2.0)

    # Verify wake transition hook
    mock_client.register_state_callback.assert_called_once()
    state_cb = mock_client.register_state_callback.call_args[0][0]

    # Transition from on to off -> no wake sync
    mock_client.is_on = False
    state_cb({"statetype": "fake_sleep_0"})
    hass.async_create_background_task.assert_not_called()

    # Transition from off to on -> wake sync triggered
    mock_client.is_on = True
    state_cb({"statetype": "app"})
    hass.async_create_background_task.assert_called_once()


@pytest.mark.anyio
async def test_async_remove_config_entry_device(mock_entry):
    """Test stale device removal handler."""
    from custom_components.hisense_vidaa import async_remove_config_entry_device

    hass = MagicMock()
    device_entry = MagicMock()
    result = await async_remove_config_entry_device(hass, mock_entry, device_entry)
    assert result is True


@pytest.mark.anyio
async def test_device_info_update_enriches_device_registry(mock_entry, mock_client, monkeypatch):
    """Test that incoming device info telemetry updates device registry model/manufacturer/sw_version."""
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
    mock_client.model_name = "65U8N"
    mock_client.manufacturer = "Toshiba"
    mock_client.firmware_version = "V0000.06.30T"

    mock_dev_reg = MagicMock()
    mock_device = MagicMock()
    mock_device.id = "dev_123"
    mock_device.model = "VIDAA TV"
    mock_device.manufacturer = "SmartTV"
    mock_device.sw_version = None
    mock_dev_reg.async_get_device.return_value = mock_device
    mock_dev_reg.async_get_device_by_identifier.return_value = mock_device

    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get",
        lambda h: mock_dev_reg,
    )

    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    result = await async_setup_entry(hass, mock_entry)
    assert result is True

    # Trigger device_info callback
    mock_client.register_device_info_callback.assert_called_once()
    dev_info_cb = mock_client.register_device_info_callback.call_args[0][0]

    dev_info_cb({"model_name": "65U8N", "brand": "tos", "sw_version": "V0000.06.30T"})

    mock_dev_reg.async_update_device.assert_called_once_with(
        "dev_123",
        model="65U8N",
        manufacturer="Toshiba",
        sw_version="V0000.06.30T",
    )
