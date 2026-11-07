"""Pytest fixtures and mock Home Assistant environment for Hisense VIDAA test suite."""

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

# Ensure repository root is in Python path for test execution
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(TEST_DIR)

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

@pytest.fixture
def anyio_backend():
    return "asyncio"

# Mock voluptuous if not installed
try:
    import voluptuous as vol
except ImportError:
    vol = types.ModuleType("voluptuous")
    class Schema:
        def __init__(self, schema):
            self.schema = schema
        def __call__(self, val):
            return val
    class Invalid(Exception):
        pass
    class All:
        def __init__(self, *validators):
            self.validators = validators
        def __call__(self, val):
            return val
    def Required(key, default=None): return key
    def Optional(key, default=None): return key
    def In(container): return lambda x: x
    def Any(*validators): return validators[0] if validators else None
    class Coerce:
        def __init__(self, target):
            self.type = target
        def __call__(self, value):
            return self.type(value)
    vol.Schema = Schema
    vol.Invalid = Invalid
    vol.All = All
    vol.Required = Required
    vol.Optional = Optional
    vol.In = In
    vol.Any = Any
    vol.Coerce = Coerce
    sys.modules["voluptuous"] = vol

# Mock aiohttp if not installed
try:
    import aiohttp
except ImportError:
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class ClientSession:
        def __init__(self, *args, **kwargs):
            self.closed = False

        async def close(self):
            self.closed = True

    class ClientTimeout:
        def __init__(self, total=None):
            self.total = total

    aiohttp.ClientError = ClientError
    aiohttp.ClientSession = ClientSession
    aiohttp.ClientTimeout = ClientTimeout
    sys.modules["aiohttp"] = aiohttp

