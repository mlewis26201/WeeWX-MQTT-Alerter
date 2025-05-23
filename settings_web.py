from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file, jsonify
import sqlite3
import logging
from datetime import datetime

DB_PATH = 'settings.db'
REQUIRED_KEYS = [
    'MQTT_BROKER', 'MQTT_PORT', 'MQTT_TOPIC', 'MQTT_USERNAME', 'MQTT_PASSWORD',
    'PUSHOVER_USER_KEY', 'PUSHOVER_API_TOKEN'
]

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this for production
logging.basicConfig(level=logging.DEBUG)

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    print('Exception:', e)
    traceback.print_exc()
    return f"Internal Server Error: {e}", 500

BOOTSTRAP_HEAD = '''
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background: #f8f9fa; }
footer { margin-top:2em; text-align:center; color:#888; }
.card { margin-bottom: 2em; }
</style>
'''

FOOTER_HTML = '<footer>WeeWX Weather Alerter. Released under GPL-3.0. <a href="https://github.com/mlewis26201/WeeWX-MQTT-Alerter" target="_blank">GitHub</a></footer>'

SETTINGS_TEMPLATE = f'''
<!doctype html>
<html><head><title>WeeWX MQTT Alerter Settings</title>{BOOTSTRAP_HEAD}</head><body>
<div class="container mt-4">
<div class="card"><div class="card-body">
<h2 class="mb-4">WeeWX MQTT Alerter Settings</h2>
<form method="post">
  <table class="table table-borderless w-auto">
    {{% for key in required_keys %}}
    <tr>
      <td><label for="{{{{key}}}}">{{{{key}}}}</label></td>
      <td>
        {{% if key == 'MQTT_PASSWORD' %}}
          <input type="password" class="form-control" name="{{{{key}}}}" id="{{{{key}}}}" value="{{{{settings.get(key, '')}}}}">
        {{% elif key == 'MQTT_TOPIC' %}}
          <input type="text" class="form-control" name="{{{{key}}}}" id="{{{{key}}}}" value="{{{{settings.get(key, '')}}}}" placeholder="e.g. sensors/temperature">
        {{% else %}}
          <input type="text" class="form-control" name="{{{{key}}}}" id="{{{{key}}}}" value="{{{{settings.get(key, '')}}}}">
        {{% endif %}}
      </td>
    </tr>
    {{% endfor %}}
  </table>
  <button type="submit" class="btn btn-primary">Save</button>
</form>
<a href="/alerts" class="btn btn-secondary mt-3">Manage Alerts</a> | <a href="/alert_history" class="btn btn-outline-secondary mt-3">View Alert History</a>
{{% with messages = get_flashed_messages() %}}
  {{% if messages %}}
    <div class="alert alert-info mt-3">
    {{% for message in messages %}}
      <div>{{{{ message }}}}</div>
    {{% endfor %}}
    </div>
  {{% endif %}}
{{% endwith %}}
</div></div>
{FOOTER_HTML}
</div></body></html>
'''

