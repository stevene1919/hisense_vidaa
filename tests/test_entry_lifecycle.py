"""Tests for Hisense VIDAA config entry setup, unload, reauth callbacks, and options update filtering."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.vidaa import (
    DOMAIN,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
    update_listener,
)
from custom_components.vidaa.const import (
    CONF_ACCESS_TOKEN,
    CONF_AUTH_PROFILE,
    CONF_BRAND,
    CONF_CLIENT_ID,
    CONF_ENABLE_NOTIFY,
    CONF_ENABLE_PICTURE_CONTROLS,
    CONF_ENABLE_REMOTE,
    CONF_IP_ADDRESS,
    CONF_MAC_ADDRESS,
    CONF_USE_SSL,
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
    def _mock_bg_task(coro, *a, **kw):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()
    hass.async_create_background_task = MagicMock(side_effect=_mock_bg_task)
    hass.services = FakeServices()
    monkeypatch.setattr(
        "custom_components.vidaa.HisenseTvClient",
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
    mock_client.async_connect_and_run = AsyncMock(
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
        "custom_components.vidaa.ir.async_delete_issue",
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
        "custom_components.vidaa.HisenseTvClient",
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
    assert mock_client.disconnect.called or mock_client.async_disconnect.called


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
        "custom_components.vidaa.HisenseTvClient",
        lambda *args, **kwargs: mock_client,
    )
    mock_client.has_notifications = False
    mock_client.check_and_refresh_token = MagicMock(return_value=False)
    mock_client.connect_and_run = MagicMock()

    created_issues = {}

    def mock_create_issue(hass_arg, domain, issue_id, **kwargs):
        created_issues[issue_id] = kwargs

    monkeypatch.setattr(
        "custom_components.vidaa.ir.async_create_issue",
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
        "custom_components.vidaa.HisenseTvClient",
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
        "custom_components.vidaa.async_track_time_interval",
        mock_track_time,
    )
    monkeypatch.setattr(
        "custom_components.vidaa.HisenseTvClient",
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
    assert mock_client.sync_clock.called or mock_client.async_sync_clock.called

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
    from custom_components.vidaa import async_remove_config_entry_device

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
        "custom_components.vidaa.HisenseTvClient",
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


@pytest.mark.anyio
async def test_async_setup_entry_passes_brand_to_client(mock_entry, monkeypatch):
    """Test that async_setup_entry reads CONF_BRAND from entry.data and initializes HisenseTvClient with it."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.loop = MagicMock()
    def _mock_bg_task(coro, *a, **kw):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()
    hass.async_create_background_task = MagicMock(side_effect=_mock_bg_task)
    hass.services = FakeServices()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    mock_entry.data = {
        "ip_address": "192.168.50.25",
        "mac_address": "00:11:22:33:44:55",
        "brand": "tos",
        "use_ssl": False,
    }
    mock_entry.options = {}

    captured_kwargs = {}

    def mock_client_factory(*args, **kwargs):
        captured_kwargs.update(kwargs)
        client = MagicMock()
        client.has_notifications = False
        client.async_check_and_refresh_token = AsyncMock(return_value=False)
        client.async_connect_and_run = AsyncMock()
        return client

    monkeypatch.setattr(
        "custom_components.vidaa.HisenseTvClient",
        mock_client_factory,
    )

    result = await async_setup_entry(hass, mock_entry)
    assert result is True
    assert captured_kwargs.get("brand") == "tos"


