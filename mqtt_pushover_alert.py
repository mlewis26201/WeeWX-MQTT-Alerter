import paho.mqtt.client as mqtt
import requests
import json
import sqlite3
import time
import logging
import os

# --- Configuration ---
def load_settings_from_db(db_path='settings.db'):
    # If DB does not exist or is empty, pre-populate from environment variables
    db_exists = os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    cursor.execute('SELECT COUNT(*) FROM settings')
    settings_count = cursor.fetchone()[0]
    # Pre-populate if missing/empty
    if not db_exists or settings_count == 0:
        env_defaults = {
            'MQTT_BROKER': os.environ.get('MQTT_BROKER', ''),
            'MQTT_PORT': os.environ.get('MQTT_PORT', '1883'),
            'MQTT_USERNAME': os.environ.get('MQTT_USERNAME', ''),
            'MQTT_PASSWORD': os.environ.get('MQTT_PASSWORD', ''),
            'MQTT_TOPIC': os.environ.get('MQTT_TOPIC', 'weather'),
            'PUSHOVER_USER_KEY': os.environ.get('PUSHOVER_USER_KEY', ''),
            'PUSHOVER_API_TOKEN': os.environ.get('PUSHOVER_API_TOKEN', ''),
        }
        for k, v in env_defaults.items():
            cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, v))
        conn.commit()
    # Required keys
    required_keys = [
        'MQTT_BROKER', 'MQTT_PORT', 'MQTT_USERNAME', 'MQTT_PASSWORD',
        'PUSHOVER_USER_KEY', 'PUSHOVER_API_TOKEN', 'MQTT_TOPIC'
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
    # Ensure direction column exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        threshold REAL NOT NULL,
        message TEXT NOT NULL,
        max_alerts INTEGER NOT NULL DEFAULT 1,
        period_seconds INTEGER NOT NULL DEFAULT 3600,
        direction TEXT NOT NULL DEFAULT 'above'
    )''')
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN direction TEXT NOT NULL DEFAULT 'above'")
    except sqlite3.OperationalError:
        pass  # Already exists
    # Add alert for MQTT_TOPIC in settings if not already present
    settings = load_settings_from_db(db_path)
    mqtt_topic = settings.get('MQTT_TOPIC') or 'weather'
    if mqtt_topic:
        cursor.execute('SELECT COUNT(*) FROM alerts WHERE topic=?', (mqtt_topic,))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''INSERT INTO alerts (topic, threshold, message, max_alerts, period_seconds, direction) VALUES (?, ?, ?, ?, ?, ?)''',
                (mqtt_topic, 0, 'Default alert for {value}', 1, 3600, 'above'))
            conn.commit()
    cursor.execute('SELECT id, topic, threshold, message, max_alerts, period_seconds, direction FROM alerts')
    alerts = [dict(id=row[0], topic=row[1], threshold=row[2], message=row[3], max_alerts=row[4], period_seconds=row[5], direction=row[6]) for row in cursor.fetchall()]
    conn.close()
    return alerts

def can_send_alert(alert_id, max_alerts, period_seconds, db_path='settings.db'):
    import time
    now = int(time.time())
    window_start = now - period_seconds
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM alert_logs WHERE alert_id=? AND timestamp>=?', (alert_id, window_start))
    count = cursor.fetchone()[0]
    conn.close()
    return count < max_alerts

def log_alert(alert_id, db_path='settings.db'):
    import time
    now = int(time.time())
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO alert_logs (alert_id, timestamp) VALUES (?, ?)', (alert_id, now))
    conn.commit()
    conn.close()

def log_seen_topic(topic, db_path='settings.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS mqtt_topics (
        topic TEXT PRIMARY KEY
    )''')
    cursor.execute('INSERT OR IGNORE INTO mqtt_topics (topic) VALUES (?)', (topic,))
    conn.commit()
    conn.close()

# --- Pushover Notification Function ---
def send_pushover_notification(message, topic=None, value=None):
    # Always include topic and value in the notification
    if topic is not None and value is not None:
        message = f"[{topic}] {message} (Value: {value})"
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
    logging.info(f"Connected to MQTT broker with result code {rc}")
    # Subscribe to all unique topics in alerts, including subtopics
    for alert in ALERTS:
        topic = alert['topic']
        if not topic.endswith('#'):
            topic = topic.rstrip('/') + '/#'  # Subscribe to all subtopics
        logging.info(f"Subscribing to topic: {topic}")
        client.subscribe(topic)


def on_message(client, userdata, msg):
    try:
        log_seen_topic(msg.topic)
        payload = msg.payload.decode('utf-8')
        logging.info(f"MQTT message received on topic '{msg.topic}': {payload}")
        try:
            value = float(payload)
        except Exception as e:
            logging.error(f"Could not convert payload to float: {payload} ({e})")
            return
        for alert in ALERTS:
            if msg.topic == alert['topic']:
                direction = alert.get('direction', 'above')
                threshold = alert['threshold']
                triggered = False
                if direction == 'above' and value > threshold:
                    triggered = True
                elif direction == 'below' and value < threshold:
                    triggered = True
                if triggered:
                    logging.info(f"Alert triggered for topic '{msg.topic}' with value {value} (threshold {threshold}, direction {direction})")
                    if can_send_alert(alert['id'], alert['max_alerts'], alert['period_seconds']):
                        # Always include topic and value in the notification
                        message = alert['message'].replace('{value}', str(value)).replace('{threshold}', str(threshold))
                        send_pushover_notification(message, topic=msg.topic, value=value)
                        log_alert(alert['id'])
                        logging.info(f"Pushover notification sent for alert {alert['id']} on topic '{msg.topic}' with value {value} (threshold {threshold}, direction {direction})")
                    else:
                        logging.info(f"Rate limit reached for alert {alert['id']} (topic: {alert['topic']})")
    except Exception as e:
        logging.error(f"Error processing message on topic '{msg.topic}': {e}")

# --- Main ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
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
    MQTT_USERNAME = settings['MQTT_USERNAME']
    MQTT_PASSWORD = settings['MQTT_PASSWORD']
    PUSHOVER_USER_KEY = settings['PUSHOVER_USER_KEY']
    PUSHOVER_API_TOKEN = settings['PUSHOVER_API_TOKEN']
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    print(f"Listening to MQTT topics for alerts...")
    client.loop_forever()
