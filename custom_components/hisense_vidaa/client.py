import asyncio
import hashlib
import json
import logging
import os
import random
import socket
import ssl
import time

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class HisenseTvClient:
    def __init__(self, ip, mac=None, client_id=None, username=None, password=None,
                 access_token=None, access_token_time=0, access_token_duration=0,
                 refresh_token=None, refresh_token_time=0, refresh_token_duration=0,
                 certfile=None, keyfile=None):
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

        # Determine cert locations: custom paths > local certs/ dir > repo root certs/ > /config/certs or /config/ssl fallback
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_cert = os.path.join(script_dir, "certs", "cert.pem")
        default_key = os.path.join(script_dir, "certs", "key.pem")
        repo_root_cert = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "certs", "cert.pem")
        repo_root_key = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "certs", "key.pem")

        if certfile:
            self.certfile = os.path.abspath(certfile)
        elif os.path.exists(default_cert):
            self.certfile = default_cert
        elif os.path.exists(repo_root_cert):
            self.certfile = repo_root_cert
        elif os.path.exists("/config/certs/cert.pem"):
            self.certfile = "/config/certs/cert.pem"
        elif os.path.exists("/config/ssl/cert.pem"):
            self.certfile = "/config/ssl/cert.pem"
        else:
            self.certfile = default_cert

        if keyfile:
            self.keyfile = os.path.abspath(keyfile)
        elif os.path.exists(default_key):
            self.keyfile = default_key
        elif os.path.exists(repo_root_key):
            self.keyfile = repo_root_key
        elif os.path.exists("/config/certs/key.pem"):
            self.keyfile = "/config/certs/key.pem"
        elif os.path.exists("/config/ssl/key.pem"):
            self.keyfile = "/config/ssl/key.pem"
        else:
            self.keyfile = default_key

        self.mqtt_client = None
        self.connected = False
        self.on_state_update = None
        self.on_volume_update = None
        self.on_sourcelist_update = None
        self.on_applist_update = None
        self.on_disconnected_callback = None
        self.on_token_refreshed = None

        self._auth_future = None
        self._auth_code_future = None
        self._token_future = None
        self._loop = None
        self._refreshing_token = False
        self._last_refresh_attempt = 0
        import threading
        self._refresh_lock = threading.Lock()

        self.topicTVUIBasepath = ""
        self.topicTVPSBasepath = ""
        self.topicMobiBasepath = ""
        self.topicBrcsBasepath = "/remoteapp/mobile/broadcast/"
        self.topicRemoBasepath = ""

        if self.client_id:
            self.define_topic_paths()

    def validate_certificates(self):
        """Verifies that the SSL certificate and private key files exist and are readable."""
        if not os.path.isfile(self.certfile):
            raise FileNotFoundError(
                f"SSL Certificate file not found: '{self.certfile}'. "
                "Please place 'cert.pem' in the 'certs/' folder or specify --cert."
            )
        if not os.path.isfile(self.keyfile):
            raise FileNotFoundError(
                f"SSL Private Key file not found: '{self.keyfile}'. "
                "Please place 'key.pem' in the 'certs/' folder or specify --key."
            )

    def test_ssl_connection(self, timeout=5.0):
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

    def ping(self, timeout=3.0):
        """Quickly tests if the TV MQTT broker is listening, accepting TLS, and responding to MQTT packets."""
        results = {
            "tcp_port_open": False,
            "tls_handshake": False,
            "tls_version": None,
            "cipher": None,
            "mqtt_connected": False,
            "mqtt_rc": None,
            "mqtt_status": None,
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
            import threading
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

        # 4. Probe Legacy Static Authentication Compatibility
        import threading
        legacy_rc = [None]
        leg_lock = threading.Event()
        leg_client = mqtt.Client(client_id="hisenseservice", clean_session=True, protocol=mqtt.MQTTv311)
        leg_client.tls_set(ca_certs=None, certfile=self.certfile, keyfile=self.keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        leg_client.tls_insecure_set(True)
        leg_client.username_pw_set(username="hisenseservice", password="multimqttservice")

        def on_leg_conn(c, userdata, flags, rc):
            legacy_rc[0] = rc
            leg_lock.set()

        leg_client.on_connect = on_leg_conn
        leg_client.on_disconnect = lambda c, u, rc: leg_lock.set()

        try:
            leg_client.connect_async(self.ip, 36669, 5)
            leg_client.loop_start()
            leg_lock.wait(timeout=1.5)
        except Exception:
            pass
        finally:
            leg_client.loop_stop()
            leg_client.disconnect()

        results["legacy_rc"] = legacy_rc[0]
        if legacy_rc[0] == 0:
            results["auth_model"] = "legacy_static"
            results["auth_recommendation"] = (
                "Your TV accepts legacy static credentials ('hisenseservice'). "
                "You can use legacy MQTT integrations such as 'ha_hisense_tv' (github.com/alexmohr/ha_hisense_tv) "
                "or this integration without PIN pairing."
            )
        else:
            results["auth_model"] = "modern_vidaa"
            results["auth_recommendation"] = (
                "Your TV enforces modern VIDAA OS authentication (static 'hisenseservice' logins rejected). "
                "Dynamic PIN pairing via this 'hisense_vidaa' integration is required."
            )

        return results

    def _safe_set_future_result(self, future, result):
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_result, result)
            else:
                future.set_result(result)

    def _safe_set_future_exception(self, future, exc):
        if future and not future.done():
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(future.set_exception, exc)
            else:
                future.set_exception(exc)

    def define_topic_paths(self):
        self.topicTVUIBasepath = f"/remoteapp/tv/ui_service/{self.client_id}/"
        self.topicTVPSBasepath = f"/remoteapp/tv/platform_service/{self.client_id}/"
        self.topicMobiBasepath = f"/remoteapp/mobile/{self.client_id}/"
        self.topicRemoBasepath = f"/remoteapp/tv/remote_service/{self.client_id}/"

    def generate_initial_creds(self):
        timestamp = int(time.time())
        # Use provided MAC if available, otherwise generate a random MAC
        if self.mac and len(self.mac.replace(":", "").replace("-", "")) == 12:
            cleaned = self.mac.replace("-", ":").upper()
            mac = cleaned
        else:
            mac = ':'.join(f'{random.randint(0, 255):02x}' for _ in range(6)).upper()

        second_hash = hashlib.md5(f"38D65DC30F45109A369A86FCE866A85B${mac}".encode()).hexdigest().upper()
        last_digit_of_cross_sum = sum(int(digit) for digit in str(timestamp)) % 10
        third_hash = hashlib.md5(f"his{last_digit_of_cross_sum}h*i&s%e!r^v0i1c9".encode()).hexdigest().upper()
        fourth_hash = hashlib.md5(f"{timestamp}${third_hash[:6]}".encode()).hexdigest().upper()

        self.username = f"his${timestamp}"
        self.password = fourth_hash
        self.client_id = f"{mac}$his${second_hash[:6]}_vidaacommon_001"
        self.define_topic_paths()
        _LOGGER.debug(f"Generated initial creds - Client ID: {self.client_id}, Username: {self.username}")

    def create_mqtt_client(self, client_id, username, password):
        client = mqtt.Client(client_id=client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        client.tls_set(ca_certs=None, certfile=self.certfile, keyfile=self.keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        client.tls_insecure_set(True)
        client.username_pw_set(username=username, password=password)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        return client

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to TV MQTT Broker")
            if hasattr(self, 'topicBrcsBasepath'):
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
                    import threading
                    threading.Timer(1.0, self.query_initial_state).start()
        else:
            _LOGGER.error(f"Failed to connect to TV MQTT Broker, rc: {rc}")
            if self._auth_future and not self._auth_future.done():
                self._safe_set_future_exception(self._auth_future, Exception(f"MQTT connection rejected with code {rc} (Not authorized / invalid credentials)"))
                return

            if rc in (4, 5) and self.refresh_token:
                current_time = time.time()
                with self._refresh_lock:
                    should_refresh = not self._refreshing_token and (current_time - self._last_refresh_attempt > 10)
                if should_refresh:
                    _LOGGER.info("Authentication failed on connect. Refreshing token in background...")
                    import threading
                    threading.Thread(target=self._refresh_token_and_update_creds, daemon=True).start()

    def _refresh_token_and_update_creds(self):
        with self._refresh_lock:
            if self._refreshing_token or not self.refresh_token:
                _LOGGER.debug("Token refresh already in progress or no refresh token, skipping spawn.")
                return
            self._refreshing_token = True
            self._last_refresh_attempt = time.time()

        try:
            if self.check_and_refresh_token(force=True):
                _LOGGER.info("Token successfully refreshed on connection failure. Updating client credentials.")
                self.mqtt_client.username_pw_set(username=self.username, password=self.access_token)
                self.mqtt_client.reconnect()
            else:
                _LOGGER.warning("Token refresh failed. Waiting before next attempt.")
        except Exception as e:
            _LOGGER.error(f"Error during background token refresh: {e}")
        finally:
            with self._refresh_lock:
                self._refreshing_token = False

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        _LOGGER.info(f"Disconnected from TV MQTT Broker, rc: {rc}")
        if self.on_disconnected_callback:
            self.on_disconnected_callback()

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        _LOGGER.debug(f"Message received: {payload} on topic {topic}")

        # Check authentication futures
        if self._auth_future and topic == self.topicMobiBasepath + 'ui_service/data/authentication':
            self._safe_set_future_result(self._auth_future, payload)
        elif self._auth_code_future and topic == self.topicMobiBasepath + 'ui_service/data/authenticationcode':
            self._safe_set_future_result(self._auth_code_future, payload)
        elif self._token_future and topic == self.topicMobiBasepath + 'platform_service/data/tokenissuance':
            self._safe_set_future_result(self._token_future, payload)

        # Handle state push callbacks
        if topic in (self.topicBrcsBasepath + "ui_service/state", self.topicMobiBasepath + "ui_service/data/gettvstate"):
            try:
                data = json.loads(payload)
                if self.on_state_update:
                    self.on_state_update(data)
            except Exception as e:
                _LOGGER.error(f"Error parsing state: {e}")
        elif topic in (self.topicBrcsBasepath + "platform_service/actions/volumechange", self.topicMobiBasepath + "platform_service/data/getvolume"):
            try:
                data = json.loads(payload)
                if self.on_volume_update:
                    self.on_volume_update(data)
            except Exception as e:
                _LOGGER.error(f"Error parsing volume: {e}")
        elif topic == self.topicBrcsBasepath + "platform_service/actions/tvsleep":
            if self.on_state_update:
                self.on_state_update({"statetype": "fake_sleep_0"})
        elif topic == self.topicMobiBasepath + "ui_service/data/sourcelist":
            try:
                data = json.loads(payload)
                if self.on_sourcelist_update:
                    self.on_sourcelist_update(data)
            except Exception as e:
                _LOGGER.error(f"Error parsing sourcelist: {e}")
        elif topic == self.topicMobiBasepath + "ui_service/data/applist":
            try:
                data = json.loads(payload)
                if self.on_applist_update:
                    self.on_applist_update(data)
            except Exception as e:
                _LOGGER.error(f"Error parsing applist: {e}")

    async def async_start_auth(self):
        """Starts the authentication handshake and triggers the TV to show PIN."""
        self.generate_initial_creds()
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
                self.mqtt_client.loop_stop()
                raise self._auth_future.exception()
            await asyncio.sleep(0.2)

        if not self.connected:
            self.mqtt_client.loop_stop()
            raise Exception("Cannot connect to TV MQTT Broker (connection timeout)")

        self.mqtt_client.subscribe([
            (self.topicTVUIBasepath + 'actions/vidaa_app_connect', 0),
            (self.topicMobiBasepath + 'ui_service/data/authentication', 0),
            (self.topicMobiBasepath + 'ui_service/data/authenticationcode', 0),
            (self.topicMobiBasepath + 'platform_service/data/tokenissuance', 0),
        ])

        # Publish connection message to trigger PIN
        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/vidaa_app_connect",
                                  '{"app_version":2,"connect_result":0,"device_type":"Mobile App"}')

        # Wait for TV response triggering PIN
        try:
            await asyncio.wait_for(self._auth_future, timeout=15)
        except TimeoutError:
            self.mqtt_client.loop_stop()
            raise Exception("TV authentication request timed out")
        finally:
            self._auth_future = None

    async def async_submit_pin(self, pin_code):
        """Submits the PIN code entered by the user."""
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._auth_code_future = loop.create_future()

        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/authenticationcode",
                                  json.dumps({"authNum": int(pin_code)}))

        try:
            payload_str = await asyncio.wait_for(self._auth_code_future, timeout=15)
            _LOGGER.debug(f"Received PIN response payload: {payload_str}")
            payload = json.loads(payload_str)
            if payload.get("result") != 1:
                _LOGGER.error(f"PIN validation rejected with payload: {payload_str}")
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
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

    def check_and_refresh_token(self, force=False):
        """Checks if access token is expired (valid for 2 hours) and refreshes it synchronously."""
        if not self.refresh_token:
            _LOGGER.debug("No refresh token available, skipping refresh.")
            return False

        current_time = time.time()
        expiration_time = self.access_token_time + (2 * 60 * 60) # 2 hours duration

        # If token is still valid, return (unless forced)
        if not force and current_time <= expiration_time - 300: # 5 minutes buffer
            return False

        _LOGGER.info("Access token expired or close to expiry, refreshing...")

        # We must use the exact registered client ID because the TV broker validates it against the pairing whitelist
        client = mqtt.Client(client_id=self.client_id, clean_session=True, protocol=mqtt.MQTTv311, transport="tcp")
        client.tls_set(ca_certs=None, certfile=self.certfile, keyfile=self.keyfile, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLS)
        client.tls_insecure_set(True)
        client.username_pw_set(username=self.username, password=self.refresh_token)

        # Synchronous wait wrapper
        import threading
        lock = threading.Event()
        updated_data = {}
        connect_rc = [None]

        def on_refresh_connect(client, userdata, flags, rc):
            _LOGGER.debug(f"Refresh client connection result: {rc}")
            connect_rc[0] = rc
            if rc == 0:
                client.subscribe(self.topicMobiBasepath + 'platform_service/data/tokenissuance')
                client.publish(f"/remoteapp/tv/platform_service/{self.client_id}/data/gettoken",
                               json.dumps({"refreshtoken": self.refresh_token}))
            else:
                lock.set()

        def on_token(client, userdata, msg):
            nonlocal updated_data
            _LOGGER.debug(f"Refresh client received token payload: {msg.payload}")
            try:
                updated_data = json.loads(msg.payload.decode('utf-8'))
            except Exception as e:
                _LOGGER.error(f"Error parsing refreshed token: {e}")
            lock.set()

        client.on_connect = on_refresh_connect
        client.on_message = None
        client.on_disconnect = lambda client, userdata, rc: _LOGGER.debug(f"Refresh client disconnected: {rc}")
        client.message_callback_add(self.topicMobiBasepath + 'platform_service/data/tokenissuance', on_token)

        try:
            client.connect(self.ip, 36669, 60)
            client.loop_start()

            # Wait up to 10 seconds
            start = time.time()
            while not lock.is_set() and time.time() - start < 10:
                time.sleep(0.1)
        except (OSError, TimeoutError) as e:
            _LOGGER.debug(f"TV is offline or unreachable during token refresh: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error during refresh client connection/loop: {e}")
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
            if self.on_token_refreshed:
                self.on_token_refreshed(self)
            return True

        if connect_rc[0] is not None:
            _LOGGER.error(f"Failed to refresh token. Connect RC: {connect_rc[0]}")
        return False

    def connect_and_run(self):
        """Main client connection loop using the access token as password."""
        try:
            self.check_and_refresh_token()
        except Exception as e:
            _LOGGER.debug(f"Could not refresh token during startup (TV may be in standby): {e}")

        self.mqtt_client = self.create_mqtt_client(self.client_id, self.username, self.access_token)
        _LOGGER.info("Starting background MQTT connection loop to TV")
        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

    def query_initial_state(self):
        if self.connected:
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/gettvstate", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/getvolume", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/sourcelist", "")
            time.sleep(0.1)
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/applist", "")

    def send_key(self, key):
        if self.connected:
            self.mqtt_client.publish(self.topicRemoBasepath + "actions/sendkey", key)

    def set_volume(self, volume):
        if self.connected:
            self.mqtt_client.publish(self.topicTVPSBasepath + "actions/changevolume", str(volume))

    def change_source(self, source_id):
        if self.connected:
            payload = json.dumps({"sourceid": source_id})
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/changesource", payload)

    def launch_app(self, app_id, app_name, url):
        if self.connected:
            payload = json.dumps({"appId": app_id, "name": app_name, "url": url})
            self.mqtt_client.publish(self.topicTVUIBasepath + "actions/launchapp", payload)

    async def async_query(self, pub_topic, sub_topic, payload=None):
        if not self.mqtt_client:
            raise Exception("MQTT client not initialized")

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def on_msg(client, userdata, msg):
            loop.call_soon_threadsafe(future.set_result, msg.payload.decode('utf-8'))

        self.mqtt_client.message_callback_add(sub_topic, on_msg)
        self.mqtt_client.subscribe(sub_topic)
        self.mqtt_client.publish(pub_topic, payload)

        try:
            result = await asyncio.wait_for(future, timeout=10)
            return json.loads(result)
        except Exception as e:
            _LOGGER.error(f"Error querying {pub_topic}: {e}")
            raise e
        finally:
            self.mqtt_client.unsubscribe(sub_topic)
            self.mqtt_client.message_callback_remove(sub_topic)

    def disconnect(self):
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
