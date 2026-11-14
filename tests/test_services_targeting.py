"""Tests for service targeting: entry_id, IP/MAC, entity, area, floor, and label targets."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from custom_components.vidaa import async_setup
from custom_components.vidaa.const import (
    ATTR_KEY,
    DOMAIN,
    SERVICE_SEND_KEY,
)
from custom_components.vidaa.services import _get_target_clients


@pytest.mark.anyio
async def test_service_target_resolution():
    """Test targeted service execution against specific entries vs fallback broadcast."""

    hass = MagicMock(spec=HomeAssistant)
    client_1 = MagicMock()
    client_1.ip = "192.168.50.12"
    client_1.mac = "e8:51:77:ec:98:1c"

    client_2 = MagicMock()
    client_2.ip = "192.168.50.15"
    client_2.mac = "e8:51:77:ec:98:2d"

    hass.data = {
        DOMAIN: {
            "entry_1": {"client": client_1},
            "entry_2": {"client": client_2},
        }
    }

    # 1. Target by entry_id
    call_entry = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={"entry_id": "entry_1"})
    assert _get_target_clients(hass, call_entry) == [client_1]

    # 2. Target by IP
    call_ip = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={"ip_address": "192.168.50.15"})
    assert _get_target_clients(hass, call_ip) == [client_2]

    # 3. Target by MAC
    call_mac = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={"mac": "e8:51:77:ec:98:1c"})
    assert _get_target_clients(hass, call_mac) == [client_1]

    # 4. Explicit broadcast to all via entity_id="all" when multiple TVs configured
    call_all = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={"entity_id": "all"})
    assert len(_get_target_clients(hass, call_all)) == 2

    # 5. Untargeted call on multiple TVs raises ambiguous_target
    call_untargeted = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={})
    with pytest.raises(ServiceValidationError) as exc_info:
        _get_target_clients(hass, call_untargeted)
    assert exc_info.value.translation_key == "ambiguous_target"



def _install_registry_fakes(monkeypatch, areas, devices, entities):
    """Point the HA registry helpers at simple in-memory registries."""
    area_reg = MagicMock()
    area_reg.areas = areas
    dev_reg = MagicMock()
    dev_reg.devices = devices
    dev_reg.async_get = devices.get
    ent_reg = MagicMock()
    ent_reg.entities = entities
    ent_reg.async_get = entities.get
    monkeypatch.setattr(
        "homeassistant.helpers.area_registry.async_get", lambda hass: area_reg
    )
    monkeypatch.setattr(
        "homeassistant.helpers.device_registry.async_get", lambda hass: dev_reg
    )
    monkeypatch.setattr(
        "homeassistant.helpers.entity_registry.async_get", lambda hass: ent_reg
    )


def _two_tv_hass():
    """Build a hass double with one TV per area/floor and one labelled device."""
    hass = MagicMock(spec=HomeAssistant)
    client_living = MagicMock()
    client_living.ip = "192.168.50.12"
    client_living.mac = "e8:51:77:ec:98:1c"
    client_living.async_send_command = AsyncMock(side_effect=client_living.send_command)
    client_living.async_launch_app = AsyncMock(side_effect=client_living.launch_app)
    client_living.async_set_picture_setting = AsyncMock(side_effect=client_living.set_picture_setting)
    client_living.async_set_sound_setting = AsyncMock(side_effect=client_living.set_sound_setting)
    client_living.async_send_text_input = AsyncMock(side_effect=client_living.send_text_input)

    client_kitchen = MagicMock()
    client_kitchen.ip = "192.168.50.15"
    client_kitchen.mac = "e8:51:77:ec:98:2d"
    client_kitchen.async_send_command = AsyncMock(side_effect=client_kitchen.send_command)
    client_kitchen.async_launch_app = AsyncMock(side_effect=client_kitchen.launch_app)
    client_kitchen.async_set_picture_setting = AsyncMock(side_effect=client_kitchen.set_picture_setting)
    client_kitchen.async_set_sound_setting = AsyncMock(side_effect=client_kitchen.set_sound_setting)
    client_kitchen.async_send_text_input = AsyncMock(side_effect=client_kitchen.send_text_input)

    hass.data = {
        DOMAIN: {
            "entry_living": {"client": client_living},
            "entry_kitchen": {"client": client_kitchen},
        }
    }
    return hass, client_living, client_kitchen




def test_area_floor_and_label_targets_are_resolved(monkeypatch):
    """[F7-leg2] area/floor/label targets must select their TV, never broadcast."""

    hass, client_living, client_kitchen = _two_tv_hass()
    areas = {
        "area_living": SimpleNamespace(id="area_living", floor_id="floor_ground"),
        "area_kitchen": SimpleNamespace(id="area_kitchen", floor_id="floor_up"),
    }
    devices = {
        "dev_kitchen": SimpleNamespace(
            id="dev_kitchen",
            area_id="area_kitchen",
            config_entries={"entry_kitchen"},
            labels={"tv_kids"},
            config_entry_id="entry_kitchen",
        )
    }
    entities = {
        "media_player.living_tv": SimpleNamespace(
            entity_id="media_player.living_tv",
            area_id="area_living",
            device_id=None,
            config_entry_id="entry_living",
            labels=set(),
        )
    }
    _install_registry_fakes(monkeypatch, areas, devices, entities)

    # area -> the entity whose area matches
    call_area = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"area_id": "area_living"}
    )
    assert _get_target_clients(hass, call_area) == [client_living]

    # floor -> the areas on that floor -> their devices
    call_floor = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"floor_id": "floor_up"}
    )
    assert _get_target_clients(hass, call_floor) == [client_kitchen]

    # label -> the labelled device
    call_label = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"label_id": "tv_kids"}
    )
    assert _get_target_clients(hass, call_label) == [client_kitchen]

    # device -> the device's config entry (existing path, fed by the fake registry)
    call_device = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"device_id": "dev_kitchen"}
    )
    assert _get_target_clients(hass, call_device) == [client_kitchen]

    # entity -> the entity's config entry (existing path, fed by the fake registry)
    call_entity = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_KEY,
        data={"entity_id": "media_player.living_tv"},
    )
    assert _get_target_clients(hass, call_entity) == [client_living]

    # an unmatched target must select nothing - never every TV
    call_unknown = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"area_id": "area_nowhere"}
    )
    assert _get_target_clients(hass, call_unknown) == []




async def _register_handlers(hass):
    """Register the integration services on `hass` and return {service: handler}."""
    handlers = {}

    def _record(domain, service, handler, schema=None, **kwargs):
        handlers[service] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=_record)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    await async_setup(hass, {})
    return handlers




@pytest.mark.anyio
async def test_targeted_call_without_a_match_raises_no_target_device():
    """[F8-leg2] a target that matches nothing must raise instead of returning count 0."""
    hass, client_living, _client_kitchen = _two_tv_hass()
    handlers = await _register_handlers(hass)
    client_living.connected = True

    call = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_KEY,
        data={ATTR_KEY: "KEY_HOME", "ip_address": "10.0.0.99"},
    )

    with pytest.raises(ServiceValidationError) as err:
        await handlers[SERVICE_SEND_KEY](call)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "no_target_device"
    client_living.send_command.assert_not_called()


@pytest.mark.anyio


def test_multi_tv_ambiguous_target_guard() -> None:
    """Test single-TV auto targeting, multi-TV ambiguous target exception, and 'all' broadcast."""
    from types import SimpleNamespace

    from custom_components.vidaa.services import (
        _get_target_clients,
        _resolve_service_targets,
    )

    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = MagicMock()

    client1 = MagicMock()
    client1.ip = "10.0.0.1"
    client1.mac = "AA:BB:CC:DD:EE:01"
    client1.connected = True

    client2 = MagicMock()
    client2.ip = "10.0.0.2"
    client2.mac = "AA:BB:CC:DD:EE:02"
    client2.connected = True

    entry1 = SimpleNamespace(entry_id="entry_1", runtime_data=SimpleNamespace(client=client1))
    entry2 = SimpleNamespace(entry_id="entry_2", runtime_data=SimpleNamespace(client=client2))

    # Case 1: Single TV configured, no target given -> auto-targets the single TV
    hass.config_entries.async_loaded_entries = MagicMock(return_value=[entry1])
    call_single = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={})
    assert _get_target_clients(hass, call_single) == [client1]

    # Case 2: Multiple TVs configured, no target given -> raises ambiguous_target
    hass.config_entries.async_loaded_entries = MagicMock(return_value=[entry1, entry2])
    call_multi_no_target = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={})
    with pytest.raises(ServiceValidationError) as exc_info:
        _get_target_clients(hass, call_multi_no_target)
    assert exc_info.value.translation_key == "ambiguous_target"

    # Case 3: Multiple TVs configured, entity_id: "all" string -> targets all
    call_broadcast_str = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"entity_id": "ALL"}
    )
    assert _get_target_clients(hass, call_broadcast_str) == [client1, client2]

    # Case 4: Multiple TVs configured, entity_id: ["all"] list -> targets all
    call_broadcast_list = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"entity_id": ["all"]}
    )
    assert _get_target_clients(hass, call_broadcast_list) == [client1, client2]

    # Case 5: Target by explicit IP address
    call_ip = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"ip_address": "10.0.0.2"}
    )
    assert _get_target_clients(hass, call_ip) == [client2]

    # Case 6: Target by non-existent IP address -> raises no_target_device
    call_unknown_ip = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={"ip_address": "192.168.1.99"}
    )
    with pytest.raises(ServiceValidationError) as exc_unknown:
        _resolve_service_targets(hass, call_unknown_ip)
    assert exc_unknown.value.translation_key == "no_target_device"



