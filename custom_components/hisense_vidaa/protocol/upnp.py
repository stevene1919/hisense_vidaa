"""Asynchronous UPnP/DLNA LAN control client for Hisense VIDAA TV.

Provides zero-certificate local volume, mute, playback state tracking,
and fast device reachability probing via UPnP RenderingControl and AVTransport.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPNP_PORT = 38400
CANDIDATE_UPNP_PORTS = (38400, 18400)

SOAP_ENVELOPE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    "<s:Body>"
    '<u:{action} xmlns:u="{service}">'
    "{args}"
    "</u:{action}>"
    "</s:Body>"
    "</s:Envelope>"
)

SERVICE_RENDERING_CONTROL = "urn:schemas-upnp-org:service:RenderingControl:1"
SERVICE_AV_TRANSPORT = "urn:schemas-upnp-org:service:AVTransport:1"
SERVICE_LAN_CONTROL = "urn:schemas-upnp-org:service:HisenseLanControl:1"

PATH_RENDERING_CONTROL = "/upnp/control/mingusrcr"
PATH_AV_TRANSPORT = "/upnp/control/mingusavtr"
PATH_LAN_CONTROL = "/upnp/control/hisense_lan_control"


class HisenseUpnpClient:
    """Asynchronous client for Hisense VIDAA TV UPnP / DLNA endpoints."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_UPNP_PORT,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 2.0,
    ) -> None:
        """Initializes the UPnP client."""
        self.host = host
        self.port = port
        self._session = session
        self._timeout = timeout
        self._owns_session = False
        self._active_port: int | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Returns the active ClientSession or creates a managed one."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Closes the underlying session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def async_probe(self) -> dict[str, Any] | None:
        """Probes candidate UPnP ports and returns basic device info if alive."""
        session = await self._get_session()
        ports_to_try = [self.port] if self._active_port == self.port else list(CANDIDATE_UPNP_PORTS)
        for port in ports_to_try:
            url = f"http://{self.host}:{port}/MediaServer/rendererdevicedesc.xml"
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as resp:
                    if resp.status == 200:
                        text = await resp.read()
                        root = ET.fromstring(text.decode("utf-8", errors="ignore"))
                        ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                        fn = root.find(".//d:friendlyName", ns)
                        mn = root.find(".//d:modelName", ns)
                        friendly = fn.text if fn is not None else "Hisense TV"
                        model = mn.text if mn is not None else "Renderer"
                        self._active_port = port
                        return {
                            "is_alive": True,
                            "port": port,
                            "friendly_name": friendly,
                            "model_name": model,
                        }
            except Exception as err:
                _LOGGER.debug("UPnP probe on %s:%s failed: %s", self.host, port, err)
        return None

    async def async_get_tv_timestamp(self, timeout: float = 2.0) -> int | None:
        """Fetches the live timestamp from the TV's UPnP HTTP Date header asynchronously."""
        import email.utils

        session = await self._get_session()
        ports_to_try = [self.port] if self._active_port == self.port else list(CANDIDATE_UPNP_PORTS)
        for port in ports_to_try:
            url = f"http://{self.host}:{port}/MediaServer/rendererdevicedesc.xml"
            try:
                async with session.get(
                    url,
                    headers={"User-Agent": "HisenseVIDAAClient/1.0"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    date_str = resp.headers.get("Date")
                    if date_str:
                        dt = email.utils.parsedate_to_datetime(date_str)
                        self._active_port = port
                        return int(dt.timestamp())
            except Exception as err:
                _LOGGER.debug(
                    "Could not fetch TV clock from HTTP Date header on %s:%s: %s",
                    self.host,
                    port,
                    err,
                )
        return None

    async def async_get_device_fingerprint(self, timeout: float = 2.0) -> dict[str, Any]:
        """Queries UPnP/DLNA XML descriptors asynchronously across candidate ports."""
        info: dict[str, Any] = {
            "friendly_name": None,
            "model_name": None,
            "model_number": None,
            "manufacturer": None,
            "serial_number": None,
            "presentation_url": None,
            "upnp_port": None,
            "brand": None,
            "model": None,
            "platform": None,
            "vidaa_support": None,
            "voice": None,
            "transport_protocol": None,
            "mac_wifi": None,
            "mac_ethernet": None,
            "model_description": None,
        }
        session = await self._get_session()
        ports_to_try = [self.port] if self._active_port == self.port else list(CANDIDATE_UPNP_PORTS)
        for port in ports_to_try:
            url = f"http://{self.host}:{port}/MediaServer/rendererdevicedesc.xml"
            try:
                async with session.get(
                    url,
                    headers={"User-Agent": "HisenseVIDAAClient/1.0"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        root = ET.fromstring(content.decode("utf-8", errors="ignore"))
                        ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                        device = root.find(".//d:device", ns)
                        if device is not None:
                            for tag, key in (
                                ("friendlyName", "friendly_name"),
                                ("modelName", "model_name"),
                                ("modelNumber", "model_number"),
                                ("manufacturer", "manufacturer"),
                                ("serialNumber", "serial_number"),
                                ("presentationURL", "presentation_url"),
                            ):
                                el = device.find(f"d:{tag}", ns)
                                if el is not None and el.text:
                                    info[key] = el.text.strip()

                            desc_el = device.find("d:modelDescription", ns)
                            if desc_el is not None and desc_el.text:
                                raw_desc = desc_el.text.strip()
                                info["model_description"] = raw_desc
                                for line in raw_desc.splitlines():
                                    if "=" in line:
                                        k, _, v = line.partition("=")
                                        k_strip = k.strip()
                                        v_strip = v.strip()
                                        if k_strip == "brand":
                                            info["brand"] = v_strip
                                        elif k_strip == "model":
                                            info["model"] = v_strip
                                        elif k_strip == "platform":
                                            info["platform"] = v_strip
                                        elif k_strip == "vidaa_support":
                                            info["vidaa_support"] = v_strip
                                        elif k_strip == "voice":
                                            info["voice"] = v_strip
                                        elif k_strip == "transport_protocol":
                                            info["transport_protocol"] = v_strip
                                        elif k_strip == "macWifi":
                                            info["mac_wifi"] = v_strip
                                        elif k_strip == "macEthernet":
                                            info["mac_ethernet"] = v_strip

                            info["upnp_port"] = port
                            self._active_port = port
                            return info
            except Exception as err:
                _LOGGER.debug(
                    "Could not fetch UPnP descriptor on %s:%s: %s",
                    self.host,
                    port,
                    err,
                )
        return info

    async def async_send_soap(
        self,
        control_path: str,
        service: str,
        action: str,
        args: str = "",
    ) -> tuple[int, str]:
        """Dispatches a SOAP action to the active or default UPnP port."""
        port = self._active_port or self.port
        url = f"http://{self.host}:{port}{control_path}"
        headers = {
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{service}#{action}"',
            "User-Agent": "HisenseVIDAAClient/1.0",
        }
        data = SOAP_ENVELOPE.format(action=action, service=service, args=args).encode("utf-8")
        session = await self._get_session()
        try:
            async with session.post(
                url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as resp:
                text = await resp.text()
                return resp.status, text
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.debug("UPnP SOAP error on %s (%s): %s", url, action, err)
            return 0, str(err)
        except Exception as err:
            _LOGGER.warning("Unexpected UPnP error on %s (%s): %s", url, action, err)
            return 0, str(err)

    async def async_get_volume(self) -> int | None:
        """Retrieves master volume level (0-100) via RenderingControl."""
        status, resp_xml = await self.async_send_soap(
            PATH_RENDERING_CONTROL,
            SERVICE_RENDERING_CONTROL,
            "GetVolume",
            "<InstanceID>0</InstanceID><Channel>Master</Channel>",
        )
        if status == 200:
            try:
                root = ET.fromstring(resp_xml)
                vol = root.find(".//CurrentVolume")
                if vol is not None and vol.text and vol.text.isdigit():
                    return int(vol.text)
            except Exception as err:
                _LOGGER.debug("Failed parsing GetVolume XML response: %s", err)
        return None

    async def async_set_volume(self, volume: int) -> bool:
        """Sets master volume level (0-100) via RenderingControl."""
        clamped = max(0, min(100, volume))
        status, _ = await self.async_send_soap(
            PATH_RENDERING_CONTROL,
            SERVICE_RENDERING_CONTROL,
            "SetVolume",
            f"<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>{clamped}</DesiredVolume>",
        )
        return status == 200

    async def async_get_mute(self) -> bool | None:
        """Retrieves master mute status via RenderingControl."""
        status, resp_xml = await self.async_send_soap(
            PATH_RENDERING_CONTROL,
            SERVICE_RENDERING_CONTROL,
            "GetMute",
            "<InstanceID>0</InstanceID><Channel>Master</Channel>",
        )
        if status == 200:
            try:
                root = ET.fromstring(resp_xml)
                mute = root.find(".//CurrentMute")
                if mute is not None and mute.text:
                    return mute.text in ("1", "true", "True")
            except Exception as err:
                _LOGGER.debug("Failed parsing GetMute XML response: %s", err)
        return None

    async def async_set_mute(self, mute: bool) -> bool:
        """Sets master mute status (True/False) via RenderingControl."""
        desired = "1" if mute else "0"
        status, _ = await self.async_send_soap(
            PATH_RENDERING_CONTROL,
            SERVICE_RENDERING_CONTROL,
            "SetMute",
            f"<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredMute>{desired}</DesiredMute>",
        )
        return status == 200

    async def async_get_transport_info(self) -> dict[str, str] | None:
        """Retrieves media playback state from AVTransport."""
        status, resp_xml = await self.async_send_soap(
            PATH_AV_TRANSPORT,
            SERVICE_AV_TRANSPORT,
            "GetTransportInfo",
            "<InstanceID>0</InstanceID>",
        )
        if status == 200:
            try:
                root = ET.fromstring(resp_xml)
                state = root.find(".//CurrentTransportState")
                st = root.find(".//CurrentTransportStatus")
                speed = root.find(".//CurrentSpeed")
                return {
                    "state": state.text if state is not None and state.text else "UNKNOWN",
                    "status": st.text if st is not None and st.text else "UNKNOWN",
                    "speed": speed.text if speed is not None and speed.text else "1",
                }
            except Exception as err:
                _LOGGER.debug("Failed parsing GetTransportInfo XML response: %s", err)
        return None

    async def async_send_lan_control(
        self, op_class: str, op_type: str, op_para: str = ""
    ) -> tuple[int, str]:
        """Sends proprietary LanControlInfo command (available on VIDAA U6+)."""
        args = f"<OpClass>{op_class}</OpClass><OpType>{op_type}</OpType><OpPara>{op_para}</OpPara>"
        return await self.async_send_soap(
            PATH_LAN_CONTROL,
            SERVICE_LAN_CONTROL,
            "LanControlInfo",
            args,
        )
