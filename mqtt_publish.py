import network
from time import sleep
from umqtt.simple import MQTTClient

SSID = "KMD757_Group_5"
PASSWORD = "Hardware@group5"
BROKER_IP = "192.168.5.253"

def connect_wlan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    while not wlan.isconnected():
        print("Connecting to WiFi...")
        sleep(1)
    print("WiFi connected IP:", wlan.ifconfig()[0])

def connect_mqtt(client_id, port=1883, callback=None):
    client = MQTTClient(client_id, BROKER_IP, port=port)
    if callback:
        client.set_callback(callback)
    client.connect()
    print("MQTT connected to", BROKER_IP, "port", port)
    return client

# first connect wifi
connect_wlan()

# one client for local calculated hrv results publishing
mqtt_client = connect_mqtt("pico_hr", port=1883)

# another one client for Kubios (to be initialized later with callback)
# kubios_client = connect_mqtt("pico_kubios", port=21883, callback=...) in kubios.py 
