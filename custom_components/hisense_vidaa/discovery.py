import contextlib
import email.utils
import logging
import os
import socket
import time
import urllib.request
from typing import Any

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)


UPNP_PORTS = (38400, 18400)


def get_tv_timestamp(ip: str, timeout: float = 2.0) -> int | None:
    """Fetches the live timestamp from the TV's UPnP HTTP Date header."""
    for port in UPNP_PORTS:
        try:
            url = f"http://{ip}:{port}/MediaServer/rendererdevicedesc.xml"
            req = urllib.request.Request(url, headers={"User-Agent": "HisenseVIDAAClient"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                date_str = response.headers.get("Date")
                if date_str:
                    dt = email.utils.parsedate_to_datetime(date_str)
                    return int(dt.timestamp())
        except Exception as e:
            _LOGGER.debug("Could not fetch TV clock from HTTP Date header on port %s: %s", port, e)
    return None


def get_arp_mac(ip: str) -> str | None:
    """Discovers hardware MAC address via getmac or Linux ARP table."""
    try:
        from getmac import get_mac_address

        mac = get_mac_address(ip=ip)
        if mac:
            return mac.lower()
    except Exception:
        pass

    try:
        import os

        if os.path.exists("/proc/net/arp"):
            with open("/proc/net/arp") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[0] == ip:
                        mac = parts[3]
                        if mac != "00:00:00:00:00:00":
                            return mac.lower()
    except Exception:
        pass

    return None


def get_device_fingerprint(ip: str, timeout: float = 2.0, zc: Any = None) -> dict[str, Any]:
    """Fetches UPnP, DLNA, and mDNS device metadata for model and capability identification."""
    info = {
        "friendly_name": None,
        "model_name": None,
        "model_number": None,
        "model_code": None,
        "manufacturer": None,
        "brand": None,
        "platform": None,
        "vidaa_support": None,
        "voice": None,
        "transport_protocol": None,
        "mac_wifi": None,
        "mac_ethernet": None,
        "firmware_version": None,
        "serial_number": None,
        "upnp_raw": None,
        "tv_timestamp": None,
    }

    # 1. Query UPnP / DLNA descriptor on candidate ports (38400, 18400)
    for port in UPNP_PORTS:
        try:
            if not info["tv_timestamp"]:
                info["tv_timestamp"] = get_tv_timestamp(ip, timeout=timeout)
            url = f"http://{ip}:{port}/MediaServer/rendererdevicedesc.xml"
            req = urllib.request.Request(url, headers={"User-Agent": "HisenseVIDAATestClient"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8", errors="ignore")
                root = ET.fromstring(content)
                ns = {"d": "urn:schemas-upnp-org:device-1-0"}
                device = root.find("d:device", ns)
                if device is not None:
                    fn = device.find("d:friendlyName", ns)
                    mn = device.find("d:modelName", ns)
                    mnum = device.find("d:modelNumber", ns)
                    mfg = device.find("d:manufacturer", ns)
                    desc = device.find("d:modelDescription", ns)

                    if fn is not None:
                        info["friendly_name"] = fn.text
                    if mn is not None:
                        info["model_name"] = mn.text
                    if mnum is not None:
                        info["model_number"] = mnum.text
                    if mfg is not None:
                        info["manufacturer"] = mfg.text

                    if desc is not None and desc.text:
                        info["upnp_raw"] = desc.text.strip()
                        for line in desc.text.strip().splitlines():
                            if "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip()
                                if k == "macWifi":
                                    info["mac_wifi"] = v
                                elif k == "macEthernet":
                                    info["mac_ethernet"] = v
                                elif k == "brand":
                                    info["brand"] = v
                                elif k == "platform":
                                    info["platform"] = v
                                elif k == "vidaa_support":
                                    info["vidaa_support"] = v
                                elif k == "voice":
                                    info["voice"] = v
                                elif k == "transport_protocol":
                                    info["transport_protocol"] = v
            # If we successfully parsed a descriptor, stop trying other ports
            if info["model_name"] or info["friendly_name"]:
                break
        except Exception as e:
            _LOGGER.debug("UPnP device description query failed on port %s: %s", port, e)

    # 2. Query mDNS / Zeroconf if available
    try:
        from zeroconf import ServiceBrowser, Zeroconf

        discovered = {}
        target_ip = ip

        class MDNSListener:
            def add_service(self, zc, type_, name):
                try:
                    s_info = zc.get_service_info(type_, name)
                    if s_info:
                        addrs = [socket.inet_ntoa(a) for a in s_info.addresses]
                        if target_ip in addrs or "Smart TV" in name:
                            discovered[type_] = s_info.properties
                except Exception:
                    pass

            def update_service(self, zc, type_, name):
                pass

            def remove_service(self, zc, type_, name):
                pass

        should_close_zc = False
        if zc is None:
            try:
                import asyncio
                asyncio.get_running_loop()
                zc = None
            except RuntimeError:
                try:
                    zc = Zeroconf()
                    should_close_zc = True
                except Exception:
                    zc = None

        if zc is not None:
            browser = ServiceBrowser(zc, ["_airplay._tcp.local.", "_hap._tcp.local."], MDNSListener())
            time.sleep(1.0)
            browser.cancel()
            if should_close_zc:
                zc.close()

        airplay = discovered.get("_airplay._tcp.local.", {})
        hap = discovered.get("_hap._tcp.local.", {})

        model_bytes = airplay.get(b"model") or hap.get(b"md")
        fv_bytes = airplay.get(b"fv")
        serial_bytes = airplay.get(b"serialNumber")
        company_bytes = airplay.get(b"company") or airplay.get(b"manufacturer")

        if model_bytes:
            info["model_code"] = model_bytes.decode("utf-8", errors="ignore")
        if fv_bytes:
            info["firmware_version"] = fv_bytes.decode("utf-8", errors="ignore")
        if serial_bytes:
            info["serial_number"] = serial_bytes.decode("utf-8", errors="ignore")
        if company_bytes and not info["manufacturer"]:
            info["manufacturer"] = company_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        _LOGGER.debug("mDNS device discovery skipped: %s", e)

    return info


def test_tv_ssl_connection(
    ip: str,
    certfile: str,
    keyfile: str,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Tests the TLS handshake against the TV MQTT broker on port 36669."""
    import ssl

    if not certfile or not os.path.isfile(certfile):
        raise FileNotFoundError(f"SSL Certificate file not found: '{certfile}'")
    if not keyfile or not os.path.isfile(keyfile):
        raise FileNotFoundError(f"SSL Private Key file not found: '{keyfile}'")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    if verify_ssl and ca_cert and os.path.isfile(ca_cert):
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=ca_cert)
    else:
        context.verify_mode = ssl.CERT_NONE
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)

    with (
        socket.create_connection((ip, 36669), timeout=timeout) as sock,
        context.wrap_socket(sock) as ssock,
    ):
        cipher_name, _proto, bits = ssock.cipher()
        return {
            "connected": True,
            "tls_version": ssock.version(),
            "cipher": cipher_name,
            "bits": bits,
            "certfile": certfile,
            "keyfile": keyfile,
            "ca_cert": ca_cert if verify_ssl else None,
        }


def probe_tv_auth_methods(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    mac: str | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Probes TV MQTT broker with various auth algorithms to diagnose compatibility."""
    import ssl
    import threading

    import paho.mqtt.client as mqtt

    try:
        from .crypto import generate_initial_credentials
    except ImportError:
        from crypto import generate_initial_credentials

    results = {
        "legacy_static": {"rc": None, "supported": False},
        "standard_dynamic": {"rc": None, "supported": False},
        "modern_dynamic": {"rc": None, "supported": False},
    }

    def _setup_tls(c: mqtt.Client) -> None:
        if certfile and keyfile and os.path.isfile(certfile) and os.path.isfile(keyfile):
            if verify_ssl and ca_cert and os.path.isfile(ca_cert):
                c.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
            else:
                c.tls_set(ca_certs=None, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
            c.tls_insecure_set(True)

    # 1. Legacy static ('hisenseservice')
    try:
        leg_rc = [None]
        leg_lock = threading.Event()
        leg_client = mqtt.Client(client_id="hisenseservice", clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(leg_client)
        leg_client.username_pw_set(username="hisenseservice", password="multimqttservice")
        leg_client.on_connect = lambda c, u, f, rc: (leg_rc.__setitem__(0, rc), leg_lock.set())
        leg_client.on_disconnect = lambda c, u, rc: leg_lock.set()
        leg_client.connect_async(ip, 36669, 5)
        leg_client.loop_start()
        leg_lock.wait(timeout=timeout)
        leg_client.loop_stop()
        leg_client.disconnect()
        results["legacy_static"]["rc"] = leg_rc[0]
        results["legacy_static"]["supported"] = (leg_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("Legacy static probe error: %s", e)

    # 2. Standard dynamic pairing (his$<timestamp>)
    try:
        cid, user, pwd = generate_initial_credentials(mac=mac, use_new_auth=False)
        std_rc = [None]
        std_lock = threading.Event()
        std_client = mqtt.Client(client_id=cid, clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(std_client)
        std_client.username_pw_set(username=user, password=pwd)
        std_client.on_connect = lambda c, u, f, rc: (std_rc.__setitem__(0, rc), std_lock.set())
        std_client.on_disconnect = lambda c, u, rc: std_lock.set()
        std_client.connect_async(ip, 36669, 5)
        std_client.loop_start()
        std_lock.wait(timeout=timeout)
        std_client.loop_stop()
        std_client.disconnect()
        results["standard_dynamic"]["rc"] = std_rc[0]
        results["standard_dynamic"]["supported"] = (std_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("Standard dynamic probe error: %s", e)

    # 3. Modern XOR dynamic pairing (his$<timestamp ^ XOR>)
    try:
        cid, user, pwd = generate_initial_credentials(mac=mac, use_new_auth=True)
        mod_rc = [None]
        mod_lock = threading.Event()
        mod_client = mqtt.Client(client_id=cid, clean_session=True, protocol=mqtt.MQTTv311)
        _setup_tls(mod_client)
        mod_client.username_pw_set(username=user, password=pwd)
        mod_client.on_connect = lambda c, u, f, rc: (mod_rc.__setitem__(0, rc), mod_lock.set())
        mod_client.on_disconnect = lambda c, u, rc: mod_lock.set()
        mod_client.connect_async(ip, 36669, 5)
        mod_client.loop_start()
        mod_lock.wait(timeout=timeout)
        mod_client.loop_stop()
        mod_client.disconnect()
        results["modern_dynamic"]["rc"] = mod_rc[0]
        results["modern_dynamic"]["supported"] = (mod_rc[0] == 0)
    except Exception as e:
        _LOGGER.debug("Modern dynamic probe error: %s", e)

    return results


def ping_tv(
    ip: str,
    certfile: str | None = None,
    keyfile: str | None = None,
    ca_cert: str | None = None,
    verify_ssl: bool = False,
    client_id: str | None = None,
    username: str | None = None,
    password: str | None = None,
    mac: str | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Quickly tests if TV broker is listening, accepting TLS, and responding to MQTT packets."""
    import ssl
    import threading

    import paho.mqtt.client as mqtt

    results: dict[str, Any] = {
        "tcp_port_open": False,
        "tls_handshake": False,
        "tls_version": None,
        "cipher": None,
        "mqtt_connected": False,
        "mqtt_rc": None,
        "mqtt_status": None,
        "auth_probe": None,
        "device_info": None,
        "error": None,
    }

    # 1. Test TCP port
    try:
        with socket.create_connection((ip, 36669), timeout=timeout):
            results["tcp_port_open"] = True
    except Exception as e:
        results["error"] = f"TCP connection failed (TV may be in deep sleep / off): {e}"
        return results

    # 2. Test TLS Handshake
    if certfile and keyfile:
        try:
            ssl_info = test_tv_ssl_connection(ip, certfile, keyfile, ca_cert=ca_cert, verify_ssl=verify_ssl, timeout=timeout)
            results["tls_handshake"] = ssl_info.get("connected", False)
            results["tls_version"] = ssl_info.get("tls_version")
            results["cipher"] = ssl_info.get("cipher")
        except Exception as e:
            results["error"] = f"TLS handshake failed: {e}"
            return results

    # 3. Test MQTT Broker Response (if credentials available)
    if client_id and username and password:
        try:
            conn_event = threading.Event()
            conn_rc = [None]

            def on_conn(c, userdata, flags, rc):
                conn_rc[0] = rc
                conn_event.set()

            c = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311)
            if certfile and keyfile and os.path.isfile(certfile) and os.path.isfile(keyfile):
                if verify_ssl and ca_cert and os.path.isfile(ca_cert):
                    c.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
                else:
                    c.tls_set(ca_certs=None, certfile=certfile, keyfile=keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
                c.tls_insecure_set(True)
            c.username_pw_set(username=username, password=password)
            c.on_connect = on_conn
            c.on_disconnect = lambda c, u, rc: conn_event.set()

            c.connect_async(ip, 36669, 5)
            c.loop_start()
            conn_event.wait(timeout=timeout)
            c.loop_stop()
            c.disconnect()

            results["mqtt_rc"] = conn_rc[0]
            if conn_rc[0] == 0:
                results["mqtt_connected"] = True
                results["mqtt_status"] = "Connected successfully"
            elif conn_rc[0] in (4, 5):
                results["mqtt_status"] = "Rejected: Bad username or password / Expired access token"
            elif conn_rc[0] is not None:
                results["mqtt_status"] = f"Broker rejected connection with code {conn_rc[0]}"
            else:
                results["mqtt_status"] = "Timeout waiting for broker CONNACK"
        except Exception as e:
            results["mqtt_status"] = f"MQTT test error: {e}"

    # 4. Probe auth methods
    with contextlib.suppress(Exception):
        results["auth_probe"] = probe_tv_auth_methods(ip, certfile=certfile, keyfile=keyfile, mac=mac, timeout=1.5)

    # 5. Device fingerprint
    with contextlib.suppress(Exception):
        results["device_info"] = get_device_fingerprint(ip, timeout=1.5)

    return results
