# Multi-stage build to slim the image
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy as builder

WORKDIR /app

COPY app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Install Chromium browser binaries
RUN playwright install chromium

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app/ ./app/

# Pre-create log directories
RUN mkdir -p /app/logs/screenshots

EXPOSE 8000

# Run the bot
CMD ["python", "-m", "app.main"]