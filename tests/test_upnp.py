"""Unit tests for HisenseUpnpClient and UPnP LAN Control services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hisense_vidaa.client import HisenseTvClient
from custom_components.hisense_vidaa.protocol.upnp import (
    PATH_LAN_CONTROL,
    HisenseUpnpClient,
)

SAMPLE_DEVICE_DESC = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
    <device>
        <friendlyName>Hisense TV</friendlyName>
        <modelName>Renderer</modelName>
    </device>
</root>
"""

SAMPLE_GET_VOLUME_RESP = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
 <s:Body>
  <u:GetVolumeResponse xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
   <CurrentVolume>25</CurrentVolume>
  </u:GetVolumeResponse>
 </s:Body>
</s:Envelope>
"""

SAMPLE_GET_MUTE_RESP = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
 <s:Body>
  <u:GetMuteResponse xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">
   <CurrentMute>1</CurrentMute>
  </u:GetMuteResponse>
 </s:Body>
</s:Envelope>
"""

SAMPLE_GET_TRANSPORT_RESP = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
 <s:Body>
  <u:GetTransportInfoResponse xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
   <CurrentTransportState>PLAYING</CurrentTransportState>
   <CurrentTransportStatus>OK</CurrentTransportStatus>
   <CurrentSpeed>1</CurrentSpeed>
  </u:GetTransportInfoResponse>
 </s:Body>
</s:Envelope>
"""


@pytest.fixture
def mock_session():
    """Returns an aiohttp-compatible mock session."""
    session = MagicMock()
    session.closed = False
    return session


@pytest.mark.anyio
async def test_upnp_probe_success(mock_session):
    """Test successful UPnP probe discovering friendly name and model."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=SAMPLE_DEVICE_DESC.encode("utf-8"))

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.get.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    result = await client.async_probe()

    assert result is not None
    assert result["is_alive"] is True
    assert result["port"] == 38400
    assert result["friendly_name"] == "Hisense TV"
    assert result["model_name"] == "Renderer"


@pytest.mark.anyio
async def test_upnp_probe_failure(mock_session):
    """Test UPnP probe when endpoints time out."""
    cm = AsyncMock()
    cm.__aenter__.side_effect = Exception("Connection refused")
    mock_session.get.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    result = await client.async_probe()

    assert result is None


@pytest.mark.anyio
async def test_upnp_get_volume(mock_session):
    """Test retrieving volume via RenderingControl."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=SAMPLE_GET_VOLUME_RESP)

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.post.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    vol = await client.async_get_volume()

    assert vol == 25
    mock_session.post.assert_called_once()
    args, kwargs = mock_session.post.call_args
    assert "/upnp/control/mingusrcr" in args[0]
    assert "RenderingControl:1#GetVolume" in kwargs["headers"]["SOAPAction"]


@pytest.mark.anyio
async def test_upnp_set_volume(mock_session):
    """Test setting volume via RenderingControl with clamping."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="")

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.post.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    success = await client.async_set_volume(150)  # Clamps to 100

    assert success is True
    _args, kwargs = mock_session.post.call_args
    assert "<DesiredVolume>100</DesiredVolume>" in kwargs["data"].decode("utf-8")


@pytest.mark.anyio
async def test_upnp_get_mute(mock_session):
    """Test retrieving mute status."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=SAMPLE_GET_MUTE_RESP)

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.post.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    muted = await client.async_get_mute()

    assert muted is True


@pytest.mark.anyio
async def test_upnp_set_mute(mock_session):
    """Test setting mute state."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="")

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.post.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    success = await client.async_set_mute(False)

    assert success is True
    _args, kwargs = mock_session.post.call_args
    assert "<DesiredMute>0</DesiredMute>" in kwargs["data"].decode("utf-8")


@pytest.mark.anyio
async def test_upnp_get_transport_info(mock_session):
    """Test retrieving media playback state."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value=SAMPLE_GET_TRANSPORT_RESP)

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.post.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    info = await client.async_get_transport_info()

    assert info is not None
    assert info["state"] == "PLAYING"
    assert info["status"] == "OK"
    assert info["speed"] == "1"


@pytest.mark.anyio
async def test_upnp_send_lan_control(mock_session):
    """Test sending proprietary LanControlInfo action."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.text = AsyncMock(return_value="<Result>OK</Result>")

    cm = AsyncMock()
    cm.__aenter__.return_value = mock_resp
    mock_session.post.return_value = cm

    client = HisenseUpnpClient("192.168.1.100", session=mock_session)
    status, text = await client.async_send_lan_control("RemoteKey", "SendKey", "KEY_HOME")

    assert status == 200
    assert text == "<Result>OK</Result>"
    args, kwargs = mock_session.post.call_args
    assert PATH_LAN_CONTROL in args[0]
    assert "<OpClass>RemoteKey</OpClass>" in kwargs["data"].decode("utf-8")


