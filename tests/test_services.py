"""Tests for Hisense VIDAA custom integration services."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.hisense_vidaa import async_setup
from custom_components.hisense_vidaa.const import (
    ATTR_ACTION,
    ATTR_APP,
    ATTR_DELAY,
    ATTR_KEY,
    ATTR_MENU_ID,
    ATTR_MENU_VALUE,
    ATTR_REPEAT,
    ATTR_TEXT,
    DOMAIN,
    SERVICE_LAUNCH_APP,
    SERVICE_SEND_KEY,
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

    def mock_async_register(domain, service, handler):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
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
    await registered_services[f"{DOMAIN}.{SERVICE_SEND_KEY}"](call_send_key)
    assert mock_client.send_command.call_count == 2
    mock_client.send_command.assert_called_with("KEY_POWER")


@pytest.mark.anyio
async def test_launch_app_service_matching():
    """Test launch_app service with app dictionary matching."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
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
    await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_yt)
    mock_client.launch_app.assert_called_with("youtube_app_01", "YouTube", "https://youtube.com/tv")

    # Match by appName
    call_netflix = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={ATTR_APP: "NETFLIX"},
    )
    await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_netflix)
    mock_client.launch_app.assert_called_with("netflix_app_02", "Netflix", "netflix://")

    # Fallback when app not in cached app list
    call_unknown = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_LAUNCH_APP,
        data={ATTR_APP: "CustomApp"},
    )
    await registered_services[f"{DOMAIN}.{SERVICE_LAUNCH_APP}"](call_unknown)
    mock_client.launch_app.assert_called_with("", "CustomApp", "CustomApp")


@pytest.mark.anyio
async def test_picture_sound_and_text_input_services():
    """Test set_picture_setting, set_sound_setting, and send_text_input services."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    registered_services = {}

    def mock_async_register(domain, service, handler):
        registered_services[f"{domain}.{service}"] = handler

    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock(side_effect=mock_async_register)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))

    mock_client = MagicMock()
    hass.data[DOMAIN] = {"entry_1": {"client": mock_client}}

    await async_setup(hass, {})

    # Picture setting
    call_pic = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SET_PICTURE_SETTING,
        data={ATTR_MENU_ID: "picture_mode", ATTR_MENU_VALUE: "Cinema Night"},
    )
    await registered_services[f"{DOMAIN}.{SERVICE_SET_PICTURE_SETTING}"](call_pic)
    mock_client.set_picture_setting.assert_called_with("picture_mode", "Cinema Night")

    # Sound setting
    call_snd = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SET_SOUND_SETTING,
        data={ATTR_MENU_ID: "sound_mode", ATTR_MENU_VALUE: "Theater"},
    )
    await registered_services[f"{DOMAIN}.{SERVICE_SET_SOUND_SETTING}"](call_snd)
    mock_client.set_sound_setting.assert_called_with("sound_mode", "Theater")

    # Text input
    call_txt = ServiceCall(
        domain=DOMAIN,
        service=SERVICE_SEND_TEXT_INPUT,
        data={ATTR_TEXT: "hello world", ATTR_ACTION: "insert"},
    )
    await registered_services[f"{DOMAIN}.{SERVICE_SEND_TEXT_INPUT}"](call_txt)
    mock_client.send_text_input.assert_called_with("hello world", "insert")


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