# If homeassistant is not installed, install lightweight mock stubs in sys.modules
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")

    # core
    core = types.ModuleType("homeassistant.core")
    class HomeAssistant:
        config_entries = None
        services = None
        data = None
        loop = None

        def async_create_background_task(self, target, name=None):
            if hasattr(target, "close"):
                target.close()
            return None

        def async_create_task(self, target, name=None):
            return None

        def async_add_executor_job(self, target, *args):
            return None

        def __init__(self):
            self.config_entries = MagicMock()
            self.services = MagicMock()
            self.data = {}
    class ServiceCall:
        def __init__(self, domain=None, service=None, data=None, context=None):
            self.domain = domain
            self.service = service
            self.data = data or {}
            self.context = context
    class SupportsResponse:
        NONE = "none"
        ONLY = "only"
        OPTIONAL = "optional"
    def callback(func):
        return func
    core.HomeAssistant = HomeAssistant
    core.ServiceCall = ServiceCall
    core.SupportsResponse = SupportsResponse
    core.callback = callback
    core.CALLBACK_TYPE = MagicMock
    core.Context = MagicMock
    ha.core = core
    sys.modules["homeassistant.core"] = core


    # const
    const = types.ModuleType("homeassistant.const")
    const.STATE_OFF = "off"
    const.STATE_ON = "on"
    const.ATTR_DEVICE_ID = "device_id"
    const.ATTR_ENTITY_ID = "entity_id"
    const.CONF_DEVICE_ID = "device_id"
    const.CONF_DOMAIN = "domain"
    const.CONF_OPTIONS = "options"
    const.CONF_PLATFORM = "platform"
    const.CONF_TYPE = "type"
    class EntityCategory:
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"
    const.EntityCategory = EntityCategory
    class UnitOfTime:
        SECONDS = "s"
        MINUTES = "min"
        HOURS = "h"
        DAYS = "d"
    const.UnitOfTime = UnitOfTime
    ha.const = const
    sys.modules["homeassistant.const"] = const

    # config_entries
    config_entries = types.ModuleType("homeassistant.config_entries")
    class ConfigEntryState:
        LOADED = "loaded"
        SETUP_ERROR = "setup_error"
        NOT_LOADED = "not_loaded"
    class ConfigEntry:
        def async_on_unload(self, func):
            pass
        def add_update_listener(self, listener):
            return lambda: None
        def async_start_reauth(self, hass):
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
        def async_show_menu(self, *, step_id, menu_options):
            return {"type": "menu", "step_id": step_id, "menu_options": menu_options}
        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors, "description_placeholders": description_placeholders}
        def async_create_entry(self, *, title="", data=None):
            return {"type": "create_entry", "title": title, "data": data or {}}
    ConfigFlowResult = dict
    config_entries.ConfigEntryState = ConfigEntryState
    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
    config_entries.ConfigFlowResult = ConfigFlowResult
    ha.config_entries = config_entries
    sys.modules["homeassistant.config_entries"] = config_entries

    # data_entry_flow
    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    FlowResult = dict
    class AbortFlow(Exception):
        """HA flow-control exception raised by _abort_if_unique_id_configured etc."""
        def __init__(self, reason: str) -> None:
            super().__init__(reason)
            self.reason = reason
    data_entry_flow.FlowResult = FlowResult
    data_entry_flow.AbortFlow = AbortFlow
    ha.data_entry_flow = data_entry_flow
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow

    # exceptions
    exceptions = types.ModuleType("homeassistant.exceptions")
    class HomeAssistantError(Exception):
        def __init__(self, message=None, *, translation_domain=None, translation_key=None, translation_placeholders=None):
            super().__init__(message)
            self.message = message
            self.translation_domain = translation_domain
            self.translation_key = translation_key
            self.translation_placeholders = translation_placeholders
    class ConfigEntryNotReady(HomeAssistantError):
        pass
    class ServiceValidationError(HomeAssistantError):
        pass
    exceptions.HomeAssistantError = HomeAssistantError
    exceptions.ConfigEntryNotReady = ConfigEntryNotReady
    exceptions.ServiceValidationError = ServiceValidationError
    ha.exceptions = exceptions
    sys.modules["homeassistant.exceptions"] = exceptions

    # components
    components = types.ModuleType("homeassistant.components")

    # media_player
    media_player = types.ModuleType("homeassistant.components.media_player")
    class MediaPlayerDeviceClass:
        TV = "tv"
        RECEIVER = "receiver"
        SPEAKER = "speaker"
    class MediaPlayerEntity:
        _attr_device_class = None
        @property
        def device_class(self):
            return getattr(self, "_attr_device_class", None)
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
        SELECT_SOUND_MODE = 65536
    class MediaType:
        CHANNEL = "channel"
        APP = "app"
        URL = "url"
        MUSIC = "music"
        VIDEO = "video"
        TVSHOW = "tvshow"
    media_player.MediaType = MediaType
    media_player.MediaPlayerEntity = MediaPlayerEntity
    media_player.MediaPlayerDeviceClass = MediaPlayerDeviceClass
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
        DURATION = "duration"
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
        RUNNING = "running"
        POWER = "power"
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

    # notify
    notify = types.ModuleType("homeassistant.components.notify")
    class NotifyEntity:
        _attr_has_entity_name = True
        def async_write_ha_state(self): pass
    notify.NotifyEntity = NotifyEntity
    components.notify = notify
    sys.modules["homeassistant.components.notify"] = notify

    # switch
    switch = types.ModuleType("homeassistant.components.switch")
    class SwitchEntity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def schedule_update_ha_state(self): pass
        def async_write_ha_state(self): pass
        @property
        def is_on(self):
            return getattr(self, "_attr_is_on", False)
    class SwitchDeviceClass:
        SWITCH = "switch"
    switch.SwitchEntity = SwitchEntity
    switch.SwitchDeviceClass = SwitchDeviceClass
    components.switch = switch
    sys.modules["homeassistant.components.switch"] = switch

    # select
    select = types.ModuleType("homeassistant.components.select")
    class SelectEntity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def schedule_update_ha_state(self): pass
        def async_write_ha_state(self): pass
        @property
        def current_option(self):
            return getattr(self, "_attr_current_option", None)
        @property
        def options(self):
            return getattr(self, "_attr_options", [])
    select.SelectEntity = SelectEntity
    components.select = select
    sys.modules["homeassistant.components.select"] = select

    # number
    number = types.ModuleType("homeassistant.components.number")
    class NumberMode:
        AUTO = "auto"
        BOX = "box"
        SLIDER = "slider"
    class NumberEntity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def schedule_update_ha_state(self): pass
        def async_write_ha_state(self): pass
        @property
        def native_value(self):
            return getattr(self, "_attr_native_value", None)
        @property
        def native_min_value(self):
            return getattr(self, "_attr_native_min_value", 0.0)
        @property
        def native_max_value(self):
            return getattr(self, "_attr_native_max_value", 100.0)
        @property
        def native_step(self):
            return getattr(self, "_attr_native_step", 1.0)
        @property
        def mode(self):
            return getattr(self, "_attr_mode", NumberMode.AUTO)
    number.NumberEntity = NumberEntity
    number.NumberMode = NumberMode
    components.number = number
    sys.modules["homeassistant.components.number"] = number

    # device_automation
    device_automation = types.ModuleType("homeassistant.components.device_automation")
    class InvalidDeviceAutomationConfig(Exception):
        def __init__(self, *args, **kwargs):
            super().__init__(*args)
            self.kwargs = kwargs
    DEVICE_TRIGGER_BASE_SCHEMA = vol.Schema({
        vol.Required("platform"): "device",
        vol.Required("domain"): str,
        vol.Required("device_id"): str,
    })
    device_automation.InvalidDeviceAutomationConfig = InvalidDeviceAutomationConfig
    device_automation.DEVICE_TRIGGER_BASE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA
    components.device_automation = device_automation
    sys.modules["homeassistant.components.device_automation"] = device_automation

    ha.components = components
    sys.modules["homeassistant.components"] = components

    # helpers
    helpers = types.ModuleType("homeassistant.helpers")

    # helpers.entity
    entity_module = types.ModuleType("homeassistant.helpers.entity")
    class Entity:
        _attr_has_entity_name = True
        _attr_should_poll = False
        def schedule_update_ha_state(self): pass
        def async_write_ha_state(self): pass
        def async_on_remove(self, func): pass
        @property
        def unique_id(self):
            return getattr(self, "_attr_unique_id", None)
        @property
        def entity_registry_enabled_default(self):
            return getattr(self, "_attr_entity_registry_enabled_default", True)
    entity_module.Entity = Entity
    helpers.entity = entity_module
    sys.modules["homeassistant.helpers.entity"] = entity_module

    # helpers.selector
    selector = types.ModuleType("homeassistant.helpers.selector")
    class NumberSelector:
        def __init__(self, config): self.config = config
        def __call__(self, data): return data
    class NumberSelectorConfig:
        def __init__(self, **kwargs): self.config = kwargs
    class NumberSelectorMode:
        SLIDER = "slider"
        BOX = "box"
    class SelectSelector:
        def __init__(self, config): self.config = config
        def __call__(self, data): return data
    class SelectSelectorConfig:
        def __init__(self, **kwargs): self.config = kwargs
    class SelectSelectorMode:
        DROPDOWN = "dropdown"
    class SelectOptionDict(dict):
        def __init__(self, value, label): super().__init__(value=value, label=label)
    selector.NumberSelector = NumberSelector
    selector.NumberSelectorConfig = NumberSelectorConfig
    selector.NumberSelectorMode = NumberSelectorMode
    selector.SelectSelector = SelectSelector
    selector.SelectSelectorConfig = SelectSelectorConfig
    selector.SelectSelectorMode = SelectSelectorMode
    selector.SelectOptionDict = SelectOptionDict
    helpers.selector = selector
    sys.modules["homeassistant.helpers.selector"] = selector

    # helpers.device_registry
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
    def format_mac(mac: str) -> str:
        clean = mac.replace("-", ":").lower()
        parts = clean.split(":")
        return ":".join(f"{p:>02}" for p in parts)
    class DeviceEntry:
        def __init__(self, id="test_device_id", name="Hisense TV", name_by_user=None, config_entries=None):
            self.id = id
            self.name = name
            self.name_by_user = name_by_user
            self.config_entries = config_entries or []
    device_registry.DeviceEntry = DeviceEntry
    device_registry.DeviceInfo = DeviceInfo
    device_registry.CONNECTION_NETWORK_MAC = "mac"
    device_registry.format_mac = format_mac
    device_registry.async_get = MagicMock()
    helpers.device_registry = device_registry
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    # helpers.entity_platform
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    AddEntitiesCallback = MagicMock
    entity_platform.AddEntitiesCallback = AddEntitiesCallback
    helpers.entity_platform = entity_platform
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    # helpers.entity_registry
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    def async_get(hass):
        return MagicMock()
    entity_registry.async_get = async_get
    helpers.entity_registry = entity_registry
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry

    # helpers.area_registry
    area_registry = types.ModuleType("homeassistant.helpers.area_registry")
    area_registry.async_get = MagicMock()
    helpers.area_registry = area_registry
    sys.modules["homeassistant.helpers.area_registry"] = area_registry

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
    def ensure_list(val):
        return val if isinstance(val, list) else [val]
    cv.config_entry_only_config_schema = config_entry_only_config_schema
    cv.empty_config_schema = empty_config_schema
    cv.ensure_list = ensure_list
    cv.entity_ids = lambda val: val
    cv.string = lambda val: str(val)
    helpers.config_validation = cv
    sys.modules["homeassistant.helpers.config_validation"] = cv

    # helpers.typing
    typing_mod = types.ModuleType("homeassistant.helpers.typing")
    typing_mod.ConfigType = dict
    helpers.typing = typing_mod
    sys.modules["homeassistant.helpers.typing"] = typing_mod

    # helpers.automation
    automation_mod = types.ModuleType("homeassistant.helpers.automation")
    def move_top_level_schema_fields_to_options(complete_config, schema_dict):
        return complete_config
    automation_mod.move_top_level_schema_fields_to_options = move_top_level_schema_fields_to_options
    helpers.automation = automation_mod
    sys.modules["homeassistant.helpers.automation"] = automation_mod

    # helpers.trigger
    trigger_mod = types.ModuleType("homeassistant.helpers.trigger")
    DATA_PLUGGABLE_ACTIONS = "pluggable_actions"
    class Trigger:
        def __init__(self, hass, config):
            self._hass = hass
            self._config = config
        @classmethod
        async def async_validate_complete_config(cls, hass, config):
            return config
        @classmethod
        async def async_validate_config(cls, hass, config):
            return config
        async def async_attach_runner(self, run_action, did_not_trigger=None):
            return lambda: None

    class TriggerConfig:
        def __init__(self, options=None):
            self.options = options or {}

    class PluggableAction:
        def __init__(self, update=None):
            self._update = update
            self._registered_key = None
            self._hass = None

        def __bool__(self):
            if not self._hass or not self._registered_key:
                return False
            reg = self._hass.data.get(DATA_PLUGGABLE_ACTIONS, {})
            entry = reg.get(self._registered_key)
            return bool(entry and entry.get("actions"))

        def async_run_update(self):
            if self._update:
                self._update()

        @staticmethod
        def async_attach_trigger(hass, trigger, action, variables):
            reg = hass.data.setdefault(DATA_PLUGGABLE_ACTIONS, {})
            key = tuple(sorted(trigger.items()))
            entry = reg.setdefault(key, {"actions": []})
            action_item = (action, variables)
            entry["actions"].append(action_item)
            def _remove():
                if action_item in entry["actions"]:
                    entry["actions"].remove(action_item)
            return _remove

        def async_register(self, hass, trigger):
            self._hass = hass
            self._registered_key = tuple(sorted(trigger.items()))
            reg = hass.data.setdefault(DATA_PLUGGABLE_ACTIONS, {})
            reg.setdefault(self._registered_key, {"actions": []})
            def _remove():
                self._registered_key = None
            return _remove

        async def async_run(self, hass, context=None):
            if not self._registered_key:
                return
            reg = hass.data.get(DATA_PLUGGABLE_ACTIONS, {})
            entry = reg.get(self._registered_key)
            if entry and entry.get("actions"):
                import asyncio
                for action, variables in list(entry["actions"]):
                    try:
                        res = action(variables, context)
                    except TypeError:
                        res = action(variables)
                    if asyncio.iscoroutine(res):
                        await res

    trigger_mod.Trigger = Trigger
    trigger_mod.TriggerConfig = TriggerConfig
    trigger_mod.TriggerActionRunner = MagicMock
    trigger_mod.TriggerNotTriggeredReporter = MagicMock
    trigger_mod.TriggerActionType = MagicMock
    trigger_mod.TriggerInfo = MagicMock
    trigger_mod.PluggableAction = PluggableAction
    helpers.trigger = trigger_mod
    sys.modules["homeassistant.helpers.trigger"] = trigger_mod

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
        def __init__(self, host=None, port=None, hostname=None, type=None, name=None, properties=None, ip_address=None, ip_addresses=None):
            self.host = host or ip_address
            self.port = port
            self.hostname = hostname
            self.type = type
            self.name = name
            self.properties = properties or {}
            self.ip_address = ip_address or host
            self.ip_addresses = ip_addresses or ([self.ip_address] if self.ip_address else [])
    zeroconf_info.ZeroconfServiceInfo = ZeroconfServiceInfo
    service_info.zeroconf = zeroconf_info
    sys.modules["homeassistant.helpers.service_info.zeroconf"] = zeroconf_info

    helpers.service_info = service_info
    sys.modules["homeassistant.helpers.service_info"] = service_info

    # helpers.event
    event = types.ModuleType("homeassistant.helpers.event")
    def async_track_time_interval(hass, action, interval):
        return lambda: None
    event.async_track_time_interval = async_track_time_interval
    helpers.event = event
    sys.modules["homeassistant.helpers.event"] = event

    # helpers.aiohttp_client
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    def async_get_clientsession(hass=None, verify_ssl=True):
        return MagicMock()
    aiohttp_client.async_get_clientsession = async_get_clientsession
    helpers.aiohttp_client = aiohttp_client
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

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


