"""Client for connecting to Hisense VIDAA TV MQTT broker over TLS."""

import asyncio
import json
import logging
import os
import socket
import ssl
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

try:
    from .const import KEY_ALIASES
    from .crypto import generate_initial_credentials, resolve_certificates
    from .discovery import get_device_fingerprint as discover_device_fingerprint
except ImportError:
    from const import KEY_ALIASES
    from crypto import generate_initial_credentials, resolve_certificates
    from discovery import get_device_fingerprint as discover_device_fingerprint

_LOGGER = logging.getLogger(__name__)


class HisenseTvClient:
    """Client for connecting, authenticating, and controlling Hisense VIDAA TVs."""

    def __init__(
        self,
        ip: str,
        mac: str | None = None,
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        access_token_time: int = 0,
        access_token_duration: int = 0,
        refresh_token: str | None = None,
        refresh_token_time: int = 0,
        refresh_token_duration: int = 0,
        certfile: str | None = None,
        keyfile: str | None = None,
        auth_profile: str = "auto",
    ) -> None:
        self.ip = ip
        self.mac = mac
        self.client_id = client_id
        self.username = username
        self.password = password
        self.access_token = access_token
        self.access_token_time = access_token_time
        self.access_token_duration = access_token_duration
        self.refresh_token = refresh_token
        self.refresh_token_time = refresh_token_time
        self.refresh_token_duration = refresh_token_duration
        self.auth_profile = (auth_profile or "auto").lower()

        self.certfile, self.keyfile = resolve_certificates(
            auth_profile=self.auth_profile,
            certfile=certfile,
            keyfile=keyfile,
        )

        self.mqtt_client: mqtt.Client | None = None
        self.connected = False
        self._state_callbacks = []
        self._volume_callbacks = []
        self._sourcelist_callbacks = []
        self._applist_callbacks = []
        self._disconnected_callbacks = []
        self._token_refreshed_callbacks = []

        self._auth_future: asyncio.Future | None = None
        self._auth_code_future: asyncio.Future | None = None
        self._token_future: asyncio.Future | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._refreshing_token = False
        self._last_refresh_attempt = 0.0
        self._refresh_lock = threading.Lock()

        self.topicTVUIBasepath = ""
        self.topicTVPSBasepath = ""
        self.topicMobiBasepath = ""
        self.topicBrcsBasepath = "/remoteapp/mobile/broadcast/"
        self.topicRemoBasepath = ""

        if self.client_id:
            self.define_topic_paths()

    # Callback properties and registrations
    @property
    def on_state_update(self):
        return self._state_callbacks[0] if self._state_callbacks else None

    @on_state_update.setter
    def on_state_update(self, cb):
        if cb and cb not in self._state_callbacks:
            self._state_callbacks.append(cb)

    @property
    def on_volume_update(self):
        return self._volume_callbacks[0] if self._volume_callbacks else None

    @on_volume_update.setter
    def on_volume_update(self, cb):
        if cb and cb not in self._volume_callbacks:
            self._volume_callbacks.append(cb)

    @property
    def on_sourcelist_update(self):
        return self._sourcelist_callbacks[0] if self._sourcelist_callbacks else None

    @on_sourcelist_update.setter
    def on_sourcelist_update(self, cb):
        if cb and cb not in self._sourcelist_callbacks:
            self._sourcelist_callbacks.append(cb)

    @property
    def on_applist_update(self):
        return self._applist_callbacks[0] if self._applist_callbacks else None

    @on_applist_update.setter
    def on_applist_update(self, cb):
        if cb and cb not in self._applist_callbacks:
            self._applist_callbacks.append(cb)

    @property
    def on_disconnected_callback(self):
        return self._disconnected_callbacks[0] if self._disconnected_callbacks else None

    @on_disconnected_callback.setter
    def on_disconnected_callback(self, cb):
        if cb and cb not in self._disconnected_callbacks:
            self._disconnected_callbacks.append(cb)

    @property
    def on_token_refreshed(self):
        return self._token_refreshed_callbacks[0] if self._token_refreshed_callbacks else None

    @on_token_refreshed.setter
    def on_token_refreshed(self, cb):
        if cb and cb not in self._token_refreshed_callbacks:
            self._token_refreshed_callbacks.append(cb)

    def register_state_callback(self, cb):
        if cb and cb not in self._state_callbacks:
            self._state_callbacks.append(cb)

    def unregister_state_callback(self, cb):
        if cb in self._state_callbacks:
            self._state_callbacks.remove(cb)

    def register_volume_callback(self, cb):
        if cb and cb not in self._volume_callbacks:
            self._volume_callbacks.append(cb)

    def unregister_volume_callback(self, cb):
        if cb in self._volume_callbacks:
            self._volume_callbacks.remove(cb)

    def register_sourcelist_callback(self, cb):
        if cb and cb not in self._sourcelist_callbacks:
            self._sourcelist_callbacks.append(cb)

    def unregister_sourcelist_callback(self, cb):
        if cb in self._sourcelist_callbacks:
            self._sourcelist_callbacks.remove(cb)

    def register_applist_callback(self, cb):
        if cb and cb not in self._applist_callbacks:
            self._applist_callbacks.append(cb)

    def unregister_applist_callback(self, cb):
        if cb in self._applist_callbacks:
            self._applist_callbacks.remove(cb)

    def register_disconnected_callback(self, cb):
        if cb and cb not in self._disconnected_callbacks:
            self._disconnected_callbacks.append(cb)

    def unregister_disconnected_callback(self, cb):
        if cb in self._disconnected_callbacks:
            self._disconnected_callbacks.remove(cb)

    def register_token_refreshed_callback(self, cb):
        if cb and cb not in self._token_refreshed_callbacks:
            self._token_refreshed_callbacks.append(cb)

    def unregister_token_refreshed_callback(self, cb):
        if cb in self._token_refreshed_callbacks:
            self._token_refreshed_callbacks.remove(cb)

    def _dispatch_state_update(self, data):
        for cb in list(self._state_callbacks):
            try:
                cb(data)
            except Exception as e:
                _LOGGER.error("Error in state callback: %s", e)

    def _dispatch_volume_update(self, data):
        for cb in list(self._volume_callbacks):
            try:
                cb(data)
            except Exception as e:
                _LOGGER.error("Error in volume callback: %s", e)

    def _dispatch_sourcelist_update(self, data):
        for cb in list(self._sourcelist_callbacks):
            try:
                cb(data)
            except Exception as e:
                _LOGGER.error("Error in sourcelist callback: %s", e)

    def _dispatch_applist_update(self, data):
        for cb in list(self._applist_callbacks):
            try:
                cb(data)
            except Exception as e:
                _LOGGER.error("Error in applist callback: %s", e)

    def _dispatch_disconnected(self):
        for cb in list(self._disconnected_callbacks):
            try:
                cb()
            except Exception as e:
                _LOGGER.error("Error in disconnect callback: %s", e)

    def _dispatch_token_refreshed(self):
        for cb in list(self._token_refreshed_callbacks):
            try:
                cb(self)
            except Exception as e:
                _LOGGER.error("Error in token refreshed callback: %s", e)

    def validate_certificates(self) -> None:
        """Verifies that the SSL certificate and private key files exist and are readable."""
        if not os.path.isfile(self.certfile):
            raise FileNotFoundError(
                f"SSL Certificate file not found: '{self.certfile}'. "
                "Please place certificate files in 'certs/' or specify --cert."
            )
        if not os.path.isfile(self.keyfile):
            raise FileNotFoundError(
                f"SSL Private Key file not found: '{self.keyfile}'. "
                "Please place key files in 'certs/' or specify --key."
            )

    def test_ssl_connection(self, timeout: float = 5.0) -> dict[str, Any]:
        """Tests the raw TLS handshake with the TV on port 36669 without authenticating."""
        self.validate_certificates()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)

        with (
            socket.create_connection((self.ip, 36669), timeout=timeout) as sock,
            context.wrap_socket(sock) as ssock,
        ):
            cipher_name, _proto, bits = ssock.cipher()
            return {
                "connected": True,
                "tls_version": ssock.version(),
                "cipher": cipher_name,
                "bits": bits,
                "certfile": self.certfile,
                "keyfile": self.keyfile,
            }

    def get_device_fingerprint(self, timeout: float = 2.0) -> dict[str, Any]:
        """Fetches UPnP, DLNA, and mDNS device metadata for model and capability identification."""
        return discover_device_fingerprint(self.ip, timeout=timeout)

    def define_topic_paths(self) -> None:
        """Sets up topic paths for the specific client ID."""
        self.topicTVUIBasepath = f"/remoteapp/tv/ui_service/{self.client_id}/"
        self.topicTVPSBasepath = f"/remoteapp/tv/platform_service/{self.client_id}/"
        self.topicMobiBasepath = f"/remoteapp/mobile/{self.client_id}/"
        self.topicRemoBasepath = f"/remoteapp/tv/remote_service/{self.client_id}/"

    def generate_initial_creds(self, use_new_auth: bool | None = None) -> None:
        """Generates initial dynamic credentials for challenge-response pairing."""
        self.client_id, self.username, self.password = generate_initial_credentials(
            mac=self.mac,
            auth_profile=self.auth_profile,
            use_new_auth=use_new_auth,
        )
        self.define_topic_paths()
        _LOGGER.debug(
            "Generated initial creds (profile=%s, use_new_auth=%s) - Client ID: %s, Username: %s",
            self.auth_profile,
            use_new_auth,
            self.client_id,
            self.username,
        )

    def create_mqtt_client(self, client_id: str, username: str, password: str) -> mqtt.Client:
        """Creates and configures an authenticated MQTT client over TLS."""
        client = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        client.reconnect_delay_set(min_delay=2, max_delay=30)
        client.tls_set(ca_certs=None, certfile=self.certfile, keyfile=self.keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        client.tls_insecure_set(True)
        client.username_pw_set(username=username, password=password)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def probe_auth_methods(self, timeout: float = 2.0) -> dict[str, Any]:
        """Probes TV MQTT broker with various auth algorithms to diagnose compatibility."""
        results = {
            "legacy_static": {"rc": None, "supported": False},
            "standard_dynamic": {"rc": None, "supported": False},
            "modern_dynamic": {"rc": None, "supported": False},
        }

        # 1. Legacy static ('hisenseservice')
        try:
            leg_rc = [None]
            leg_lock = threading.Event()
            leg_client = mqtt.Client(client_id="hisenseservice", clean_session=True, protocol=mqtt.MQTTv311)
            leg_client.tls_set(ca_certs=None, certfile=self.certfile, keyfile=self.keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
            leg_client.tls_insecure_set(True)
            leg_client.username_pw_set(username="hisenseservice", password="multimqttservice")
            leg_client.on_connect = lambda c, u, f, rc: (leg_rc.__setitem__(0, rc), leg_lock.set())
            leg_client.on_disconnect = lambda c, u, rc: leg_lock.set()
            leg_client.connect_async(self.ip, 36669, 5)
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
            self.generate_initial_creds(use_new_auth=False)
            std_rc = [None]
            std_lock = threading.Event()
            std_client = self.create_mqtt_client(self.client_id, self.username, self.password)
            std_client.on_connect = lambda c, u, f, rc: (std_rc.__setitem__(0, rc), std_lock.set())
            std_client.on_disconnect = lambda c, u, rc: std_lock.set()
            std_client.connect_async(self.ip, 36669, 5)
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
            self.generate_initial_creds(use_new_auth=True)
            mod_rc = [None]
            mod_lock = threading.Event()
            mod_client = self.create_mqtt_client(self.client_id, self.username, self.password)
            mod_client.on_connect = lambda c, u, f, rc: (mod_rc.__setitem__(0, rc), mod_lock.set())
            mod_client.on_disconnect = lambda c, u, rc: mod_lock.set()
            mod_client.connect_async(self.ip, 36669, 5)
            mod_client.loop_start()
            mod_lock.wait(timeout=timeout)
            mod_client.loop_stop()
            mod_client.disconnect()
            results["modern_dynamic"]["rc"] = mod_rc[0]
            results["modern_dynamic"]["supported"] = (mod_rc[0] == 0)
        except Exception as e:
            _LOGGER.debug("Modern dynamic probe error: %s", e)

        return results

    def ping(self, timeout: float = 3.0) -> dict[str, Any]:
        """Quickly tests if TV broker is listening, accepting TLS, and responding to MQTT packets."""
        results = {
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
            with socket.create_connection((self.ip, 36669), timeout=timeout):
                results["tcp_port_open"] = True
        except Exception as e:
            results["error"] = f"TCP connection failed (TV may be in deep sleep / off): {e}"
            return results

        # 2. Test TLS Handshake
        try:
            ssl_info = self.test_ssl_connection(timeout=timeout)
            results["tls_handshake"] = ssl_info.get("connected", False)
            results["tls_version"] = ssl_info.get("tls_version")
            results["cipher"] = ssl_info.get("cipher")
        except Exception as e:
            results["error"] = f"TLS handshake failed: {e}"
            return results

        # 3. Test MQTT Broker Response (if credentials available)
        if self.access_token and self.client_id and self.username:
            lock = threading.Event()
            rc_holder = [None]
            client = self.create_mqtt_client(self.client_id, self.username, self.access_token)

            def on_conn(c, userdata, flags, rc):
                rc_holder[0] = rc
                lock.set()

            client.on_connect = on_conn
            client.on_message = None
            client.on_disconnect = lambda c, u, rc: lock.set()

            try:
                client.connect_async(self.ip, 36669, 10)
                client.loop_start()
                lock.wait(timeout=timeout)
            finally:
                client.loop_stop()
                client.disconnect()

            results["mqtt_rc"] = rc_holder[0]
            if rc_holder[0] == 0:
                results["mqtt_connected"] = True
                results["mqtt_status"] = "Connection Accepted"
            elif rc_holder[0] is not None:
                results["mqtt_status"] = f"Connection Rejected (rc={rc_holder[0]})"
            else:
                results["mqtt_status"] = "Connection Timeout"
        else:
            results["mqtt_status"] = "Ready for pairing (no stored credentials)"

        # 4. Probe Auth Methods
        auth_probe = self.probe_auth_methods(timeout=1.5)
        results["auth_probe"] = auth_probe

        if auth_probe["legacy_static"]["supported"]:
            results["auth_model"] = "legacy_static"
            results["auth_recommendation"] = (
                "Your TV accepts legacy static credentials ('hisenseservice'). "
                "See the README for recommended legacy integrations."
            )
        elif auth_probe["modern_dynamic"]["supported"] or auth_probe["standard_dynamic"]["supported"]:
            results["auth_model"] = "modern_vidaa"
            results["auth_recommendation"] = (
                "Your TV enforces modern VIDAA OS authentication (dynamic PIN pairing supported)."
            )
        else:
            results["auth_model"] = "unknown"
            results["auth_recommendation"] = (
                "The TV broker rejected initial connection attempts. Ensure TV is awake and connected."
            )

        # 5. Device fingerprint
        results["device_info"] = self.get_device_fingerprint(timeout=1.5)
        return results

    def _safe_set_future_result(self, future: asyncio.Future | None, result: Any) -> None:
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_result, result)
            else:
                future.set_result(result)

    def _safe_set_future_exception(self, future: asyncio.Future | None, exc: Exception) -> None:
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_exception, exc)
            else:
                future.set_exception(exc)

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to TV MQTT Broker")
            if hasattr(self, "topicBrcsBasepath"):
                client.subscribe([
                    (self.topicBrcsBasepath + "ui_service/state", 0),
                    (self.topicBrcsBasepath + "platform_service/actions/volumechange", 0),
                    (self.topicBrcsBasepath + "platform_service/actions/tvsleep", 0),
                    (self.topicMobiBasepath + "ui_service/data/sourcelist", 0),
                    (self.topicMobiBasepath + "ui_service/data/applist", 0),
                    (self.topicMobiBasepath + "ui_service/data/gettvstate", 0),
                    (self.topicMobiBasepath + "platform_service/data/getvolume", 0),
                ])
                if self.on_state_update:
                    threading.Timer(1.0, self.query_initial_state).start()
        else:
            _LOGGER.error("Failed to connect to TV MQTT Broker, rc: %d", rc)
            if self._auth_future and not self._auth_future.done():
                self._safe_set_future_exception(
                    self._auth_future,
                    Exception(f"MQTT connection rejected with code {rc} (Not authorized / invalid credentials)"),
                )
                return

            if rc in (4, 5) and self.refresh_token:
                current_time = time.time()
                with self._refresh_lock:
                    should_refresh = not self._refreshing_token and (current_time - self._last_refresh_attempt > 10)
                if should_refresh:
                    _LOGGER.info("Authentication failed on connect. Refreshing token in background...")
                    threading.Thread(target=self._refresh_token_and_update_creds, daemon=True).start()

    def _refresh_token_and_update_creds(self) -> None:
        with self._refresh_lock:
            if self._refreshing_token or not self.refresh_token:
                return
            self._refreshing_token = True
            self._last_refresh_attempt = time.time()

        try:
            if self.check_and_refresh_token(force=True):
                _LOGGER.info("Token successfully refreshed on connection failure. Updating client credentials.")
                if self.mqtt_client:
                    self.mqtt_client.username_pw_set(username=self.username, password=self.access_token)
                    self.mqtt_client.reconnect()
            else:
                _LOGGER.warning("Token refresh failed. Waiting before next attempt.")
        except Exception as e:
            _LOGGER.error("Error during background token refresh: %s", e)
        finally:
            with self._refresh_lock:
                self._refreshing_token = False

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        self.connected = False
        _LOGGER.info("Disconnected from TV MQTT Broker, rc: %d", rc)
        self._dispatch_disconnected()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="ignore")
        _LOGGER.debug("Message received: %s on topic %s", payload, topic)

        # Check authentication futures
        if self._auth_future and topic == self.topicMobiBasepath + "ui_service/data/authentication":
            self._safe_set_future_result(self._auth_future, payload)
        elif self._auth_code_future and topic == self.topicMobiBasepath + "ui_service/data/authenticationcode":
            self._safe_set_future_result(self._auth_code_future, payload)
        elif self._token_future and topic == self.topicMobiBasepath + "platform_service/data/tokenissuance":
            self._safe_set_future_result(self._token_future, payload)

        # Handle state push callbacks
        if topic in (self.topicBrcsBasepath + "ui_service/state", self.topicMobiBasepath + "ui_service/data/gettvstate"):
            try:
                data = json.loads(payload)
                self._dispatch_state_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing state: %s", e)
        elif topic in (self.topicBrcsBasepath + "platform_service/actions/volumechange", self.topicMobiBasepath + "platform_service/data/getvolume"):
            try:
                data = json.loads(payload)
                self._dispatch_volume_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing volume: %s", e)
        elif topic == self.topicBrcsBasepath + "platform_service/actions/tvsleep":
            self._dispatch_state_update({"statetype": "fake_sleep_0"})
        elif topic == self.topicMobiBasepath + "ui_service/data/sourcelist":
            try:
                data = json.loads(payload)
                self._dispatch_sourcelist_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing sourcelist: %s", e)
        elif topic == self.topicMobiBasepath + "ui_service/data/applist":
            try:
                data = json.loads(payload)
                self._dispatch_applist_update(data)
            except Exception as e:
                _LOGGER.error("Error parsing applist: %s", e)

    async def async_start_auth(self) -> None:
        """Starts the authentication handshake and triggers the TV to show PIN."""
        if self.auth_profile == "legacy":
            self.client_id = "hisenseservice"
            self.username = "hisenseservice"
            self.password = "multimqttservice"
            self.access_token = "multimqttservice"
            self.define_topic_paths()
            return

        if self.auth_profile in ("modern", "vidaa_2024", "vidaa"):
            await self._async_start_auth_internal(use_new_auth=True)
        elif self.auth_profile in ("remotenow", "remotenow_2018", "standard"):
            await self._async_start_auth_internal(use_new_auth=False)
        else:  # auto
            try:
                await self._async_start_auth_internal(use_new_auth=False)
            except Exception as e:
                err_msg = str(e)
                if "code 5" in err_msg or "code 4" in err_msg or "Not authorized" in err_msg:
                    _LOGGER.info("Standard auth failed (%s), auto-falling back to modern VIDAA auth...", err_msg)
                    await self._async_start_auth_internal(use_new_auth=True)
                else:
                    raise

    async def _async_start_auth_internal(self, use_new_auth: bool = False) -> None:
        self.generate_initial_creds(use_new_auth=use_new_auth)
        loop = asyncio.get_running_loop()
        self._loop = loop
        self.mqtt_client = await loop.run_in_executor(
            None, self.create_mqtt_client, self.client_id, self.username, self.password
        )

        self._auth_future = loop.create_future()
        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

        # Wait up to 10 seconds for connection
        for _ in range(50):
            if self.connected:
                break
            if self._auth_future.done() and self._auth_future.exception():
                self.disconnect()
                raise self._auth_future.exception()
            await asyncio.sleep(0.2)

        if not self.connected:
            self.disconnect()
            raise Exception("Cannot connect to TV MQTT Broker (connection timeout)")

        self.mqtt_client.subscribe([
            (self.topicTVUIBasepath + "actions/vidaa_app_connect", 0),
            (self.topicMobiBasepath + "ui_service/data/authentication", 0),
            (self.topicMobiBasepath + "ui_service/data/authenticationcode", 0),
            (self.topicMobiBasepath + "platform_service/data/tokenissuance", 0),
        ])

        # Allow broker time to register subscriptions before publishing
        await asyncio.sleep(0.5)

        # Publish connection message to trigger PIN with retry if TV dropped first frame
        for attempt in range(3):
            self.mqtt_client.publish(
                self.topicTVUIBasepath + "actions/vidaa_app_connect",
                '{"app_version":2,"connect_result":0,"device_type":"Mobile App"}',
            )
            try:
                await asyncio.wait_for(asyncio.shield(self._auth_future), timeout=4.0)
                break
            except TimeoutError:
                if attempt < 2 and not self._auth_future.done():
                    _LOGGER.debug("No response to vidaa_app_connect on attempt %d, retrying...", attempt + 1)
                    await asyncio.sleep(0.5)
                else:
                    self.disconnect()
                    raise Exception("TV authentication request timed out (TV did not show PIN)")
        self._auth_future = None

    async def async_submit_pin(self, pin_code: str) -> dict[str, Any]:
        """Submits the PIN code entered by the user and retrieves token pair."""
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._auth_code_future = loop.create_future()

        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")

        self.mqtt_client.publish(
            self.topicTVUIBasepath + "actions/authenticationcode",
            json.dumps({"authNum": int(pin_code)}),
        )

        try:
            payload_str = await asyncio.wait_for(self._auth_code_future, timeout=15)
            _LOGGER.debug("Received PIN response payload: %s", payload_str)
            payload = json.loads(payload_str)
            if payload.get("result") != 1:
                _LOGGER.error("PIN validation rejected with payload: %s", payload_str)
                raise Exception(f"Incorrect PIN code (TV response: {payload_str})")
        except TimeoutError:
            raise Exception("Timeout waiting for PIN validation")
        finally:
            self._auth_code_future = None

        # Request tokens
        self._token_future = loop.create_future()
        self.mqtt_client.publish(self.topicTVPSBasepath + "data/gettoken", '{"refreshtoken": ""}')
        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/authenticationcodeclose")

        try:
            token_payload_str = await asyncio.wait_for(self._token_future, timeout=15)
            token_data = json.loads(token_payload_str)

            self.access_token = token_data["accesstoken"]
            self.access_token_time = int(token_data["accesstoken_time"])
            self.access_token_duration = int(token_data["accesstoken_duration_day"])
            self.refresh_token = token_data["refreshtoken"]
            self.refresh_token_time = int(token_data["refreshtoken_time"])
            self.refresh_token_duration = int(token_data["refreshtoken_duration_day"])

            return token_data
        except TimeoutError:
            raise Exception("Timeout waiting for tokens")
        finally:
            self._token_future = None
            self.disconnect()

    def check_and_refresh_token(self, force: bool = False) -> bool:
        """Checks if access token is expired (valid for 2 days) and refreshes it synchronously."""
        if self.auth_profile == "legacy":
            return False

        if not self.refresh_token:
            _LOGGER.debug("No refresh token available, skipping refresh.")
            return False

        current_time = time.time()
        expiration_time = self.access_token_time + (2 * 60 * 60)

        if not force and current_time <= expiration_time - 300:
            return False

        _LOGGER.info("Access token expired or close to expiry, refreshing...")
        client = mqtt.Client(client_id=self.client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        client.tls_set(ca_certs=None, certfile=self.certfile, keyfile=self.keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        client.tls_insecure_set(True)
        client.username_pw_set(username=self.username, password=self.refresh_token)

        lock = threading.Event()
        updated_data: dict[str, Any] = {}
        connect_rc = [None]

        def on_refresh_connect(client, userdata, flags, rc):
            connect_rc[0] = rc
            if rc == 0:
                _LOGGER.info("Refresh client connected successfully. Requesting new access token.")
                client.publish(self.topicTVPSBasepath + "data/gettoken", '{"refreshtoken": ""}')
            else:
                _LOGGER.error("Refresh client connection failed, rc: %d", rc)
                lock.set()

        def on_token(client, userdata, msg):
            nonlocal updated_data
            try:
                updated_data = json.loads(msg.payload.decode("utf-8"))
            except Exception as e:
                _LOGGER.error("Error parsing refreshed token: %s", e)
            lock.set()

        client.on_connect = on_refresh_connect
        client.on_message = None
        client.on_disconnect = lambda client, userdata, rc: _LOGGER.debug("Refresh client disconnected: %d", rc)
        client.message_callback_add(self.topicMobiBasepath + "platform_service/data/tokenissuance", on_token)

        try:
            client.connect(self.ip, 36669, 60)
            client.loop_start()

            start = time.time()
            while not lock.is_set() and time.time() - start < 10:
                time.sleep(0.1)
        except (OSError, TimeoutError) as e:
            _LOGGER.debug("TV is offline or unreachable during token refresh: %s", e)
        except Exception as e:
            _LOGGER.error("Unexpected error during refresh client connection: %s", e)
        finally:
            client.loop_stop()
            client.disconnect()

        if updated_data:
            self.access_token = updated_data["accesstoken"]
            self.access_token_time = int(updated_data["accesstoken_time"])
            self.access_token_duration = int(updated_data["accesstoken_duration_day"])
            self.refresh_token = updated_data["refreshtoken"]
            self.refresh_token_time = int(updated_data["refreshtoken_time"])
            self.refresh_token_duration = int(updated_data["refreshtoken_duration_day"])
            self._dispatch_token_refreshed()
            return True

        if connect_rc[0] is not None:
            _LOGGER.error("Failed to refresh token. Connect RC: %d", connect_rc[0])
        return False

    def connect_and_run(self) -> None:
        """Main client connection loop using the access token as password."""
        try:
            self.check_and_refresh_token()
        except Exception as e:
            _LOGGER.debug("Could not refresh token during startup (TV may be in standby): %s", e)

        if not self.access_token or not self.client_id or not self.username:
            _LOGGER.error("Cannot connect to TV: missing credentials (client_id, username, or access_token)")
            return

        self.mqtt_client = self.create_mqtt_client(self.client_id, self.username, self.access_token)
        _LOGGER.info("Starting background MQTT connection loop to TV at %s", self.ip)
        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

    def query_initial_state(self) -> None:
        """Queries initial state, volume, source list, and app list from TV."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/gettvstate", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/getvolume", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/sourcelist", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/applist", "")

    @staticmethod
    def send_wake_on_lan(mac: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> bool:
        """Sends a standard Wake-on-LAN magic packet UDP broadcast."""
        if not mac:
            return False
        cleaned_mac = mac.replace(":", "").replace("-", "").replace(".", "").strip()
        if len(cleaned_mac) != 12:
            return False
        try:
            mac_bytes = bytes.fromhex(cleaned_mac)
            magic_packet = b"\xff" * 6 + mac_bytes * 16
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(magic_packet, (broadcast_ip, port))
            _LOGGER.debug("Sent Wake-on-LAN magic packet to %s", mac)
            return True
        except Exception as e:
            _LOGGER.warning("Failed to send Wake-on-LAN packet to %s: %s", mac, e)
            return False

    def send_key(self, key: str) -> None:
        """Publishes a raw keypress event to the TV."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(self.topicRemoBasepath + "actions/sendkey", key)

    def send_command(self, command: str) -> bool:
        """Sends a key command to the TV, automatically resolving known key aliases."""
        if not command:
            return False
        cmd_clean = command.strip().lower()
        key_to_send = KEY_ALIASES.get(cmd_clean, command.strip().upper())
        self.send_key(key_to_send)
        return True

    def set_volume(self, volume: int) -> None:
        """Sets the absolute volume on the TV (0–100)."""
        if self.connected and self.mqtt_client:
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/changevolume", str(volume))

    def change_source(self, source_id: str) -> None:
        """Switches the active input source on the TV."""
        if self.connected and self.mqtt_client:
            payload = json.dumps({"sourceid": source_id})
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/changesource", payload)

    def launch_app(self, app_id: str, app_name: str, url: str) -> None:
        """Launches an installed Smart TV application."""
        if self.connected and self.mqtt_client:
            payload = json.dumps({"appId": app_id, "name": app_name, "url": url})
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/launchapp", payload)

    async def async_query(self, pub_topic: str, sub_topic: str, payload: str | None = None) -> Any:
        """Publishes a query to the TV and asynchronously awaits the response topic."""
        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def on_msg(client, userdata, msg):
            loop.call_soon_threadsafe(future.set_result, msg.payload.decode("utf-8"))

        self.mqtt_client.message_callback_add(sub_topic, on_msg)
        self.mqtt_client.subscribe(sub_topic)
        self.mqtt_client.publish(pub_topic, payload)

        try:
            result = await asyncio.wait_for(future, timeout=10)
            return json.loads(result)
        except Exception as e:
            _LOGGER.error("Error querying %s: %s", pub_topic, e)
            raise e
        finally:
            self.mqtt_client.unsubscribe(sub_topic)
            self.mqtt_client.message_callback_remove(sub_topic)

    def disconnect(self) -> None:
        """Cleanly disconnects the MQTT client and stops the background network thread."""
        if self.mqtt_client:
            try:
                self.mqtt_client.on_connect = None
                self.mqtt_client.on_disconnect = None
                self.mqtt_client.on_message = None
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                _LOGGER.debug("Error during client disconnect: %s", e)
            finally:
                self.mqtt_client = None
                self.connected = False
