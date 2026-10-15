"""Tests for Hisense VIDAA custom integration services."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from custom_components.hisense_vidaa import async_setup
from custom_components.hisense_vidaa.const import (
    ATTR_ACTION,
    ATTR_APP,
    ATTR_CHANNEL,
    ATTR_CONFIRM,
    ATTR_DELAY,
    ATTR_KEY,
    ATTR_MENU_ID,
    ATTR_MENU_VALUE,
    ATTR_REPEAT,
    ATTR_SEQUENCE,
    ATTR_TEXT,
    DOMAIN,
    SERVICE_CHANGE_CHANNEL,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
)


@pytest.mark.anyio
async def test_services_registration_and_send_key():
    """Test registering services and calling send_key service."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler, *args, **kwargs):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
    mock_client.ip = "192.168.50.12"
    hass.data[DOMAIN] = {"entry_1": {"client": mock_client}}

    success = await async_setup(hass, {})
    assert success is True

    # Ensure all services registered
    assert f"{DOMAIN}.{SERVICE_SEND_KEY}" in registered_services
    assert f"{DOMAIN}.{SERVICE_LAUNCH_APP}" in registered_services
    assert f"{DOMAIN}.{SERVICE_SET_PICTURE_SETTING}" in registered_services
    assert f"{DOMAIN}.{SERVICE_SET_SOUND_SETTING}" in registered_services
    assert f"{DOMAIN}.{SERVICE_SEND_TEXT_INPUT}" in registered_services

    # Call send_key with repeat and delay
    call_send_key = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_KEY,
        data={ATTR_KEY: "KEY_POWER", ATTR_REPEAT: 2, ATTR_DELAY: 0.01},
    )
    result = await registered_services[f"{DOMAIN}.{SERVICE_SEND_KEY}"](call_send_key)
    assert mock_client.send_command.call_count == 2
    mock_client.send_command.assert_called_with("KEY_POWER")
    assert result == {
        "key": "KEY_POWER",
        "repeat": 2,
        "targets": ["192.168.50.12"],
        "count": 1,
    }


@pytest.mark.anyio
async def test_launch_app_service_matching():
    """Test launch_app service with app dictionary matching."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler, *args, **kwargs):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
    mock_client.ip = "192.168.50.12"
    mock_client.apps = [
        {"name": "YouTube", "appId": "youtube_app_01", "url": "https://youtube.com/tv"},
        {"appName": "Netflix", "appId": "netflix_app_02", "appUrl": "netflix://"},
    ]
    hass.data[DOMAIN] = {"entry_1": {"client": mock_client}}

    await async_setup(hass, {})

    # Match by name
    call_yt = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={ATTR_APP: "youtube"},
    )
    result_yt = await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_yt)
    mock_client.launch_app.assert_called_with("youtube_app_01", "YouTube", "https://youtube.com/tv")
    assert result_yt["count"] == 1
    assert result_yt["targets"][0]["app_id"] == "youtube_app_01"

    # Match by appName
    call_netflix = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={ATTR_APP: "NETFLIX"},
    )
    result_nf = await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_netflix)
    mock_client.launch_app.assert_called_with("netflix_app_02", "Netflix", "netflix://")
    assert result_nf["count"] == 1
    assert result_nf["targets"][0]["app_id"] == "netflix_app_02"

    # Fallback when app not in cached app list
    call_unknown = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={ATTR_APP: "CustomApp"},
    )
    result_unk = await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_unknown)
    mock_client.launch_app.assert_called_with("", "CustomApp", "CustomApp")
    assert result_unk["count"] == 1
    assert result_unk["targets"][0]["app_name"] == "CustomApp"


@pytest.mark.anyio
async def test_launch_app_service_with_app_id_and_url_overrides():
    """Test launch_app with app_id, app_name, and url parameter overrides."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler, *args, **kwargs):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
    mock_client.ip = "192.168.50.12"
    mock_client.apps = [
        {"name": "YouTube", "appId": "3", "url": "https://youtube.com"},
    ]
    hass.data[DOMAIN] = {"entry_1": {"client": mock_client}}

    await async_setup(hass, {})

    # Launch with explicit app_id, app_name, and url override (e.g. YouTube video URL)
    call_yt_url = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={
            "app": "YouTube",
            "app_id": "3",
            "app_name": "YouTube",
            "url": "https://www.youtube.com/watch?v=REPPgPcw4hk",
        },
    )
    res = await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_yt_url)
    mock_client.launch_app.assert_called_with("3", "YouTube", "https://www.youtube.com/watch?v=REPPgPcw4hk")
    assert res["count"] == 1
    assert res["targets"][0]["app_id"] == "3"
    assert res["targets"][0]["app_url"] == "https://www.youtube.com/watch?v=REPPgPcw4hk"

    # Launch providing ONLY app_id (without app parameter)
    call_id_only = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={
            "app_id": "3",
            "url": "https://www.youtube.com/watch?v=REPPgPcw4hk",
        },
    )
    res_id_only = await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_id_only)
    mock_client.launch_app.assert_called_with("3", "YouTube", "https://www.youtube.com/watch?v=REPPgPcw4hk")
    assert res_id_only["app"] == "3"
    assert res_id_only["targets"][0]["app_id"] == "3"
    assert res_id_only["targets"][0]["app_name"] == "YouTube"

    # Schema validation: calling with neither app nor app_id should fail validation
    from custom_components.hisense_vidaa.services import _validate_launch_app_data
    with pytest.raises(vol.Invalid):
        _validate_launch_app_data({})


