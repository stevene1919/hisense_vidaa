"""Tests for static-session PIN pairing, dispatcher future routing and flow guards.

Covers the campaign fixes:
  * PIN pairing over a STATIC session (gettvstate -> authentication challenge ->
    authNum submit) without regressing already-paired setups;
  * F3-leg3  dispatcher: the vidaa_app_connect ACK must not resolve the PIN future;
  * F10-leg3 dispatcher: exact topic matches for the pairing close/toast pushes;
  * F1-leg2  flows must not swallow HA's AbortFlow;
  * F2-leg2  duplicate guard runs before (and scopes) the sibling disconnect;
  * F9-leg6  only the PIN submit call is guarded in async_step_auth;
  * F10-leg6 async_remove keeps + logs the executor future.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.config_flow import HisenseVidaaConfigFlow
from custom_components.hisense_vidaa.protocol.dispatcher import dispatch_incoming_mqtt_message
from custom_components.hisense_vidaa.protocol.pairing import (
    PairingStatusError,
    _async_execute_pairing_attempt,
    async_probe_pairing_challenge,
    async_submit_pin_code,
)

PROBE_PATH = "custom_components.hisense_vidaa.config_flow.async_probe_pairing_challenge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _static_client() -> HisenseTvClient:
    """A static-session (legacy) client with its topic paths defined."""
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="legacy")
    client.client_id = "hisenseservice"
    client.username = "hisenseservice"
    client.password = "multimqttservice"
    client.define_topic_paths()
    return client


def _hass() -> MagicMock:
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.data = {}
    return hass


def _flow(hass: MagicMock, *, profile: str = "legacy") -> HisenseVidaaConfigFlow:
    flow = HisenseVidaaConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.ip_address = "192.168.50.12"
    flow.mac_address = "e8:51:77:ec:98:1c"
    flow.auth_profile = profile
    flow.async_set_unique_id = AsyncMock(return_value=None)
    flow._abort_if_unique_id_configured = MagicMock()
    return flow


@pytest.fixture
def no_network_start_auth(monkeypatch):
    """Keep the flow's client construction offline."""
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_start_auth",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.get_device_fingerprint",
        MagicMock(return_value={}),
    )


# ---------------------------------------------------------------------------
# F3-leg3 / F10-leg3: dispatcher future routing
# ---------------------------------------------------------------------------
def test_dispatcher_connect_ack_does_not_resolve_pin_future():
    """The vidaa_app_connect ACK is NOT the PIN-shown signal."""
    client = _static_client()
    loop = asyncio.new_event_loop()
    try:
        client._auth_future = loop.create_future()
        client._connect_ack_future = loop.create_future()
        dispatch_incoming_mqtt_message(
            client,
            client.topicMobiBasepath + "ui_service/data/vidaa_app_connect",
            '{"connect_result":1}',
        )
        assert not client._auth_future.done(), "connect-ACK must not resolve the PIN future"
        assert client._connect_ack_future.done(), "connect-ACK is tracked on its own future"
    finally:
        loop.close()


def test_dispatcher_auth_challenge_resolves_pin_future():
    """The .../data/authentication push is the PIN-shown signal."""
    client = _static_client()
    loop = asyncio.new_event_loop()
    try:
        client._auth_future = loop.create_future()
        dispatch_incoming_mqtt_message(
            client, client.topicMobiBasepath + "ui_service/data/authentication", ""
        )
        assert client._auth_future.done()
        assert client._auth_future.result() == ""
    finally:
        loop.close()


def test_dispatcher_close_and_toast_resolve_pairing_event_future():
    """close -> 'closed', toast -> 'busy' on the dedicated event future."""
    client = _static_client()
    for topic_suffix, expected in (
        ("ui_service/data/authenticationcodetoast", "busy"),
        ("ui_service/data/authenticationcodeclose", "closed"),
    ):
        loop = asyncio.new_event_loop()
        try:
            fut = loop.create_future()
            client._pairing_event_future = fut
            dispatch_incoming_mqtt_message(client, client.topicMobiBasepath + topic_suffix, "")
            assert fut.done() and fut.result() == expected
        finally:
            loop.close()