ALERTS_TEMPLATE = f'''
<!doctype html>
<html><head><title>Alert Configurations</title>{BOOTSTRAP_HEAD}
<script>
function testAlert(alertId, btn) {{
  btn.disabled = true;
  fetch('/test_alert/' + alertId, {{method: 'POST'}})
    .then(r => r.json())
    .then(data => {{
      alert(data.message);
      btn.disabled = false;
    }})
    .catch(() => {{
      alert('Failed to send test alert');
      btn.disabled = false;
    }});
}}
</script>
</head><body>
<div class="container mt-4">
<div class="card"><div class="card-body">
<h2 class="mb-4">Alert Configurations</h2>
<a href="/" class="btn btn-secondary mb-3">Back to Settings</a> | <a href="/alert_history" class="btn btn-outline-secondary mb-3">View Alert History</a> | <a href="/download_db" class="btn btn-outline-info mb-3">Download DB</a>
<table class="table table-striped table-bordered">
<tr><th>ID</th><th>Topic</th><th>Friendly Name</th><th>IS</th><th>Value</th><th>Message</th><th>Max Alerts</th><th>Period (s)</th><th>Actions</th></tr>
{{% for alert in alerts %}}
<tr>
  <td>{{{{alert['id']}}}}</td>
  <td>{{{{alert['topic']}}}}</td>
  <td>{{{{alert['friendly_name']}}}}</td>
  <td>{{{{alert['direction']}}}}</td>
  <td>{{{{alert['threshold']}}}}</td>
  <td>{{{{alert['message']}}}}</td>
  <td>{{{{alert['max_alerts']}}}}</td>
  <td>{{{{alert['period_seconds']}}}}</td>
  <td>
    <a href="/alerts/edit/{{{{alert['id']}}}}" class="btn btn-sm btn-primary">Edit</a>
    <a href="/alerts/delete/{{{{alert['id']}}}}" class="btn btn-sm btn-danger" onclick="return confirm('Delete this alert?');">Delete</a>
    <form method="post" action="/set_friendly_name" style="display:inline-block; margin-top:5px;">
      <input type="hidden" name="topic" value="{{{{alert['topic']}}}}">
      <input type="text" name="friendly_name" value="{{{{alert['friendly_name']}}}}" placeholder="Friendly name" style="width:100px;">
      <button type="submit" class="btn btn-sm btn-outline-secondary">Set</button>
    </form>
    <button type="button" class="btn btn-sm btn-warning mt-1" onclick="testAlert({{{{alert['id']}}}}, this)">Test</button>
  </td>
</tr>
{{% endfor %}}
</table>
<h3 class="mt-4">Add New Alert</h3>
<form method="post" action="/alerts/add" class="row g-2 align-items-end">
  <div class="col-auto">
    <label>Topic:</label>
    <select name="topic" class="form-select">
      {{% for t in topics %}}
        <option value="{{{{t}}}}">{{{{t}}}}</option>
      {{% endfor %}}
    </select>
  </div>
  <div class="col-auto">
    <label>IS</label>
    <select name="direction" class="form-select">
      <option value="above">above</option>
      <option value="below">below</option>
    </select>
  </div>
  <div class="col-auto">
    <label>Value:</label>
    <input type="number" step="any" class="form-control" name="threshold" required>
  </div>
  <div class="col-auto">
    <label>Message:</label>
    <input type="text" class="form-control" name="message" required>
  </div>
  <div class="col-auto">
    <label>Max Alerts:</label>
    <input type="number" class="form-control" name="max_alerts" value="1" min="1" required>
  </div>
  <div class="col-auto">
    <label>Period (seconds):</label>
    <input type="number" class="form-control" name="period_seconds" value="3600" min="1" required>
  </div>
  <div class="col-auto">
    <button type="submit" class="btn btn-success">Add Alert</button>
  </div>
</form>
{{% with messages = get_flashed_messages() %}}
  {{% if messages %}}
    <div class="alert alert-info mt-3">
    {{% for message in messages %}}
      <div>{{{{ message }}}}</div>
    {{% endfor %}}
    </div>
  {{% endif %}}
{{% endwith %}}
</div></div>
{FOOTER_HTML}
</div></body></html>
'''

EDIT_ALERT_TEMPLATE = '''
<!doctype html>
<html><head><title>Edit Alert</title>''' + BOOTSTRAP_HEAD + '''</head><body>
<div class="container mt-4">
<div class="card"><div class="card-body">
<h2>Edit Alert</h2>
<a href="/alerts" class="btn btn-secondary mb-3">Back to Alerts</a>
<form method="post" class="row g-2 align-items-end">
  <div class="col-auto">
    <label>Topic:</label>
    <select name="topic" class="form-select">
      {% for t in topics %}
        <option value="{{t}}" {% if alert['topic'] == t %}selected{% endif %}>{{t}}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-auto">
    <label>IS</label>
    <select name="direction" class="form-select">
      <option value="above" {% if alert['direction'] == 'above' %}selected{% endif %}>above</option>
      <option value="below" {% if alert['direction'] == 'below' %}selected{% endif %}>below</option>
    </select>
  </div>
  <div class="col-auto">
    <label>Value:</label>
    <input type="number" step="any" class="form-control" name="threshold" value="{{alert['threshold']}}" required>
  </div>
  <div class="col-auto">
    <label>Message:</label>
    <input type="text" class="form-control" name="message" value="{{alert['message']}}" required>
  </div>
  <div class="col-auto">
    <label>Max Alerts:</label>
    <input type="number" class="form-control" name="max_alerts" value="{{alert['max_alerts']}}" min="1" required>
  </div>
  <div class="col-auto">
    <label>Period (seconds):</label>
    <input type="number" class="form-control" name="period_seconds" value="{{alert['period_seconds']}}" min="1" required>
  </div>
  <div class="col-auto">
    <button type="submit" class="btn btn-primary">Save</button>
  </div>
</form>
</div></div>
{FOOTER_HTML}
</div></body></html>
'''

