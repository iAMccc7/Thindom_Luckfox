import paho.mqtt.client as mqtt
import time
import logging

class MqttHandler:
    def __init__(self, broker, port, client_id):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.connected = False
        
        # Callback for incoming messages
        self.on_message_callback = None

    def start(self, subscriptions=None, callback=None):
        """
        Start the MQTT client.
        :param subscriptions: List of topics to subscribe to
        :param callback: Function to call when a message is received
        """
        self.subscriptions = subscriptions or []
        self.on_message_callback = callback
        
        if callback:
            self.client.on_message = self.on_message

        try:
            print(f"[MQTT] Connecting to {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"[MQTT] Connection failed: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"[MQTT] Connected successfully (Code: {rc})")
            # Subscribe to topics on reconnect
            for topic in self.subscriptions:
                self.client.subscribe(topic)
                print(f"[MQTT] Subscribed to: {topic}")
        else:
            print(f"[MQTT] Connection failed with code {rc}")

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        print(f"[MQTT] Disconnected (Code: {rc})")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode('utf-8')
        print(f"\n[MQTT] Received message on {msg.topic}")
        if self.on_message_callback:
            self.on_message_callback(msg.topic, payload)

    def publish(self, topic, payload):
        if not self.connected:
            print("[MQTT] Warning: Not connected. Attempting to publish anyway...")
        
        try:
            self.client.publish(topic, payload)
            print(f"[MQTT] Published to {topic}")
            return True
        except Exception as e:
            print(f"[MQTT] Publish failed: {e}")
            return False