def test_dispatcher_ignores_topic_with_foreign_client_id():
    """F10-leg3: an exact-topic match, not a loose endswith on a foreign basepath."""
    client = _static_client()
    loop = asyncio.new_event_loop()
    try:
        client._auth_future = loop.create_future()
        dispatch_incoming_mqtt_message(
            client, "/remoteapp/mobile/someone_else/ui_service/data/authentication", ""
        )
        assert not client._auth_future.done()
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# async_submit_pin_code: publish/consume + static (tokenless) behaviour
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_static_pin_submit_publishes_authnum_without_token_wait():
    client = _static_client()
    published: list[tuple[str, object]] = []
    mqtt = MagicMock()

    def fake_publish(topic, payload="", *args, **kwargs):
        published.append((topic, payload))
        if topic.endswith("actions/authenticationcode"):
            client._loop.call_soon_threadsafe(
                client._safe_set_future_result, client._auth_code_future, '{"result":1,"info":""}'
            )
        return (0, 1)

    mqtt.publish.side_effect = fake_publish
    client.mqtt_client = mqtt

    result = await async_submit_pin_code(client, "0656")

    assert result == {}
    assert (client.topicTVUIBasepath + "actions/authenticationcode", '{"authNum": 656}') in published
    assert not any("gettoken" in topic for topic, _ in published)


@pytest.mark.anyio
async def test_dynamic_pin_submit_still_requests_token():
    client = HisenseTvClient(ip="192.168.50.12", auth_profile="modern")
    client.client_id = "aa$his$BB_vidaacommon_001"
    client.define_topic_paths()
    published: list[tuple[str, object]] = []
    mqtt = MagicMock()

    def fake_publish(topic, payload="", *args, **kwargs):
        published.append((topic, payload))
        if topic.endswith("actions/authenticationcode"):
            client._loop.call_soon_threadsafe(
                client._safe_set_future_result, client._auth_code_future, '{"result":1,"info":""}'
            )
        if topic.endswith("data/gettoken"):
            client._loop.call_soon_threadsafe(
                client._safe_set_future_result,
                client._token_future,
                json.dumps({
                    "accesstoken": "AT",
                    "accesstoken_time": 1700000000,
                    "accesstoken_duration_day": 7,
                    "refreshtoken": "RT",
                    "refreshtoken_time": 1700000000,
                    "refreshtoken_duration_day": 30,
                }),
            )
        return (0, 1)

    mqtt.publish.side_effect = fake_publish
    client.mqtt_client = mqtt

    data = await async_submit_pin_code(client, "1234")

    assert data["accesstoken"] == "AT"
    assert client.access_token == "AT"
    assert any("data/gettoken" in topic for topic, _ in published)


@pytest.mark.anyio
async def test_pin_submit_rejects_wrong_code():
    client = _static_client()
    mqtt = MagicMock()

    def fake_publish(topic, payload="", *args, **kwargs):
        if topic.endswith("actions/authenticationcode"):
            client._loop.call_soon_threadsafe(
                client._safe_set_future_result,
                client._auth_code_future,
                '{"result":100,"info":"Wrong authNum!!"}',
            )
        return (0, 1)

    mqtt.publish.side_effect = fake_publish
    client.mqtt_client = mqtt

    with pytest.raises(Exception, match="Incorrect PIN"):
        await async_submit_pin_code(client, "0000")


@pytest.mark.anyio
async def test_pin_submit_raises_pairing_status_on_busy():
    client = _static_client()
    mqtt = MagicMock()

    def fake_publish(topic, payload="", *args, **kwargs):
        if topic.endswith("actions/authenticationcode"):
            client._loop.call_soon_threadsafe(
                client._safe_set_future_result, client._pairing_event_future, "busy"
            )
        return (0, 1)

    mqtt.publish.side_effect = fake_publish
    client.mqtt_client = mqtt

    with pytest.raises(PairingStatusError) as exc:
        await async_submit_pin_code(client, "1234")
    assert exc.value.status == "busy"


# ---------------------------------------------------------------------------
# Flow: static session challenge -> PIN form -> completion
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_static_session_challenge_shows_pin_form(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(return_value=True))

    result = await flow._async_init_client_and_auth()

    assert result["type"] == "form"
    assert result["step_id"] == "auth"