ALERT_HISTORY_TEMPLATE = f'''
<!doctype html>
<html><head><title>Alert History</title>{BOOTSTRAP_HEAD}</head><body>
<div class="container mt-4">
<div class="card"><div class="card-body">
<h2>Alert History</h2>
<a href="/" class="btn btn-secondary mb-3">Back to Settings</a> | <a href="/alerts" class="btn btn-outline-secondary mb-3">Manage Alerts</a>
<table class="table table-striped table-bordered">
<tr><th>ID</th><th>Time</th><th>Topic</th><th>Friendly Name</th><th>Threshold</th><th>Message</th><th>Direction</th></tr>
{{% for log in history %}}
<tr>
  <td>{{{{log['id']}}}}</td>
  <td>{{{{log['timestamp'] | datetimeformat}}}}</td>
  <td>{{{{log['topic']}}}}</td>
  <td>{{{{log['friendly_name']}}}}</td>
  <td>{{{{log['threshold']}}}}</td>
  <td>{{{{log['message']}}}}</td>
  <td>{{{{log['direction']}}}}</td>
</tr>
{{% endfor %}}
</table>
</div></div>
{FOOTER_HTML}
</div></body></html>
'''

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        threshold REAL NOT NULL,
        message TEXT NOT NULL,
        max_alerts INTEGER NOT NULL DEFAULT 1,
        period_seconds INTEGER NOT NULL DEFAULT 3600,
        direction TEXT NOT NULL DEFAULT 'above'
    )''')
    # Add direction column if missing (for upgrades)
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN direction TEXT NOT NULL DEFAULT 'above'")
    except sqlite3.OperationalError:
        pass  # Already exists
    cursor.execute('''CREATE TABLE IF NOT EXISTS alert_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        timestamp INTEGER NOT NULL,
        FOREIGN KEY(alert_id) REFERENCES alerts(id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS mqtt_topics (
        topic TEXT PRIMARY KEY
    )''')
    # Add table for friendly topic names
    cursor.execute('''CREATE TABLE IF NOT EXISTS topic_friendly_names (
        topic TEXT PRIMARY KEY,
        friendly_name TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def get_settings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    settings = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return settings

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value''', (key, value))
    conn.commit()
    conn.close()
    logging.info(f"Setting updated: {key} = {value}")

def get_friendly_name(topic):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT friendly_name FROM topic_friendly_names WHERE topic=?', (topic,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return topic

def set_friendly_name(topic, friendly_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO topic_friendly_names (topic, friendly_name) VALUES (?, ?)
        ON CONFLICT(topic) DO UPDATE SET friendly_name=excluded.friendly_name''', (topic, friendly_name))
    conn.commit()
    conn.close()

def get_alerts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, topic, threshold, message, max_alerts, period_seconds, direction FROM alerts')
    alerts = [dict(id=row[0], topic=row[1], threshold=row[2], message=row[3], max_alerts=row[4], period_seconds=row[5], direction=row[6], friendly_name=get_friendly_name(row[1])) for row in cursor.fetchall()]
    conn.close()
    return alerts

def get_alert(alert_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, topic, threshold, message, max_alerts, period_seconds, direction FROM alerts WHERE id=?', (alert_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(id=row[0], topic=row[1], threshold=row[2], message=row[3], max_alerts=row[4], period_seconds=row[5], direction=row[6])
    return None

def add_alert(topic, threshold, message, max_alerts=1, period_seconds=3600, direction='above'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO alerts (topic, threshold, message, max_alerts, period_seconds, direction) VALUES (?, ?, ?, ?, ?, ?)', (topic, threshold, message, max_alerts, period_seconds, direction))
    conn.commit()
    conn.close()
    logging.info(f"Alert created: topic={topic}, direction={direction}, value={threshold}, message={message}, max_alerts={max_alerts}, period_seconds={period_seconds}")

def update_alert(alert_id, topic, threshold, message, max_alerts=1, period_seconds=3600, direction='above'):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE alerts SET topic=?, threshold=?, message=?, max_alerts=?, period_seconds=?, direction=? WHERE id=?', (topic, threshold, message, max_alerts, period_seconds, direction, alert_id))
    conn.commit()
    conn.close()

def delete_alert(alert_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT topic, threshold, direction FROM alerts WHERE id=?', (alert_id,))
    row = cursor.fetchone()
    cursor.execute('DELETE FROM alerts WHERE id=?', (alert_id,))
    conn.commit()
    conn.close()
    if row:
        logging.info(f"Alert deleted: topic={row[0]}, direction={row[2]}, value={row[1]}")
    else:
        logging.info(f"Alert deleted: id={alert_id} (not found in DB)")

def get_seen_topics():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT topic FROM mqtt_topics ORDER BY topic')
    topics = [row[0] for row in cursor.fetchall()]
    conn.close()
    return topics

def get_alert_history(limit=100):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT alert_logs.id, alert_logs.timestamp, alerts.topic, alerts.threshold, alerts.message, alerts.direction
        FROM alert_logs
        JOIN alerts ON alert_logs.alert_id = alerts.id
        ORDER BY alert_logs.timestamp DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        dict(id=row[0], timestamp=row[1], topic=row[2], threshold=row[3], message=row[4], direction=row[5], friendly_name=get_friendly_name(row[2]))
        for row in rows
    ]

@app.template_filter('datetimeformat')
def datetimeformat_filter(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        for key in REQUIRED_KEYS:
            value = request.form.get(key, '')
            set_setting(key, value)
        logging.info("Settings updated via web form.")
        flash('Settings updated!')
        return redirect(url_for('index'))
    settings = get_settings()
    return render_template_string(SETTINGS_TEMPLATE, settings=settings, required_keys=REQUIRED_KEYS)

@app.route('/alerts')
def alerts():
    alerts = get_alerts()
    topics = get_seen_topics()
    return render_template_string(ALERTS_TEMPLATE, alerts=alerts, topics=topics)

@app.route('/alerts/add', methods=['POST'])
def add_alert_route():
    topic = request.form['topic']
    threshold = request.form['threshold']
    message = request.form['message']
    max_alerts = request.form['max_alerts']
    period_seconds = request.form['period_seconds']
    direction = request.form.get('direction', 'above')
    add_alert(topic, threshold, message, max_alerts, period_seconds, direction)
    flash('Alert added!')
    return redirect(url_for('alerts'))

@app.route('/alerts/edit/<int:alert_id>', methods=['GET', 'POST'])
def edit_alert(alert_id):
    alert = get_alert(alert_id)
    topics = get_seen_topics()
    if not alert:
        flash('Alert not found!')
        return redirect(url_for('alerts'))
    if request.method == 'POST':
        topic = request.form['topic']
        threshold = request.form['threshold']
        message = request.form['message']
        max_alerts = request.form['max_alerts']
        period_seconds = request.form['period_seconds']
        direction = request.form.get('direction', 'above')
        update_alert(alert_id, topic, threshold, message, max_alerts, period_seconds, direction)
        flash('Alert updated!')
        return redirect(url_for('alerts'))
    return render_template_string(EDIT_ALERT_TEMPLATE, alert=alert, topics=topics)

@app.route('/alerts/delete/<int:alert_id>')
def delete_alert_route(alert_id):
    delete_alert(alert_id)
    flash('Alert deleted!')
    return redirect(url_for('alerts'))

@app.route('/alert_history')
def alert_history():
    history = get_alert_history()
    return render_template_string(ALERT_HISTORY_TEMPLATE, history=history)

@app.route('/download_db')
def download_db():
    return send_file(DB_PATH, as_attachment=True, download_name='settings.db')

@app.route('/set_friendly_name', methods=['POST'])
def set_friendly_name_route():
    topic = request.form['topic']
    friendly_name = request.form['friendly_name']
    set_friendly_name(topic, friendly_name)
    flash(f'Friendly name for "{topic}" set to "{friendly_name}"')
    return redirect(url_for('alerts'))

@app.route('/test_alert/<int:alert_id>', methods=['POST'])
def test_alert(alert_id):
    alert = get_alert(alert_id)
    if not alert:
        return jsonify({'success': False, 'message': 'Alert not found'}), 404
    import os
    from mqtt_pushover_alert import send_pushover_notification, get_friendly_name
    settings = get_settings()
    os.environ['PUSHOVER_USER_KEY'] = settings.get('PUSHOVER_USER_KEY', '')
    os.environ['PUSHOVER_API_TOKEN'] = settings.get('PUSHOVER_API_TOKEN', '')
    friendly_name = get_friendly_name(alert['topic']) if 'friendly_name' in alert else alert['topic']
    test_value = alert['threshold']
    message = alert['message'].replace('{value}', str(test_value)).replace('{threshold}', str(alert['threshold']))
    prefix = f"[{friendly_name}] " if friendly_name and friendly_name != alert['topic'] else f"[{alert['topic']}] "
    message = f"[TEST] {prefix}{message}"
    try:
        send_pushover_notification(message)
        return jsonify({'success': True, 'message': 'Test alert sent!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send test alert: {e}'})
