"""Tests for non-breaking migration layer from hisense_vidaa to vidaa."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.vidaa import async_migrate_entry, async_setup
from custom_components.vidaa.const import (
    ATTR_KEY,
    DOMAIN,
    LEGACY_DOMAIN,
    SERVICE_CHANGE_CHANNEL,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
)
from custom_components.vidaa.device_trigger import (
    async_validate_trigger_config,
)
from custom_components.vidaa.triggers.turn_on import (
    LEGACY_PLATFORM_TYPE,
    PLATFORM_TYPE,
)


@pytest.mark.anyio
async def test_async_migrate_entry_v1_to_v2():
    """Test migrating v1 hisense_vidaa config entry to v2.1 vidaa."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()

    mock_entry = MagicMock(spec=ConfigEntry)
    mock_entry.entry_id = "entry_vidaa_test_123"
    mock_entry.title = "Living Room TV"
    mock_entry.version = 1
    mock_entry.minor_version = 1
    mock_entry.domain = LEGACY_DOMAIN
    mock_entry.data = {"ip_address": "192.168.50.12"}
    mock_entry.options = {}

    # Mock entity registry
    mock_entity = MagicMock()
    mock_entity.platform = LEGACY_DOMAIN
    mock_entity.config_entry_id = "entry_vidaa_test_123"
    mock_entity.entity_id = "media_player.hisense_tv"

    ent_reg = MagicMock()
    ent_reg.entities = {mock_entity.entity_id: mock_entity}

    def _mock_update_platform(entity_id, new_platform, **kwargs):
        mock_entity.platform = new_platform
        return mock_entity

    ent_reg.async_update_entity_platform.side_effect = _mock_update_platform

    # Mock device registry
    mock_device = MagicMock()
    mock_device.id = "dev_reg_id_1"

    with patch("custom_components.vidaa.er.async_get", return_value=ent_reg), \
         patch("custom_components.vidaa.dr.async_get") as mock_dr_get:

        dev_reg = MagicMock()
        dev_reg.async_get_device.return_value = mock_device
        mock_dr_get.return_value = dev_reg

        result = await async_migrate_entry(hass, mock_entry)

        assert result is True
        assert mock_entry.domain == DOMAIN
        assert mock_entity.platform == DOMAIN

        dev_reg.async_update_device.assert_called_once_with(
            "dev_reg_id_1",
            merge_identifiers={(DOMAIN, "entry_vidaa_test_123"), (LEGACY_DOMAIN, "entry_vidaa_test_123")},
        )

        hass.config_entries.async_update_entry.assert_called_once_with(
            mock_entry,
            version=2,
            minor_version=1,
        )


@pytest.mark.anyio
async def test_legacy_service_aliases(caplog):
    """Test legacy hisense_vidaa.* services register as aliases with deprecation warnings."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler, *args, **kwargs):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(side_effect=lambda d, s: f"{d}.{s}" in registered_services)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
    mock_client.ip = "192.168.50.12"
    mock_client.async_send_command = AsyncMock()
    hass.data[DOMAIN] = {"entry_1": {"client": mock_client}}

    success = await async_setup(hass, {})
    assert success is True

    # Both domains should have all 7 custom services registered
    services_to_check = [
        SERVICE_SEND_KEY,
        SERVICE_SEND_KEY_SEQUENCE,
        SERVICE_CHANGE_CHANNEL,
        SERVICE_LAUNCH_APP,
        SERVICE_SET_PICTURE_SETTING,
        SERVICE_SET_SOUND_SETTING,
        SERVICE_SEND_TEXT_INPUT,
    ]

    for s in services_to_check:
        assert f"{DOMAIN}.{s}" in registered_services
        assert f"{LEGACY_DOMAIN}.{s}" in registered_services

    # Calling legacy hisense_vidaa.send_key should warn and invoke the handler
    with caplog.at_level(logging.WARNING):
        call_legacy = ServiceCall(
            domain=LEGACY_DOMAIN,
            service=SERVICE_SEND_KEY,
            data={ATTR_KEY: "KEY_POWER"},
        )
        await registered_services[f"{LEGACY_DOMAIN}.{SERVICE_SEND_KEY}"](call_legacy)

        assert mock_client.async_send_command.called
        assert "Action 'hisense_vidaa.send_key' is deprecated" in caplog.text


@pytest.mark.anyio
async def test_legacy_device_trigger_support():
    """Test legacy hisense_vidaa.turn_on device trigger is supported."""
    hass = MagicMock(spec=HomeAssistant)
    mock_entry = MagicMock()
    mock_entry.domain = DOMAIN
    mock_entry.state = ConfigEntryState.LOADED
    hass.config_entries.async_get_entry.return_value = mock_entry

    mock_device = MagicMock()
    mock_device.id = "device_123"
    mock_device.config_entries = ["test_entry_456"]

    with patch("custom_components.vidaa.helpers.dr.async_get") as mock_dr_get, \
         patch("custom_components.vidaa.device_trigger.async_get_device_entry_by_device_id", return_value=mock_device):

        dev_reg = MagicMock()
        dev_reg.async_get.return_value = mock_device
        mock_dr_get.return_value = dev_reg

        # Validate trigger config with legacy trigger type
        config = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "device_123",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: LEGACY_PLATFORM_TYPE,
        }
        validated = await async_validate_trigger_config(hass, config)
        assert validated[CONF_TYPE] == LEGACY_PLATFORM_TYPE

        # Validate trigger config with canonical trigger type
        config_canonical = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: "device_123",
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: PLATFORM_TYPE,
        }
        validated_canonical = await async_validate_trigger_config(hass, config_canonical)
        assert validated_canonical[CONF_TYPE] == PLATFORM_TYPE


@pytest.mark.anyio
async def test_async_setup_auto_migrates_legacy_entries():
    """Test async_setup detects and migrates existing hisense_vidaa entries."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()

    legacy_entry = MagicMock(spec=ConfigEntry)
    legacy_entry.title = "Old TV"
    legacy_entry.entry_id = "old_entry_1"
    legacy_entry.version = 1
    legacy_entry.minor_version = 1
    legacy_entry.domain = LEGACY_DOMAIN
    legacy_entry.data = {}
    legacy_entry.options = {}

    hass.config_entries = MagicMock()
    hass.config_entries.async_entries.return_value = [legacy_entry]

    with patch("custom_components.vidaa.er.async_get"), \
         patch("custom_components.vidaa.dr.async_get"):

        res = await async_setup(hass, {})
        assert res is True
        assert legacy_entry.domain == DOMAIN
        hass.config_entries.async_update_entry.assert_called_once_with(
            legacy_entry,
            version=2,
            minor_version=1,
        )


@pytest.mark.anyio
async def test_legacy_directory_detection_issue():
    """Test async_setup creates a repair issue when old custom_components/hisense_vidaa exists."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries.return_value = []
    hass.config.path.return_value = "/config/custom_components/hisense_vidaa"

    with patch("os.path.isdir", return_value=True), \
         patch("custom_components.vidaa.ir.async_create_issue") as mock_create_issue:

        res = await async_setup(hass, {})
        assert res is True
        mock_create_issue.assert_called_once()
        assert mock_create_issue.call_args[0][2] == "legacy_folder_detected"