@pytest.mark.anyio
async def test_static_session_without_challenge_skips_pin_form(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(return_value=False))

    result = await flow._async_init_client_and_auth()

    assert result["type"] == "form"
    assert result["step_id"] == "options"


@pytest.mark.anyio
async def test_static_probe_busy_shows_retryable_error(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(side_effect=PairingStatusError("busy")))

    result = await flow._async_init_client_and_auth()

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.anyio
async def test_static_pin_submit_completes_flow(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(return_value=True))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_submit_pin",
        AsyncMock(return_value={}),
    )

    shown = await flow._async_init_client_and_auth()
    assert shown["step_id"] == "auth"

    result = await flow.async_step_auth(user_input={"pin_code": "0656"})
    assert result["step_id"] == "options"

    entry = await flow.async_step_options(user_input={"enable_remote": True})
    assert entry["type"] == "create_entry"


@pytest.mark.anyio
async def test_static_pin_submit_close_shows_retryable_error(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(return_value=True))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_submit_pin",
        AsyncMock(side_effect=PairingStatusError("closed")),
    )

    await flow._async_init_client_and_auth()
    result = await flow.async_step_auth(user_input={"pin_code": "0656"})

    assert result["type"] == "form"
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.anyio
async def test_static_pin_submit_failure_after_pin_is_not_invalid_auth(monkeypatch, no_network_start_auth):
    """F9-leg6: an error AFTER a successful PIN must not surface as invalid_auth."""
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(return_value=True))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.async_submit_pin",
        AsyncMock(return_value={}),
    )

    async def boom():
        raise RuntimeError("discovery exploded")

    monkeypatch.setattr(flow, "_async_discover_device_name", boom)

    await flow._async_init_client_and_auth()
    with pytest.raises(RuntimeError, match="discovery exploded"):
        await flow.async_step_auth(user_input={"pin_code": "0656"})


# ---------------------------------------------------------------------------
# F1-leg2: AbortFlow must escape the generic cannot_connect handlers
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_duplicate_tv_aborts_with_already_configured(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="legacy")
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_helpers.get_arp_mac",
        lambda host: "e8:51:77:ec:98:1c",
    )

    with pytest.raises(AbortFlow) as exc:
        await flow.async_step_user(
            user_input={"ip_address": "192.168.50.12", "auth_profile": "legacy"}
        )
    assert exc.value.reason == "already_configured"


@pytest.mark.anyio
async def test_discovery_confirm_does_not_swallow_abort_flow(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="legacy")
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

    with pytest.raises(AbortFlow):
        await flow.async_step_discovery_confirm(user_input={})


@pytest.mark.anyio
async def test_certs_step_does_not_swallow_abort_flow(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="modern")
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.flow_certs.check_certs_exist", lambda c, k: True
    )

    with pytest.raises(AbortFlow):
        await flow.async_step_certs(user_input={"use_ssl": False, "certfile": "", "keyfile": ""})


# ---------------------------------------------------------------------------
# F2-leg2: duplicate guard before disconnect; sibling scoping
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_duplicate_add_keeps_running_client_connected():
    hass = _hass()
    running = MagicMock()
    running.ip = "192.168.50.12"
    running.mac = "e8:51:77:ec:98:1c"
    hass.data = {"hisense_vidaa": {"entry_1": {"client": running}}}

    flow = _flow(hass)
    flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

    with pytest.raises(AbortFlow):
        await flow._async_init_client_and_auth()

    assert not running.disconnect.called


@pytest.mark.anyio
async def test_reauth_disconnects_only_its_own_client():
    hass = _hass()
    own = MagicMock()
    own.ip = "192.168.50.12"
    own.mac = "e8:51:77:ec:98:1c"
    sibling = MagicMock()
    sibling.ip = "192.168.50.12"  # same IP, different entry
    sibling.mac = "e8:51:77:ec:98:1d"
    hass.data = {"hisense_vidaa": {"entry_1": {"client": own}, "entry_2": {"client": sibling}}}

    flow = _flow(hass)
    flow._reauth_entry = MagicMock()
    flow._reauth_entry.entry_id = "entry_1"

    await flow._async_disconnect_existing_client()

    assert own.disconnect.called
    assert not sibling.disconnect.called


