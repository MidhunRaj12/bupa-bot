# Dockerfile
#
# Uses the official Playwright Python image which bundles Chromium
# and all system dependencies — no manual apt installs needed.

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory — all paths inside container are relative to this
WORKDIR /app

# Install Python dependencies first so Docker can cache this layer.
# Only re-runs when requirements.txt changes.
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser binaries
RUN playwright install chromium

# Copy application code
COPY app/ ./app/

# Pre-create log directories so the container has them on first run
RUN mkdir -p /app/logs/screenshots

# Run the bot as a module so imports resolve correctly
CMD ["python", "-m", "app.main"]