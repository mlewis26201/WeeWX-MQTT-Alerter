# WeeWX MQTT Alerter

A Dockerized system for monitoring MQTT topics and sending Pushover notifications when configurable thresholds are exceeded. Includes a Flask web frontend for managing settings and alerts, with alert history and logging.

## Features
- Subscribes to MQTT topics and triggers alerts when values are above or below thresholds
- Sends notifications via Pushover
- Supports multiple, configurable alerts with rate limiting
- Web UI (Flask/Gunicorn) for managing settings and alerts
- View alert history and logs in the web UI
- MQTT authentication (username/password)
- Dockerized: easy to deploy and run
- Database stored in a bind mount for easy backup and inspection

## Quick Start

### 1. Clone the repository
```
git clone <your-repo-url>
cd WeeWX-MQTT-Alerter
```

### 2. Configure Environment Variables
Edit `docker-compose.yaml` and set the following for both `mqtt_alerter` and `web_frontend`:
- `MQTT_BROKER` (e.g. your MQTT server IP)
- `MQTT_PORT` (default: 1883)
- `MQTT_USERNAME` / `MQTT_PASSWORD` (if needed)
- `MQTT_TOPIC` (e.g. `weather`)
- `PUSHOVER_USER_KEY` / `PUSHOVER_API_TOKEN` (from your Pushover account)

### 3. Create a blank database file
```
powershell New-Item -ItemType File -Path settings.db
```
Or on Linux:
```
touch settings.db
```

### 4. Start the containers
```
docker-compose up --build
```

- The web UI will be available at [http://localhost:8999](http://localhost:8999)
- The MQTT alerter will run in the background and process MQTT messages

## Web UI
- Manage MQTT and Pushover settings
- Add/edit/delete alerts (choose topic, direction, value, message, rate limits)
- View alert history and logs

## Database
- The SQLite database (`settings.db`) is bind-mounted for persistence and easy backup.
- If the database is missing or empty, it will be initialized from environment variables.

## Customization
- Edit `docker-compose.yaml` to change ports, environment variables, or database location.
- Edit `settings_web.py` or `mqtt_pushover_alert.py` for advanced customization.

## Troubleshooting
- Check container logs for errors: `docker-compose logs mqtt_alerter` or `docker-compose logs web_frontend`
- Ensure MQTT and Pushover credentials are correct
- Ensure MQTT messages are being published to the correct topic

## License
GNU GPL v3
