FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mqtt_pushover_alert.py settings_web.py ./

EXPOSE 8000

# By default, do nothing. Specify the entrypoint when running the container.
CMD ["python", "--version"]