# ---------------------------------------------------------------------------
# F10-leg6: async_remove keeps and logs the executor future
# ---------------------------------------------------------------------------
def test_async_remove_registers_done_callback():
    flow = HisenseVidaaConfigFlow()
    fut = MagicMock()
    fut.cancelled.return_value = False
    fut.exception.return_value = RuntimeError("disconnect failed")
    hass = MagicMock()
    hass.async_add_executor_job = MagicMock(return_value=fut)
    flow.hass = hass
    flow.client = MagicMock()

    flow.async_remove()

    assert fut.add_done_callback.called
    callback = fut.add_done_callback.call_args[0][0]
    callback(fut)  # must log and not raise


# ---------------------------------------------------------------------------
# [P4-a] The probe body itself: async_probe_pairing_challenge must clean up the
# pairing futures on EVERY exit path (challenge, close, no-challenge timeout).
# ---------------------------------------------------------------------------
def _probe_client() -> tuple[HisenseTvClient, MagicMock]:
    """A static client whose MQTT layer is faked for the pairing probe."""
    client = HisenseTvClient(
        ip="192.168.50.12", mac="e8:51:77:ec:98:1c", auth_profile="legacy"
    )
    client.client_id = "hisenseservice"
    client.username = "hisenseservice"
    client.password = "multimqttservice"
    client.define_topic_paths()
    client.mqtt_client = None
    client.connected = True  # skip the ~10s connect-wait loop
    mqtt = MagicMock()
    client.create_mqtt_client = MagicMock(return_value=mqtt)
    return client, mqtt


@pytest.mark.anyio
async def test_probe_no_challenge_timeout_cleans_up_futures():
    client, _mqtt = _probe_client()

    assert await async_probe_pairing_challenge(client, timeout=0.3) is False
    assert client._auth_future is None, "probe must null _auth_future on timeout"
    assert client._pairing_event_future is None, "probe must null the pairing event future on timeout"


@pytest.mark.anyio
async def test_probe_close_event_cleans_up_futures():
    client, mqtt = _probe_client()

    def fake_publish(topic, payload="", *args, **kwargs):
        if topic.endswith("actions/gettvstate") and client._pairing_event_future is not None:
            client._safe_set_future_result(client._pairing_event_future, "closed")
        return (0, 1)

    mqtt.publish.side_effect = fake_publish

    with pytest.raises(PairingStatusError) as exc:
        await async_probe_pairing_challenge(client, timeout=1.0)
    assert exc.value.status == "closed"
    assert client._auth_future is None, "probe must null _auth_future when the dialog closes"
    assert client._pairing_event_future is None, "probe must null the pairing event future when the dialog closes"


@pytest.mark.anyio
async def test_probe_challenge_returns_true_and_cleans_up_futures():
    client, mqtt = _probe_client()

    def fake_publish(topic, payload="", *args, **kwargs):
        if topic.endswith("actions/gettvstate") and client._auth_future is not None:
            client._safe_set_future_result(client._auth_future, "")
        return (0, 1)

    mqtt.publish.side_effect = fake_publish

    assert await async_probe_pairing_challenge(client, timeout=1.0) is True
    assert client._auth_future is None, "probe must null _auth_future after a challenge"
    assert client._pairing_event_future is None, "probe must null the pairing event future after a challenge"


# ---------------------------------------------------------------------------
# [P4-b] No-challenge path must drop the probe MQTT connection (same-client-id
# collision with the running entry otherwise).
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_static_no_challenge_disconnects_probe_client(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass)
    monkeypatch.setattr(PROBE_PATH, AsyncMock(return_value=False))

    disconnected: list[object] = []
    monkeypatch.setattr(
        "custom_components.hisense_vidaa.client.HisenseTvClient.disconnect",
        lambda self: disconnected.append(self),
    )

    result = await flow._async_init_client_and_auth()

    assert result["step_id"] == "options"
    assert disconnected, "the probe connection must be dropped on the no-challenge path"


