import ssl
import time
import json
import logging
import hashlib
import random
import os
import paho.mqtt.client as mqtt
import asyncio

_LOGGER = logging.getLogger(__name__)

class HisenseTvClient:
    def __init__(self, ip, mac=None, client_id=None, username=None, password=None, 
                 access_token=None, access_token_time=0, access_token_duration=0,
                 refresh_token=None, refresh_token_time=0, refresh_token_duration=0):
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

        # Locate certs packaged in the custom component
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.certfile = os.path.join(script_dir, "certs", "cert.pem")
        self.keyfile = os.path.join(script_dir, "certs", "key.pem")

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

        self.topicTVUIBasepath = ""
        self.topicTVPSBasepath = ""
        self.topicMobiBasepath = ""
        self.topicBrcsBasepath = "/remoteapp/mobile/broadcast/"
        self.topicRemoBasepath = ""
        
        if self.client_id:
            self.define_topic_paths()

    def define_topic_paths(self):
        self.topicTVUIBasepath = f"/remoteapp/tv/ui_service/{self.client_id}/"
        self.topicTVPSBasepath = f"/remoteapp/tv/platform_service/{self.client_id}/"
        self.topicMobiBasepath = f"/remoteapp/mobile/{self.client_id}/"
        self.topicRemoBasepath = f"/remoteapp/tv/remote_service/{self.client_id}/"

    def generate_initial_creds(self):
        timestamp = int(time.time())
        # Always generate a random MAC address for the client ID to prevent conflicts
        mac = ':'.join(f'{random.randint(0, 255):02x}' for _ in range(6)).upper()

        second_hash = hashlib.md5(f"38D65DC30F45109A369A86FCE866A85B${mac}".encode("utf-8")).hexdigest().upper()
        last_digit_of_cross_sum = sum(int(digit) for digit in str(timestamp)) % 10
        third_hash = hashlib.md5(f"his{last_digit_of_cross_sum}h*i&s%e!r^v0i1c9".encode("utf-8")).hexdigest().upper()
        fourth_hash = hashlib.md5(f"{timestamp}${third_hash[:6]}".encode("utf-8")).hexdigest().upper()

        self.username = f"his${timestamp}"
        self.password = fourth_hash
        self.client_id = f"{mac}$his${second_hash[:6]}_vidaacommon_001"
        self.define_topic_paths()

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
            if rc in (4, 5):
                _LOGGER.info("Authentication failed on connect. Refreshing token in background...")
                import threading
                threading.Thread(target=self._refresh_token_and_update_creds, daemon=True).start()

    def _refresh_token_and_update_creds(self):
        try:
            if self.check_and_refresh_token():
                _LOGGER.info("Token successfully refreshed on connection failure. Updating client credentials.")
                self.mqtt_client.username_pw_set(username=self.username, password=self.access_token)
        except Exception as e:
            _LOGGER.error(f"Error during background token refresh: {e}")

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
            self._auth_future.set_result(payload)
        elif self._auth_code_future and topic == self.topicMobiBasepath + 'ui_service/data/authenticationcode':
            self._auth_code_future.set_result(payload)
        elif self._token_future and topic == self.topicMobiBasepath + 'platform_service/data/tokenissuance':
            self._token_future.set_result(payload)

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
        self.mqtt_client = self.create_mqtt_client(self.client_id, self.username, self.password)

        loop = asyncio.get_running_loop()
        self._auth_future = loop.create_future()

        self.mqtt_client.connect_async(self.ip, 36669, 60)
        self.mqtt_client.loop_start()

        # Wait up to 10 seconds for connection
        for _ in range(50):
            if self.connected:
                break
            await asyncio.sleep(0.2)

        if not self.connected:
            self.mqtt_client.loop_stop()
            raise Exception("Cannot connect to TV MQTT Broker")

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
        except asyncio.TimeoutError:
            self.mqtt_client.loop_stop()
            raise Exception("TV authentication request timed out")
        finally:
            self._auth_future = None

    async def async_submit_pin(self, pin_code):
        """Submits the PIN code entered by the user."""
        loop = asyncio.get_running_loop()
        self._auth_code_future = loop.create_future()

        self.mqtt_client.publish(self.topicTVUIBasepath + "actions/authenticationcode", 
                                  json.dumps({"authNum": int(pin_code)}))

        try:
            payload_str = await asyncio.wait_for(self._auth_code_future, timeout=15)
            payload = json.loads(payload_str)
            if payload.get("result") != 1:
                raise Exception("Incorrect PIN code")
        except asyncio.TimeoutError:
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
        except asyncio.TimeoutError:
            raise Exception("Timeout waiting for tokens")
        finally:
            self._token_future = None
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

    def check_and_refresh_token(self):
        """Checks if access token is expired (valid for 2 hours) and refreshes it synchronously."""
        current_time = time.time()
        expiration_time = self.access_token_time + (2 * 60 * 60) # 2 hours duration
        
        # If token is still valid, return
        if current_time <= expiration_time - 300: # 5 minutes buffer
            return False

        _LOGGER.info("Access token expired or close to expiry, refreshing...")
        client = self.create_mqtt_client(self.client_id, self.username, self.refresh_token)
        
        # Synchronous wait wrapper
        import threading
        lock = threading.Event()
        updated_data = {}

        def on_token(client, userdata, msg):
            nonlocal updated_data
            try:
                updated_data = json.loads(msg.payload.decode('utf-8'))
            except Exception as e:
                _LOGGER.error(f"Error parsing refreshed token: {e}")
            lock.set()

        client.message_callback_add(self.topicMobiBasepath + 'platform_service/data/tokenissuance', on_token)
        client.connect(self.ip, 36669, 60)
        client.loop_start()
        
        client.subscribe(self.topicMobiBasepath + 'platform_service/data/tokenissuance')
        client.publish(f"/remoteapp/tv/platform_service/{self.client_id}/data/gettoken", 
                       json.dumps({"refreshtoken": self.refresh_token}))

        # Synchronous wait in executor (will block calling thread but safe when run in executor)
        start = time.time()
        while not lock.is_set() and time.time() - start < 10:
            time.sleep(0.1)

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
        else:
            _LOGGER.error("Failed to refresh token")
            return False

    def connect_and_run(self):
        """Main client connection loop using the access token as password."""
        try:
            self.check_and_refresh_token()
        except Exception as e:
            _LOGGER.warning(f"Failed to check/refresh token during startup: {e}")

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
