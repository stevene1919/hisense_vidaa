"""Pytest fixtures and mock Home Assistant environment for Hisense VIDAA test suite."""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

# Ensure custom_components/hisense_vidaa is in Python path for test execution
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)
INTEGRATION_DIR = os.path.join(PROJECT_DIR, "custom_components", "hisense_vidaa")

if INTEGRATION_DIR not in sys.path:
    sys.path.insert(0, INTEGRATION_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

@pytest.fixture
def anyio_backend():
    return "asyncio"

# Mock voluptuous if not installed
if "voluptuous" not in sys.modules:
    vol = types.ModuleType("voluptuous")
    class Schema:
        def __init__(self, schema):
            self.schema = schema
        def __call__(self, val):
            return val
    def Required(key, default=None): return key
    def Optional(key, default=None): return key
    def In(container): return lambda x: x
    vol.Schema = Schema
    vol.Required = Required
    vol.Optional = Optional
    vol.In = In
    sys.modules["voluptuous"] = vol

# If homeassistant is not installed, install lightweight mock stubs in sys.modules
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")

    # core
    core = types.ModuleType("homeassistant.core")
    class HomeAssistant:
        pass
    class ServiceCall:
        pass
    def callback(func):
        return func
    core.HomeAssistant = HomeAssistant
    core.ServiceCall = ServiceCall
    core.callback = callback
    ha.core = core
    sys.modules["homeassistant.core"] = core

    # const
    const = types.ModuleType("homeassistant.const")
    const.STATE_OFF = "off"
    const.STATE_ON = "on"
    class EntityCategory:
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"
    const.EntityCategory = EntityCategory
    ha.const = const
    sys.modules["homeassistant.const"] = const

    # config_entries
    config_entries = types.ModuleType("homeassistant.config_entries")
    class ConfigEntry:
        pass
    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls._domain = domain
        async def async_set_unique_id(self, unique_id, raise_on_progress=True):
            self.unique_id = unique_id
        def _abort_if_unique_id_configured(self, updates=None, error="already_configured"):
            pass
        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors, "description_placeholders": description_placeholders}
        def async_create_entry(self, *, title, data, options=None):
            return {"type": "create_entry", "title": title, "data": data, "options": options}
        def async_abort(self, *, reason, description_placeholders=None):
            return {"type": "abort", "reason": reason, "description_placeholders": description_placeholders}
    class OptionsFlow:
        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors, "description_placeholders": description_placeholders}
        def async_create_entry(self, *, title="", data=None):
            return {"type": "create_entry", "title": title, "data": data or {}}
    ConfigFlowResult = dict
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    config_entries.ConfigFlowResult = ConfigFlowResult
    ha.config_entries = config_entries
    sys.modules["homeassistant.config_entries"] = config_entries

    # data_entry_flow
    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    FlowResult = dict
    data_entry_flow.FlowResult = FlowResult
    ha.data_entry_flow = data_entry_flow
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow

    # components
    components = types.ModuleType("homeassistant.components")

    # media_player
    media_player = types.ModuleType("homeassistant.components.media_player")
    class MediaPlayerEntity:
        def schedule_update_ha_state(self): pass
        def async_write_ha_state(self): pass
    class MediaPlayerEntityFeature:
        PAUSE = 1
        SEEK = 2
        VOLUME_SET = 4
        VOLUME_MUTE = 8
        PREVIOUS_TRACK = 16
        NEXT_TRACK = 32
        TURN_ON = 128
        TURN_OFF = 256
        PLAY_MEDIA = 512
        VOLUME_STEP = 1024
        SELECT_SOURCE = 2048
        STOP = 4096
        PLAY = 16384
    media_player.MediaPlayerEntity = MediaPlayerEntity
    media_player.MediaPlayerEntityFeature = MediaPlayerEntityFeature
    components.media_player = media_player
    sys.modules["homeassistant.components.media_player"] = media_player

    # remote
    remote = types.ModuleType("homeassistant.components.remote")
    class RemoteEntity:
        def schedule_update_ha_state(self): pass
        def async_write_ha_state(self): pass
    remote.RemoteEntity = RemoteEntity
    components.remote = remote
    sys.modules["homeassistant.components.remote"] = remote

    # sensor
    sensor = types.ModuleType("homeassistant.components.sensor")
    class SensorEntity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def async_write_ha_state(self): pass
        @property
        def native_value(self):
            return getattr(self, "_attr_native_value", None)
        @property
        def extra_state_attributes(self):
            return getattr(self, "_attr_extra_state_attributes", {})
    class SensorDeviceClass:
        TIMESTAMP = "timestamp"
        ENUM = "enum"
    sensor.SensorEntity = SensorEntity
    sensor.SensorDeviceClass = SensorDeviceClass
    components.sensor = sensor
    sys.modules["homeassistant.components.sensor"] = sensor

    # binary_sensor
    binary_sensor = types.ModuleType("homeassistant.components.binary_sensor")
    class BinarySensorEntity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def async_write_ha_state(self): pass
        @property
        def is_on(self):
            return getattr(self, "_attr_is_on", None)
    class BinarySensorDeviceClass:
        CONNECTIVITY = "connectivity"
    binary_sensor.BinarySensorEntity = BinarySensorEntity
    binary_sensor.BinarySensorDeviceClass = BinarySensorDeviceClass
    components.binary_sensor = binary_sensor
    sys.modules["homeassistant.components.binary_sensor"] = binary_sensor

    # button
    button = types.ModuleType("homeassistant.components.button")
    class ButtonEntity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def async_write_ha_state(self): pass
    class ButtonDeviceClass:
        RESTART = "restart"
        UPDATE = "update"
    button.ButtonEntity = ButtonEntity
    button.ButtonDeviceClass = ButtonDeviceClass
    components.button = button
    sys.modules["homeassistant.components.button"] = button

    # repairs
    repairs = types.ModuleType("homeassistant.components.repairs")
    class RepairsFlow:
        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors, "description_placeholders": description_placeholders}
        def async_create_entry(self, *, data=None):
            return {"type": "create_entry", "data": data or {}}
    repairs.RepairsFlow = RepairsFlow
    components.repairs = repairs
    sys.modules["homeassistant.components.repairs"] = repairs

    # diagnostics
    diagnostics = types.ModuleType("homeassistant.components.diagnostics")
    def async_redact_data(data, to_redact):
        if isinstance(data, dict):
            return {k: ("**REDACTED**" if k in to_redact else async_redact_data(v, to_redact)) for k, v in data.items()}
        return data
    diagnostics.async_redact_data = async_redact_data
    components.diagnostics = diagnostics
    sys.modules["homeassistant.components.diagnostics"] = diagnostics

    ha.components = components
    sys.modules["homeassistant.components"] = components

    # helpers
    helpers = types.ModuleType("homeassistant.helpers")

    # helpers.device_registry
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
    def format_mac(mac: str) -> str:
        clean = mac.replace("-", ":").lower()
        parts = clean.split(":")
        return ":".join(f"{p:>02}" for p in parts)
    device_registry.DeviceInfo = DeviceInfo
    device_registry.CONNECTION_NETWORK_MAC = "mac"
    device_registry.format_mac = format_mac
    helpers.device_registry = device_registry
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    # helpers.entity_platform
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    AddEntitiesCallback = MagicMock
    entity_platform.AddEntitiesCallback = AddEntitiesCallback
    helpers.entity_platform = entity_platform
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    # helpers.issue_registry
    issue_registry = types.ModuleType("homeassistant.helpers.issue_registry")
    class IssueSeverity:
        CRITICAL = "critical"
        ERROR = "error"
        WARNING = "warning"
    def async_create_issue(*args, **kwargs): pass
    def async_delete_issue(*args, **kwargs): pass
    issue_registry.IssueSeverity = IssueSeverity
    issue_registry.async_create_issue = async_create_issue
    issue_registry.async_delete_issue = async_delete_issue
    helpers.issue_registry = issue_registry
    sys.modules["homeassistant.helpers.issue_registry"] = issue_registry

    # helpers.config_validation
    cv = types.ModuleType("homeassistant.helpers.config_validation")
    def config_entry_only_config_schema(domain):
        return lambda val: val
    def empty_config_schema(domain):
        return lambda val: val
    cv.config_entry_only_config_schema = config_entry_only_config_schema
    cv.empty_config_schema = empty_config_schema
    helpers.config_validation = cv
    sys.modules["homeassistant.helpers.config_validation"] = cv

    # helpers.service_info.ssdp
    service_info = types.ModuleType("homeassistant.helpers.service_info")
    ssdp = types.ModuleType("homeassistant.helpers.service_info.ssdp")
    class SsdpServiceInfo:
        def __init__(self, ssdp_usn=None, ssdp_st=None, ssdp_location=None, ssdp_headers=None, upnp=None, ssdp_udn=None):
            self.ssdp_usn = ssdp_usn
            self.ssdp_st = ssdp_st
            self.ssdp_location = ssdp_location
            self.ssdp_headers = ssdp_headers or {}
            self.upnp = upnp or {}
            self.ssdp_udn = ssdp_udn
    ssdp.SsdpServiceInfo = SsdpServiceInfo
    service_info.ssdp = ssdp
    sys.modules["homeassistant.helpers.service_info.ssdp"] = ssdp

    # helpers.service_info.zeroconf
    zeroconf_info = types.ModuleType("homeassistant.helpers.service_info.zeroconf")
    class ZeroconfServiceInfo:
        def __init__(self, host=None, port=None, hostname=None, type=None, name=None, properties=None):
            self.host = host
            self.port = port
            self.hostname = hostname
            self.type = type
            self.name = name
            self.properties = properties or {}
    zeroconf_info.ZeroconfServiceInfo = ZeroconfServiceInfo
    service_info.zeroconf = zeroconf_info
    sys.modules["homeassistant.helpers.service_info.zeroconf"] = zeroconf_info

    # helpers.selector
    selector_mod = types.ModuleType("homeassistant.helpers.selector")
    class SelectSelector:
        def __init__(self, config=None):
            self.config = config
        def __call__(self, val):
            return val
    class SelectSelectorConfig:
        def __init__(self, options=None, mode=None, translation_key=None):
            self.options = options
            self.mode = mode
            self.translation_key = translation_key
    class SelectSelectorMode:
        DROPDOWN = "dropdown"
        LIST = "list"
    class SelectOptionDict(dict):
        def __init__(self, value, label):
            super().__init__(value=value, label=label)
    selector_mod.SelectSelector = SelectSelector
    selector_mod.SelectSelectorConfig = SelectSelectorConfig
    selector_mod.SelectSelectorMode = SelectSelectorMode
    selector_mod.SelectOptionDict = SelectOptionDict
    helpers.selector = selector_mod
    sys.modules["homeassistant.helpers.selector"] = selector_mod

    helpers.service_info = service_info
    sys.modules["homeassistant.helpers.service_info"] = service_info

    ha.helpers = helpers
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant"] = ha


class MockMQTTMessage:
    """Mock paho-mqtt message object."""

    def __init__(self, topic: str, payload: bytes | str):
        self.topic = topic
        self.payload = payload.encode("utf-8") if isinstance(payload, str) else payload


@pytest.fixture
def mock_mqtt_message():
    """Factory fixture to create mock MQTT messages."""
    def _create(topic: str, payload: str | bytes):
        return MockMQTTMessage(topic, payload)
    return _create


@pytest.fixture
def mock_paho_client(monkeypatch):
    """Mocks paho.mqtt.client.Client with simulated broker responses."""
    mock_client_instance = MagicMock()
    mock_client_instance.connect_async.return_value = 0
    mock_client_instance.disconnect.return_value = 0
    mock_client_instance.publish.return_value = (0, 1)
    mock_client_instance.subscribe.return_value = (0, 1)

    mock_client_class = MagicMock(return_value=mock_client_instance)
    monkeypatch.setattr("paho.mqtt.client.Client", mock_client_class)
    return mock_client_instance
