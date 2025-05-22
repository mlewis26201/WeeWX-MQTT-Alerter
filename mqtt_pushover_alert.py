import paho.mqtt.client as mqtt
import requests
import json
import sqlite3

# --- Configuration ---
def load_settings_from_db(db_path='settings.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    # Required keys
    required_keys = [
        'MQTT_BROKER', 'MQTT_PORT', 'PUSHOVER_USER_KEY', 'PUSHOVER_API_TOKEN'
    ]
    settings = {}
    for key in required_keys:
        cursor.execute('SELECT value FROM settings WHERE key=?', (key,))
        row = cursor.fetchone()
        if row is None:
            raise Exception(f"Missing setting: {key} in database.")
        settings[key] = row[0]
    conn.close()
    # Convert types
    settings['MQTT_PORT'] = int(settings['MQTT_PORT'])
    return settings

def load_alerts_from_db(db_path='settings.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        threshold REAL NOT NULL,
        message TEXT NOT NULL
    )''')
    cursor.execute('SELECT topic, threshold, message FROM alerts')
    alerts = [dict(topic=row[0], threshold=row[1], message=row[2]) for row in cursor.fetchall()]
    conn.close()
    return alerts

# --- Pushover Notification Function ---
def send_pushover_notification(message):
    url = 'https://api.pushover.net/1/messages.json'
    data = {
        'token': PUSHOVER_API_TOKEN,
        'user': PUSHOVER_USER_KEY,
        'message': message
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"Failed to send notification: {response.text}")

# --- MQTT Callback ---
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to all unique topics in alerts
    for alert in ALERTS:
        client.subscribe(alert['topic'])


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        value = float(payload)
        print(f"Received value: {value} on topic: {msg.topic}")
        for alert in ALERTS:
            if msg.topic == alert['topic'] and value > alert['threshold']:
                send_pushover_notification(alert['message'].replace('{value}', str(value)).replace('{threshold}', str(alert['threshold'])))
    except Exception as e:
        print(f"Error processing message: {e}")

# --- Main ---
if __name__ == '__main__':
    try:
        settings = load_settings_from_db()
        ALERTS = load_alerts_from_db()
        if not ALERTS:
            print("No alerts configured in the database.")
    except Exception as e:
        print(f"Error loading settings or alerts: {e}")
        exit(1)
    MQTT_BROKER = settings['MQTT_BROKER']
    MQTT_PORT = settings['MQTT_PORT']
    PUSHOVER_USER_KEY = settings['PUSHOVER_USER_KEY']
    PUSHOVER_API_TOKEN = settings['PUSHOVER_API_TOKEN']
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    print(f"Listening to MQTT topics for alerts...")
    client.loop_forever()