@pytest.mark.anyio
async def test_client_upnp_wrappers():
    """Test that HisenseTvClient UPnP methods properly delegate to HisenseUpnpClient."""
    tv_client = HisenseTvClient("192.168.1.50")

    with (
        patch.object(tv_client.upnp, "async_get_volume", AsyncMock(return_value=42)) as mock_vol,
        patch.object(tv_client.upnp, "async_set_volume", AsyncMock(return_value=True)) as mock_set_vol,
        patch.object(tv_client.upnp, "async_get_mute", AsyncMock(return_value=False)) as mock_mute,
        patch.object(tv_client.upnp, "async_set_mute", AsyncMock(return_value=True)) as mock_set_mute,
        patch.object(
            tv_client.upnp,
            "async_get_transport_info",
            AsyncMock(return_value={"state": "PAUSED_PLAYBACK", "status": "OK", "speed": "1"}),
        ) as mock_trans,
        patch.object(
            tv_client.upnp,
            "async_probe",
            AsyncMock(return_value={"is_alive": True, "port": 38400, "friendly_name": "Living Room TV"}),
        ) as mock_probe,
    ):
        assert await tv_client.async_upnp_get_volume() == 42
        mock_vol.assert_called_once()

        assert await tv_client.async_upnp_set_volume(42) is True
        mock_set_vol.assert_called_once_with(42)

        assert await tv_client.async_upnp_get_mute() is False
        mock_mute.assert_called_once()

        assert await tv_client.async_upnp_set_mute(True) is True
        mock_set_mute.assert_called_once_with(True)

        trans = await tv_client.async_upnp_get_transport_info()
        assert trans["state"] == "PAUSED_PLAYBACK"
        mock_trans.assert_called_once()

        probe = await tv_client.async_upnp_probe()
        assert probe["friendly_name"] == "Living Room TV"
        mock_probe.assert_called_once()


def test_upnp_desc_parsers() -> None:
    """Test dedicated UPnP descriptor parsing utilities."""
    from custom_components.hisense_vidaa.tv.upnp_desc import (
        parse_upnp_description_properties,
        parse_upnp_friendly_name,
        parse_upnp_renderer_descriptor,
    )

    xml_sample = """<?xml version="1.0"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0">
        <device>
            <friendlyName>Lounge Hisense TV</friendlyName>
            <modelName>VIDAA UHD</modelName>
            <modelNumber>65U7H</modelNumber>
            <manufacturer>Hisense</manufacturer>
            <modelDescription>
                macWifi=aa:bb:cc:dd:ee:01
                macEthernet=aa:bb:cc:dd:ee:02
                brand=Hisense
                platform=MTK9602
                vidaa_support=1
                voice=remote
                transport_protocol=mqtt
            </modelDescription>
        </device>
    </root>
    """

    assert parse_upnp_friendly_name(xml_sample) == "Lounge Hisense TV"
    assert parse_upnp_friendly_name("<invalid>xml") is None

    props = parse_upnp_description_properties("brand=Hisense\nplatform=MTK9602\nkey_without_val")
    assert props == {"brand": "Hisense", "platform": "MTK9602"}

    desc = parse_upnp_renderer_descriptor(xml_sample)
    assert desc["friendly_name"] == "Lounge Hisense TV"
    assert desc["model_name"] == "VIDAA UHD"
    assert desc["model_number"] == "65U7H"
    assert desc["manufacturer"] == "Hisense"
    assert desc["mac_wifi"] == "aa:bb:cc:dd:ee:01"
    assert desc["mac_ethernet"] == "aa:bb:cc:dd:ee:02"
    assert desc["brand"] == "Hisense"
    assert desc["platform"] == "MTK9602"
    assert desc["vidaa_support"] == "1"
    assert desc["voice"] == "remote"
    assert desc["transport_protocol"] == "mqtt"

    empty_desc = parse_upnp_renderer_descriptor("not valid xml")
    assert empty_desc["friendly_name"] is None