@pytest.mark.anyio
async def test_setup_entry_cleans_up_disabled_platforms():
    """Test async_setup_entry removes disabled platform entities from Entity Registry."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_update_entry = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    def _mock_bg_task(coro, *a, **kw):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()
    hass.async_create_background_task = MagicMock(side_effect=_mock_bg_task)
    hass.services = FakeServices()
    hass.loop = MagicMock()

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_cleanup_entry"
    entry.async_on_unload = MagicMock()
    entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_CLIENT_ID: "E85177EC981C$his$123456_vidaacommon_001",
        CONF_ACCESS_TOKEN: "valid_token",
        CONF_BRAND: "his",
    }
    # User disabled remote, notify, and picture controls
    entry.options = {
        CONF_ENABLE_REMOTE: False,
        CONF_ENABLE_NOTIFY: False,
        CONF_ENABLE_PICTURE_CONTROLS: False,
    }

    mock_client = MagicMock()
    mock_client.has_notifications = False
    mock_client.async_check_and_refresh_token = AsyncMock(return_value=False)
    mock_client.async_connect_and_run = AsyncMock()

    mock_reg = MagicMock()
    removed_entities = []
    mock_reg.async_get_entity_id = MagicMock(side_effect=lambda domain, platform, uid: f"{domain}.{uid}")
    mock_reg.async_remove = MagicMock(side_effect=lambda eid: removed_entities.append(eid))

    with patch("custom_components.vidaa.HisenseTvClient", return_value=mock_client), \
         patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_reg), \
         patch("homeassistant.helpers.issue_registry.async_create_issue"), \
         patch("homeassistant.helpers.issue_registry.async_delete_issue"):
        res = await async_setup_entry(hass, entry)
        assert res is True

    # Remote, notify, and 3 picture controls must be removed
    assert "remote.test_cleanup_entry_remote" in removed_entities
    assert "notify.test_cleanup_entry_notify" in removed_entities
    assert "number.test_cleanup_entry_backlight" in removed_entities
    assert "number.test_cleanup_entry_brightness" in removed_entities
    assert "number.test_cleanup_entry_contrast" in removed_entities


@pytest.mark.anyio
async def test_async_setup_entry_resolves_certs_in_executor():
    """Test that async_setup_entry offloads certificate resolution to executor job (Issue #49)."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_update_entry = MagicMock()
    executor_calls = []

    def fake_executor_job(func, *args):
        executor_calls.append(func)
        return func(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=fake_executor_job)
    hass.loop = MagicMock()
    hass.async_create_background_task = MagicMock(side_effect=lambda coro, *a, **kw: coro.close() if hasattr(coro, "close") else MagicMock())
    hass.services = FakeServices()

    entry = MagicMock()
    entry.entry_id = "test_executor_certs"
    entry.unique_id = "e8:51:77:ec:98:1c"
    entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_CLIENT_ID: "E85177EC981C$his$123456_vidaacommon_001",
        CONF_ACCESS_TOKEN: "valid_token",
        CONF_BRAND: "his",
        CONF_USE_SSL: True,
    }
    entry.options = {
        CONF_USE_SSL: True,
        CONF_AUTH_PROFILE: "auto",
    }

    mock_client = MagicMock()
    mock_client.has_notifications = False
    mock_client.async_check_and_refresh_token = AsyncMock(return_value=False)
    mock_client.async_connect_and_run = AsyncMock()
    mock_client.certfile = "/ssl/hisense.crt"
    mock_client.keyfile = "/ssl/hisense.key"

    with patch("custom_components.vidaa.HisenseTvClient", return_value=mock_client), \
         patch("custom_components.vidaa.resolve_certificates", return_value=("/ssl/hisense.crt", "/ssl/hisense.key")) as mock_resolve, \
         patch("custom_components.vidaa.resolve_ca_certificate", return_value=None), \
         patch("homeassistant.helpers.issue_registry.async_create_issue"), \
         patch("homeassistant.helpers.issue_registry.async_delete_issue"):
        res = await async_setup_entry(hass, entry)
        assert res is True
        # Verify resolve_certificates was passed to executor
        assert any(call is mock_resolve or getattr(call, "__name__", "") == "resolve_certificates" for call in executor_calls)


@pytest.mark.anyio
async def test_setup_entry_prunes_retired_diagnostic_sensors():
    """Verify setup entry automatically removes orphaned brand_profile and auth_profile entities."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.loop = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.async_create_background_task = MagicMock(side_effect=lambda coro, *a, **kw: coro.close() if hasattr(coro, "close") else MagicMock())
    hass.services = FakeServices()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    entry = MagicMock()
    entry.entry_id = "test_prune_entry"
    entry.unique_id = "e8:51:77:ec:98:1c"
    entry.data = {
        CONF_IP_ADDRESS: "192.168.50.12",
        CONF_MAC_ADDRESS: "e8:51:77:ec:98:1c",
        CONF_CLIENT_ID: "client_1",
        CONF_ACCESS_TOKEN: "token_1",
        CONF_BRAND: "his",
        CONF_USE_SSL: False,
    }
    entry.options = {}

    mock_ent_reg = MagicMock()
    def _mock_get_entity_id(domain, platform, unique_id):
        if unique_id in ("test_prune_entry_brand_profile", "test_prune_entry_auth_profile"):
            return f"sensor.{unique_id}"
        return None
    mock_ent_reg.async_get_entity_id.side_effect = _mock_get_entity_id

    mock_client = MagicMock()
    mock_client.has_notifications = False
    mock_client.async_check_and_refresh_token = AsyncMock(return_value=False)
    mock_client.async_connect_and_run = AsyncMock()

    with patch("custom_components.vidaa.HisenseTvClient", return_value=mock_client), \
         patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_ent_reg), \
         patch("homeassistant.helpers.issue_registry.async_delete_issue"):
        res = await async_setup_entry(hass, entry)
        assert res is True
        mock_ent_reg.async_remove.assert_any_call("sensor.test_prune_entry_brand_profile")
        mock_ent_reg.async_remove.assert_any_call("sensor.test_prune_entry_auth_profile")