@pytest.mark.anyio
async def test_picture_sound_and_text_input_services():
    """Test set_picture_setting, set_sound_setting, and send_text_input services."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler, *args, **kwargs):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
    mock_client.ip = "192.168.50.12"
    hass.data[DOMAIN] = {"entry_1": {"client": mock_client}}

    await async_setup(hass, {})

    # Picture setting
    call_pic = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SET_PICTURE_SETTING,
        data={ATTR_MENU_ID: "picture_mode", ATTR_MENU_VALUE: "Cinema Night"},
    )
    res_pic = await registered_services[f"{DOMAIN}.{SERVICE_SET_PICTURE_SETTING}"](call_pic)
    mock_client.set_picture_setting.assert_called_with("picture_mode", "Cinema Night")
    assert res_pic["menu_id"] == "picture_mode"

    # Sound setting
    call_snd = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SET_SOUND_SETTING,
        data={ATTR_MENU_ID: "sound_mode", ATTR_MENU_VALUE: "Theater"},
    )
    res_snd = await registered_services[f"{DOMAIN}.{SERVICE_SET_SOUND_SETTING}"](call_snd)
    mock_client.set_sound_setting.assert_called_with("sound_mode", "Theater")
    assert res_snd["menu_value"] == "Theater"

    # Text input
    call_txt = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_TEXT_INPUT,
        data={ATTR_TEXT: "hello world", ATTR_ACTION: "insert"},
    )
    res_txt = await registered_services[f"{DOMAIN}.{SERVICE_SEND_TEXT_INPUT}"](call_txt)
    mock_client.send_text_input.assert_called_with("hello world", "insert")
    assert res_txt["text"] == "hello world"


@pytest.mark.anyio
async def test_service_target_resolution():
    """Test targeted service execution against specific entries vs fallback broadcast."""
    from custom_components.hisense_vidaa.services import _get_target_clients

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

    # 4. Fallback to all when no target filter specified
    call_all = ServiceCall(domain=DOMAIN, service=SERVICE_SEND_KEY, data={})
    assert len(_get_target_clients(hass, call_all)) == 2


# ---------------------------------------------------------------------------
# HA-surface fix leg: F7-leg2 (area/floor/label targets) and F8-leg2
# (vol schemas + ServiceValidationError).
# ---------------------------------------------------------------------------

ALL_SERVICE_NAMES = [
    SERVICE_SEND_KEY,
    SERVICE_LAUNCH_APP,
    SERVICE_SET_PICTURE_SETTING,
    SERVICE_SET_SOUND_SETTING,
    SERVICE_SEND_TEXT_INPUT,
    SERVICE_SEND_KEY_SEQUENCE,
    SERVICE_CHANGE_CHANNEL,
]


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
    client_kitchen = MagicMock()
    client_kitchen.ip = "192.168.50.15"
    client_kitchen.mac = "e8:51:77:ec:98:2d"
    hass.data = {
        DOMAIN: {
            "entry_living": {"client": client_living},
            "entry_kitchen": {"client": client_kitchen},
        }
    }
    return hass, client_living, client_kitchen


def test_area_floor_and_label_targets_are_resolved(monkeypatch):
    """[F7-leg2] area/floor/label targets must select their TV, never broadcast."""
    from custom_components.hisense_vidaa.services import _get_target_clients

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


def _field(schema, name):
    """Return the validator `name` is declared with (works with real vol markers)."""
    for key, value in schema.items():
        if key == name or getattr(key, "schema", None) == name:
            return value
    raise AssertionError(f"{name} is not declared in {schema}")


@pytest.mark.anyio
async def test_services_register_schemas_that_coerce_repeat_and_delay():
    """[F8-leg2] every service declares a schema; repeat/delay are coerced."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    registered_schemas = {}

    def _record(domain, service, handler, schema=None, **kwargs):
        registered_schemas[service] = schema

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=_record)

    await async_setup(hass, {})

    for service in ALL_SERVICE_NAMES:
        assert isinstance(registered_schemas[service], vol.Schema), service

    fields = registered_schemas[SERVICE_SEND_KEY].schema
    assert _field(fields, ATTR_KEY) is str
    assert isinstance(_field(fields, ATTR_REPEAT), vol.Coerce)
    assert _field(fields, ATTR_REPEAT).type is int
    assert isinstance(_field(fields, ATTR_DELAY), vol.Coerce)
    assert _field(fields, ATTR_DELAY).type is float

    # the target selector keys must stay accepted, otherwise HA rejects every call
    for key in (
        "entity_id",
        "device_id",
        "area_id",
        "floor_id",
        "label_id",
        "entry_id",
        "ip_address",
        "mac_address",
    ):
        assert _field(fields, key) is not None


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
async def test_call_against_disconnected_tvs_raises_not_connected():
    """[F8-leg2] a call that can only reach disconnected TVs must raise not_connected."""
    hass, client_living, client_kitchen = _two_tv_hass()
    handlers = await _register_handlers(hass)
    client_living.connected = False
    client_kitchen.connected = False

    call = ServiceCall(
        domain=DOMAIN, service=SERVICE_SEND_KEY, data={ATTR_KEY: "KEY_HOME"}
    )

    with pytest.raises(ServiceValidationError) as err:
        await handlers[SERVICE_SEND_KEY](call)

    assert err.value.translation_key == "not_connected"
    client_living.send_command.assert_not_called()
    client_kitchen.send_command.assert_not_called()