@pytest.fixture(autouse=True)
def isolate_host_network_environment(monkeypatch):
    """Ensures test suite does not query real host ARP tables or network devices by default."""
    import os

    real_exists = os.path.exists

    def mock_exists(path):
        if path == "/proc/net/arp":
            return False
        return real_exists(path)

    monkeypatch.setattr("os.path.exists", mock_exists)


@pytest.fixture
def mock_entry(mock_client):
    from types import SimpleNamespace

    from homeassistant.config_entries import ConfigEntry
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.title = "Living Room TV"
    entry.data = {
        "ip_address": "192.168.50.12",
        "mac_address": "e8:51:77:ec:98:1c",
        "auth_profile": "modern",
        "model": "65U7G",
        "manufacturer": "Hisense",
        "sw_version": "V1.0",
    }
    entry.options = {"enable_remote": True, "enable_wol": True}
    entry.runtime_data = SimpleNamespace(
        client=mock_client,
        platforms=[],
        options=entry.options,
    )
    return entry


@pytest.fixture
def mock_client():
    from unittest.mock import AsyncMock

    from custom_components.hisense_vidaa.tv.actions import turn_off_tv, turn_on_tv

    client = MagicMock()
    client.ip = "192.168.50.12"
    client.connected = True
    client.is_on = True
    client.auth_profile = "modern"
    client.access_token_time = 1700000000
    client.access_token_duration = 3600
    client.refresh_token_time = 1700000000
    client.refresh_token_duration = 86400
    client.current_app = "Netflix"
    client.source = "HDMI 1"
    client.tv_state = "on"
    client.device_name = None
    client.model_name = None
    client.manufacturer = None
    client.firmware_version = None
    client.clock_offset = 0
    client.last_clock_sync = 0.0
    client.tv_timestamp = None
    client.picture_settings = []
    client.sound_settings = []
    client.has_active_signal = False
    client.sync_clock = MagicMock(return_value=0)
    client.async_sync_clock = AsyncMock(return_value=0)
    client.async_connect_and_run = AsyncMock()
    client.async_disconnect = AsyncMock()
    client.async_check_and_refresh_token = AsyncMock(return_value=False)
    client.async_query_initial_state = AsyncMock()
    client.async_turn_on = AsyncMock()
    client.async_turn_off = AsyncMock()
    client.async_set_volume = AsyncMock()
    client.async_send_key = AsyncMock()
    client.async_send_command = AsyncMock(return_value=True)
    client.async_set_sound_mode = AsyncMock()
    client.async_set_picture_mode = AsyncMock()
    client.async_set_backlight = AsyncMock()
    client.async_set_brightness = AsyncMock()
    client.async_set_contrast = AsyncMock()
    client.async_set_picture_setting = AsyncMock()
    client.async_set_sound_setting = AsyncMock()
    client.async_send_text_input = AsyncMock()
    client.async_show_message = AsyncMock(return_value=True)
    client.async_launch_app = AsyncMock()
    client.async_get_picture_settings = AsyncMock()
    client.async_get_sound_settings = AsyncMock()
    client.async_get_device_fingerprint = AsyncMock(return_value={})
    client.async_turn_on.side_effect = lambda *a, **k: client.turn_on(*a, **k)
    client.async_turn_off.side_effect = lambda *a, **k: client.turn_off(*a, **k)
    client.async_set_volume.side_effect = lambda *a, **k: client.set_volume(*a, **k)
    client.async_send_key.side_effect = lambda *a, **k: client.send_key(*a, **k)
    client.async_send_command.side_effect = lambda *a, **k: client.send_command(*a, **k) or True
    client.async_set_sound_mode.side_effect = lambda *a, **k: client.set_sound_mode(*a, **k)
    client.async_set_picture_mode.side_effect = lambda *a, **k: client.set_picture_mode(*a, **k)
    client.async_set_backlight.side_effect = lambda *a, **k: client.set_backlight(*a, **k)
    client.async_set_brightness.side_effect = lambda *a, **k: client.set_brightness(*a, **k)
    client.async_set_contrast.side_effect = lambda *a, **k: client.set_contrast(*a, **k)
    client.async_set_picture_setting.side_effect = lambda *a, **k: client.set_picture_setting(*a, **k)
    client.async_set_sound_setting.side_effect = lambda *a, **k: client.set_sound_setting(*a, **k)
    client.async_send_text_input.side_effect = lambda *a, **k: client.send_text_input(*a, **k)
    client.async_show_message.side_effect = lambda *a, **k: client.show_message(*a, **k) or True
    client.async_launch_app.side_effect = lambda *a, **k: client.launch_app(*a, **k)
    client.async_change_source = AsyncMock(side_effect=lambda *a, **k: client.change_source(*a, **k))
    client.async_cycle_source = AsyncMock(side_effect=lambda *a, **k: client.cycle_source(*a, **k))
    client.async_disconnect.side_effect = lambda *a, **k: client.disconnect(*a, **k)
    client.async_connect_and_run.side_effect = lambda *a, **k: client.connect_and_run(*a, **k)
    client.async_sync_clock.side_effect = lambda *a, **k: client.sync_clock(*a, **k) or 0
    client.async_get_device_fingerprint.side_effect = lambda *a, **k: client.get_device_fingerprint(*a, **k) or {}
    client.async_check_and_refresh_token.side_effect = lambda *a, **k: client.check_and_refresh_token(*a, **k) or False
    client.turn_on.side_effect = lambda mac_targets=None: turn_on_tv(client, mac_targets)
    client.turn_off.side_effect = lambda: turn_off_tv(client)
    return client


