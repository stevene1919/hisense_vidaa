"""Unit tests for Hisense VIDAA device automation triggers and PluggableAction."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.trigger import PluggableAction, TriggerConfig

from custom_components.hisense_vidaa import HisenseVidaaData
from custom_components.hisense_vidaa.const import DOMAIN
from custom_components.hisense_vidaa.device_trigger import (
    async_attach_trigger,
    async_get_triggers,
    async_validate_trigger_config,
)
from custom_components.hisense_vidaa.helpers import (
    async_get_device_entry_by_device_id,
    async_get_device_id_from_entity_id,
)
from custom_components.hisense_vidaa.media_player import HisenseVidaaMediaPlayer
from custom_components.hisense_vidaa.trigger import async_get_triggers as async_get_integration_triggers
from custom_components.hisense_vidaa.triggers.turn_on import (
    PLATFORM_TYPE,
    TurnOnTrigger,
    async_get_turn_on_description,
    async_get_turn_on_trigger,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_device_entry():
    """Create a mock device entry."""
    entry = MagicMock()
    entry.id = "test_device_123"
    entry.name = "Living Room TV"
    entry.name_by_user = "Living Room TV"
    entry.config_entries = ["test_entry_456"]
    return entry


def test_turn_on_trigger_structure():
    """Test data returned by async_get_turn_on_trigger."""
    trigger = async_get_turn_on_trigger("device_abc")
    assert trigger == {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: "device_abc",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: PLATFORM_TYPE,
    }
    assert PLATFORM_TYPE == "hisense_vidaa.turn_on"


def test_turn_on_description(mock_hass, mock_device_entry):
    """Test turn on trigger description helper."""
    with patch(
        "custom_components.hisense_vidaa.helpers.dr.async_get"
    ) as mock_dr_get:
        dev_reg = MagicMock()
        dev_reg.async_get.return_value = mock_device_entry
        mock_dr_get.return_value = dev_reg

        desc = async_get_turn_on_description(mock_hass, "test_device_123")
        assert "hisense_vidaa turn on trigger for Living Room TV" in desc


def test_helpers_get_device_entry_invalid(mock_hass):
    """Test error raised when device entry not found."""
    with patch(
        "custom_components.hisense_vidaa.helpers.dr.async_get"
    ) as mock_dr_get:
        dev_reg = MagicMock()
        dev_reg.async_get.return_value = None
        mock_dr_get.return_value = dev_reg

        with pytest.raises(ValueError, match="not a valid hisense_vidaa device"):
            async_get_device_entry_by_device_id(mock_hass, "missing_dev")


def test_helpers_get_device_id_from_entity_id(mock_hass):
    """Test extracting device ID from entity registry entry."""
    with patch(
        "custom_components.hisense_vidaa.helpers.er.async_get"
    ) as mock_er_get:
        ent_reg = MagicMock()
        mock_entity = MagicMock()
        mock_entity.device_id = "device_xyz"
        mock_entity.platform = DOMAIN
        ent_reg.async_get.return_value = mock_entity
        mock_er_get.return_value = ent_reg

        dev_id = async_get_device_id_from_entity_id(mock_hass, "media_player.hisense")
        assert dev_id == "device_xyz"

        # Invalid entity / wrong platform
        mock_entity.platform = "other_domain"
        with pytest.raises(HomeAssistantError):
            async_get_device_id_from_entity_id(mock_hass, "media_player.hisense")


@pytest.mark.anyio
async def test_device_trigger_list(mock_hass):
    """Test async_get_triggers returns turn_on trigger."""
    triggers = await async_get_triggers(mock_hass, "device_abc")
    assert len(triggers) == 1
    assert triggers[0][CONF_TYPE] == PLATFORM_TYPE
    assert triggers[0][CONF_DEVICE_ID] == "device_abc"


@pytest.mark.anyio
async def test_integration_triggers_list(mock_hass):
    """Test async_get_triggers in trigger.py."""
    triggers = await async_get_integration_triggers(mock_hass)
    assert "turn_on" in triggers
    assert triggers["turn_on"] is TurnOnTrigger


@pytest.mark.anyio
async def test_validate_trigger_config(mock_hass, mock_device_entry):
    """Test validating trigger config."""
    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: "test_device_123",
        CONF_TYPE: PLATFORM_TYPE,
    }

    mock_entry = MagicMock()
    mock_entry.domain = DOMAIN
    mock_entry.state = ConfigEntryState.LOADED

    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    with patch(
        "custom_components.hisense_vidaa.helpers.dr.async_get"
    ) as mock_dr_get:
        dev_reg = MagicMock()
        dev_reg.async_get.return_value = mock_device_entry
        mock_dr_get.return_value = dev_reg

        validated = await async_validate_trigger_config(mock_hass, config)
        assert validated == config


@pytest.mark.anyio
async def test_validate_trigger_config_not_loaded(mock_hass, mock_device_entry):
    """Test validating trigger config when entry not loaded."""
    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: "test_device_123",
        CONF_TYPE: PLATFORM_TYPE,
    }

    mock_entry = MagicMock()
    mock_entry.domain = DOMAIN
    mock_entry.state = ConfigEntryState.NOT_LOADED

    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    with patch(
        "custom_components.hisense_vidaa.helpers.dr.async_get"
    ) as mock_dr_get:
        dev_reg = MagicMock()
        dev_reg.async_get.return_value = mock_device_entry
        mock_dr_get.return_value = dev_reg

        with pytest.raises(InvalidDeviceAutomationConfig):
            await async_validate_trigger_config(mock_hass, config)


@pytest.mark.anyio
async def test_attach_trigger_and_pluggable_action(mock_hass, mock_device_entry):
    """Test attaching a device trigger connects to PluggableAction."""
    action_called = []

    def mock_action(variables, description, context=None):
        action_called.append((variables, description))

    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: "test_device_123",
        CONF_TYPE: PLATFORM_TYPE,
    }

    with patch(
        "custom_components.hisense_vidaa.helpers.dr.async_get"
    ) as mock_dr_get:
        dev_reg = MagicMock()
        dev_reg.async_get.return_value = mock_device_entry
        mock_dr_get.return_value = dev_reg

        remove_trigger = await async_attach_trigger(
            mock_hass,
            config,
            mock_action,
            {"trigger_data": {"test_var": 123}},
        )

        pluggable = PluggableAction()
        pluggable.async_register(
            mock_hass, async_get_turn_on_trigger("test_device_123")
        )

        assert bool(pluggable) is True

        await pluggable.async_run(mock_hass)
        assert len(action_called) == 1
        assert action_called[0][0]["trigger"]["test_var"] == 123

        # Test remove trigger
        remove_trigger()
        assert bool(pluggable) is False


@pytest.mark.anyio
async def test_turn_on_trigger_class(mock_hass, mock_device_entry):
    """Test TurnOnTrigger attachment with entity_id and device_id."""
    action_called = []

    async def mock_runner(variables, description, context=None):
        action_called.append((variables, description))

    config = TriggerConfig(
        options={
            ATTR_DEVICE_ID: ["test_device_123"],
        }
    )
    trigger = TurnOnTrigger(mock_hass, config)

    with patch(
        "custom_components.hisense_vidaa.helpers.dr.async_get"
    ) as mock_dr_get:
        dev_reg = MagicMock()
        dev_reg.async_get.return_value = mock_device_entry
        mock_dr_get.return_value = dev_reg

        unsub = await trigger.async_attach_runner(mock_runner)

        pluggable = PluggableAction()
        pluggable.async_register(
            mock_hass, async_get_turn_on_trigger("test_device_123")
        )
        assert bool(pluggable) is True

        await pluggable.async_run(mock_hass)
        assert len(action_called) == 1

        unsub()
        assert bool(pluggable) is False


@pytest.mark.anyio
async def test_media_player_turn_on_with_pluggable_action(mock_hass):
    """Test media player async_turn_on delegates to PluggableAction when registered."""
    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.is_on = False
    mock_client.async_turn_on = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.data = {}
    mock_entry.options = {}

    pluggable = PluggableAction()
    mock_entry.runtime_data = HisenseVidaaData(
        client=mock_client,
        platforms=["media_player"],
        options={},
        turn_on=pluggable,
    )

    player = HisenseVidaaMediaPlayer(mock_client, mock_entry)
    player.hass = mock_hass

    # 1. No action attached: fallback to client.async_turn_on
    await player.async_turn_on()
    mock_client.async_turn_on.assert_called_once()
    mock_client.async_turn_on.reset_mock()

    # 2. Action attached to PluggableAction
    action_ran = []

    def mock_action(variables, description, context=None):
        action_ran.append(True)

    PluggableAction.async_attach_trigger(
        mock_hass,
        async_get_turn_on_trigger("device_tv"),
        mock_action,
        {},
    )
    pluggable.async_register(mock_hass, async_get_turn_on_trigger("device_tv"))
    assert bool(pluggable) is True

    await player.async_turn_on()
    assert len(action_ran) == 1
    # Client WoL should NOT have been called because pluggable action intercepted
    mock_client.async_turn_on.assert_not_called()