@pytest.mark.anyio
async def test_send_key_sequence_service():
    """Test send_key_sequence service with list and comma-separated string."""
    hass, client_living, _client_kitchen = _two_tv_hass()
    client_living.ip = "10.0.0.1"
    handlers = await _register_handlers(hass)
    client_living.connected = True

    # Test list sequence
    call = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_KEY_SEQUENCE,
        data={
            ATTR_SEQUENCE: ["home", "down", "ok"],
            ATTR_DELAY: 0.01,
            "ip_address": "10.0.0.1",
        },
    )
    result = await handlers[SERVICE_SEND_KEY_SEQUENCE](call)
    assert result["sequence"] == ["home", "down", "ok"]
    assert client_living.send_command.call_count == 3
    client_living.send_command.assert_any_call("home")
    client_living.send_command.assert_any_call("down")
    client_living.send_command.assert_any_call("ok")

    # Test comma-separated string
    client_living.send_command.reset_mock()
    call_str = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_KEY_SEQUENCE,
        data={
            ATTR_SEQUENCE: "back, menu",
            ATTR_DELAY: 0.01,
            "ip_address": "10.0.0.1",
        },
    )
    result_str = await handlers[SERVICE_SEND_KEY_SEQUENCE](call_str)
    assert result_str["sequence"] == ["back", "menu"]
    assert client_living.send_command.call_count == 2

    # Test empty sequence validation
    call_empty = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_KEY_SEQUENCE,
        data={
            ATTR_SEQUENCE: [],
            "ip_address": "10.0.0.1",
        },
    )
    with pytest.raises(ServiceValidationError):
        await handlers[SERVICE_SEND_KEY_SEQUENCE](call_empty)


@pytest.mark.anyio
async def test_change_channel_service():
    """Test change_channel service dispatches digits and confirmation key."""
    hass, client_living, _client_kitchen = _two_tv_hass()
    client_living.ip = "10.0.0.1"
    handlers = await _register_handlers(hass)
    client_living.connected = True

    # Tune to channel 701 with confirmation
    call = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_CHANGE_CHANNEL,
        data={
            ATTR_CHANNEL: 701,
            ATTR_CONFIRM: True,
            ATTR_DELAY: 0.01,
            "ip_address": "10.0.0.1",
        },
    )
    result = await handlers[SERVICE_CHANGE_CHANNEL](call)
    assert result["digits"] == ["7", "0", "1"]
    assert result["confirmed"] is True
    # Digits KEY_7, KEY_0, KEY_1 and confirmation KEY_OK
    assert client_living.send_command.call_count == 4
    calls = [c[0][0] for c in client_living.send_command.call_args_list]
    assert calls == ["KEY_7", "KEY_0", "KEY_1", "KEY_OK"]

    # Tune without confirmation
    client_living.send_command.reset_mock()
    call_no_confirm = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_CHANGE_CHANNEL,
        data={
            ATTR_CHANNEL: "12",
            ATTR_CONFIRM: False,
            ATTR_DELAY: 0.01,
            "ip_address": "10.0.0.1",
        },
    )
    result_no_confirm = await handlers[SERVICE_CHANGE_CHANNEL](call_no_confirm)
    assert result_no_confirm["confirmed"] is False
    assert client_living.send_command.call_count == 2
    calls_no_confirm = [c[0][0] for c in client_living.send_command.call_args_list]
    assert calls_no_confirm == ["KEY_1", "KEY_2"]

    # Invalid channel with no digits
    call_invalid = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_CHANGE_CHANNEL,
        data={
            ATTR_CHANNEL: "invalid",
            "ip_address": "10.0.0.1",
        },
    )
    with pytest.raises(ServiceValidationError):
        await handlers[SERVICE_CHANGE_CHANNEL](call_invalid)