# ---------------------------------------------------------------------------
# [P4-c] Static reauth route reaches the pairing step, and disconnects only its
# own (live) entry before the probe connects under the fixed client-id.
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_static_reauth_disconnects_own_entry_before_probe(monkeypatch, no_network_start_auth):
    hass = _hass()
    events: list[str] = []

    own = MagicMock()
    own.ip = "192.168.50.12"
    own.mac = "e8:51:77:ec:98:1c"
    own.disconnect = MagicMock(side_effect=lambda: events.append("disconnect:own"))
    sibling = MagicMock()
    sibling.ip = "192.168.50.12"  # same IP, different entry
    sibling.mac = "e8:51:77:ec:98:1d"
    sibling.disconnect = MagicMock(side_effect=lambda: events.append("disconnect:sibling"))
    hass.data = {"hisense_vidaa": {"entry_1": {"client": own}, "entry_2": {"client": sibling}}}

    flow = _flow(hass, profile="legacy")
    flow._reauth_entry = MagicMock()
    flow._reauth_entry.entry_id = "entry_1"

    async def fake_probe(*_args, **_kwargs):
        events.append("probe")
        return True

    monkeypatch.setattr(PROBE_PATH, fake_probe)

    result = await flow.async_step_reauth_confirm(user_input={})

    assert result["step_id"] == "auth"
    assert "probe" in events, "legacy/static reauth must still probe the pairing challenge"
    assert events.index("disconnect:own") < events.index("probe")
    assert "disconnect:sibling" not in events


# ---------------------------------------------------------------------------
# [P3] A generic probe failure during reauth must surface as cannot_connect,
# not escape as an unhandled "Error in flow".
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_reauth_probe_failure_shows_cannot_connect(monkeypatch, no_network_start_auth):
    hass = _hass()
    flow = _flow(hass, profile="legacy")
    flow._reauth_entry = MagicMock()
    flow._reauth_entry.entry_id = "entry_1"

    async def boom(*_args, **_kwargs):
        raise RuntimeError("create_mqtt_client exploded")

    monkeypatch.setattr(PROBE_PATH, boom)

    result = await flow.async_step_reauth_confirm(user_input={})

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# [P4-d] Dynamic fallback: the vidaa_app_connect ACK unblocks the retry wait.
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_dynamic_connect_ack_unblocks_retry_wait(monkeypatch):
    client = HisenseTvClient(
        ip="192.168.50.12", mac="e8:51:77:ec:98:1c", auth_profile="modern"
    )
    client.client_id = "aa$his$BB_vidaacommon_001"
    client.username = "his$1"
    client.password = "pw"
    client.access_token = "at"
    client.define_topic_paths()
    client.connected = True

    monkeypatch.setattr(
        "custom_components.hisense_vidaa.protocol.pairing.get_tv_timestamp",
        lambda ip, timeout: 1700000000,
    )

    mqtt = MagicMock()

    def fake_publish(topic, payload="", *args, **kwargs):
        # The TV accepts the connect request but never announces a PIN dialog.
        ack = getattr(client, "_connect_ack_future", None)
        if ack is not None and not ack.done():
            ack.set_result('{"connect_result":1}')
        return (0, 1)

    mqtt.publish.side_effect = fake_publish
    client.create_mqtt_client = MagicMock(return_value=mqtt)

    # Must return cleanly (ACK breaks the retry loop) instead of raising the
    # "TV did not show PIN" timeout after three attempts.
    await _async_execute_pairing_attempt(client, profile="modern")

    assert client._auth_future is None
    assert client._connect_ack_future is None


# ---------------------------------------------------------------------------
# [P4-e] Dispatcher exact-topic match: a getdeviceinfo/gettvinfo push on a
# FOREIGN client-id basepath must not reach the device-info handler.
# ---------------------------------------------------------------------------
def test_dispatcher_device_info_requires_exact_topic():
    client = _static_client()
    client._dispatch_device_info_update = MagicMock()

    # Foreign basepath: an `endswith` match would (wrongly) sweep this in.
    dispatch_incoming_mqtt_message(
        client, "/remoteapp/mobile/someone_else/platform_service/data/getdeviceinfo", "{}"
    )
    dispatch_incoming_mqtt_message(
        client, "/remoteapp/mobile/someone_else/platform_service/data/gettvinfo", "{}"
    )
    assert not client._dispatch_device_info_update.called

    # Exact topic for THIS client still routes.
    dispatch_incoming_mqtt_message(
        client, client.topicMobiBasepath + "platform_service/data/getdeviceinfo", "{}"
    )
    assert client._dispatch_device_info_update.called
