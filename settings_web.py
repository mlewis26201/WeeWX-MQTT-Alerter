from flask import Flask, render_template_string, request, redirect, url_for, flash
import sqlite3

DB_PATH = 'settings.db'
REQUIRED_KEYS = [
    'MQTT_BROKER', 'MQTT_PORT', 'MQTT_USERNAME', 'MQTT_PASSWORD',
    'PUSHOVER_USER_KEY', 'PUSHOVER_API_TOKEN'
]

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this for production

SETTINGS_TEMPLATE = '''
<!doctype html>
<title>WeeWX MQTT Alerter Settings</title>
<h2>WeeWX MQTT Alerter Settings</h2>
<form method="post">
  <table>
    {% for key in required_keys %}
    <tr>
      <td><label for="{{key}}">{{key}}</label></td>
      <td><input type="text" name="{{key}}" id="{{key}}" value="{{settings.get(key, '')}}"></td>
    </tr>
    {% endfor %}
  </table>
  <input type="submit" value="Save">
</form>
<a href="/alerts">Manage Alerts</a>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for message in messages %}
      <li>{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<footer style="margin-top:2em;text-align:center;color:#888;">Built with Coco!</footer>
'''

ALERTS_TEMPLATE = '''
<!doctype html>
<title>Alert Configurations</title>
<h2>Alert Configurations</h2>
<a href="/">Back to Settings</a>
<table border=1>
<tr><th>ID</th><th>Topic</th><th>Threshold</th><th>Message</th><th>Max Alerts</th><th>Period (s)</th><th>Actions</th></tr>
{% for alert in alerts %}
<tr>
  <td>{{alert['id']}}</td>
  <td>{{alert['topic']}}</td>
  <td>{{alert['threshold']}}</td>
  <td>{{alert['message']}}</td>
  <td>{{alert['max_alerts']}}</td>
  <td>{{alert['period_seconds']}}</td>
  <td>
    <a href="/alerts/edit/{{alert['id']}}">Edit</a>
    <a href="/alerts/delete/{{alert['id']}}" onclick="return confirm('Delete this alert?');">Delete</a>
  </td>
</tr>
{% endfor %}
</table>
<h3>Add New Alert</h3>
<form method="post" action="/alerts/add">
  Topic: <input type="text" name="topic" required> &nbsp;
  Threshold: <input type="number" step="any" name="threshold" required> &nbsp;
  Message: <input type="text" name="message" required> &nbsp;
  Max Alerts: <input type="number" name="max_alerts" value="1" min="1" required> &nbsp;
  Period (seconds): <input type="number" name="period_seconds" value="3600" min="1" required> &nbsp;
  <input type="submit" value="Add Alert">
</form>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>
    {% for message in messages %}
      <li>{{ message }}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<footer style="margin-top:2em;text-align:center;color:#888;">Built with Coco!</footer>
'''

EDIT_ALERT_TEMPLATE = '''
<!doctype html>
<title>Edit Alert</title>
<h2>Edit Alert</h2>
<a href="/alerts">Back to Alerts</a>
<form method="post">
  Topic: <input type="text" name="topic" value="{{alert['topic']}}" required><br>
  Threshold: <input type="number" step="any" name="threshold" value="{{alert['threshold']}}" required><br>
  Message: <input type="text" name="message" value="{{alert['message']}}" required><br>
  Max Alerts: <input type="number" name="max_alerts" value="{{alert['max_alerts']}}" min="1" required><br>
  Period (seconds): <input type="number" name="period_seconds" value="{{alert['period_seconds']}}" min="1" required><br>
  <input type="submit" value="Save">
</form>
<footer style="margin-top:2em;text-align:center;color:#888;">Built with Coco!</footer>
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
        period_seconds INTEGER NOT NULL DEFAULT 3600
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS alert_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        timestamp INTEGER NOT NULL,
        FOREIGN KEY(alert_id) REFERENCES alerts(id)
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

def get_alerts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, topic, threshold, message, max_alerts, period_seconds FROM alerts')
    alerts = [dict(id=row[0], topic=row[1], threshold=row[2], message=row[3], max_alerts=row[4], period_seconds=row[5]) for row in cursor.fetchall()]
    conn.close()
    return alerts

def get_alert(alert_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, topic, threshold, message, max_alerts, period_seconds FROM alerts WHERE id=?', (alert_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(id=row[0], topic=row[1], threshold=row[2], message=row[3], max_alerts=row[4], period_seconds=row[5])
    return None

def add_alert(topic, threshold, message, max_alerts=1, period_seconds=3600):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO alerts (topic, threshold, message, max_alerts, period_seconds) VALUES (?, ?, ?, ?, ?)', (topic, threshold, message, max_alerts, period_seconds))
    conn.commit()
    conn.close()

def update_alert(alert_id, topic, threshold, message, max_alerts=1, period_seconds=3600):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE alerts SET topic=?, threshold=?, message=?, max_alerts=?, period_seconds=? WHERE id=?', (topic, threshold, message, max_alerts, period_seconds, alert_id))
    conn.commit()
    conn.close()

def delete_alert(alert_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM alerts WHERE id=?', (alert_id,))
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        for key in REQUIRED_KEYS:
            value = request.form.get(key, '')
            set_setting(key, value)
        flash('Settings updated!')
        return redirect(url_for('index'))
    settings = get_settings()
    return render_template_string(SETTINGS_TEMPLATE, settings=settings, required_keys=REQUIRED_KEYS)

@app.route('/alerts')
def alerts():
    alerts = get_alerts()
    return render_template_string(ALERTS_TEMPLATE, alerts=alerts)

@app.route('/alerts/add', methods=['POST'])
def add_alert_route():
    topic = request.form['topic']
    threshold = request.form['threshold']
    message = request.form['message']
    max_alerts = request.form['max_alerts']
    period_seconds = request.form['period_seconds']
    add_alert(topic, threshold, message, max_alerts, period_seconds)
    flash('Alert added!')
    return redirect(url_for('alerts'))

@app.route('/alerts/edit/<int:alert_id>', methods=['GET', 'POST'])
def edit_alert(alert_id):
    alert = get_alert(alert_id)
    if not alert:
        flash('Alert not found!')
        return redirect(url_for('alerts'))
    if request.method == 'POST':
        topic = request.form['topic']
        threshold = request.form['threshold']
        message = request.form['message']
        max_alerts = request.form['max_alerts']
        period_seconds = request.form['period_seconds']
        update_alert(alert_id, topic, threshold, message, max_alerts, period_seconds)
        flash('Alert updated!')
        return redirect(url_for('alerts'))
    return render_template_string(EDIT_ALERT_TEMPLATE, alert=alert)

@app.route('/alerts/delete/<int:alert_id>')
def delete_alert_route(alert_id):
    delete_alert(alert_id)
    flash('Alert deleted!')
    return redirect(url_for('alerts'))

if __name__ == '__main__':
    app.run(debug=True)
