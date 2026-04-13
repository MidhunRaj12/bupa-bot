# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Install Python dependencies first (Docker layer caching)
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY app/ ./app/

# Create log directories
RUN mkdir -p /app/logs/screenshots

# Run the bot
CMD ["python", "-m", "app.main"]