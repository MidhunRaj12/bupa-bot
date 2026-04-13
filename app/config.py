# app/config.py
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

# --- Person details ---
HAP_ID             = os.getenv("HAP_ID", "")
EMAIL              = os.getenv("EMAIL", "")
GIVEN_NAMES        = os.getenv("GIVEN_NAMES", "")
FAMILY_NAME        = os.getenv("FAMILY_NAME", "")
DOB                = os.getenv("DOB", "")
PREFERRED_LOCATION = os.getenv("PREFERRED_LOCATION", "")

# --- Scheduler ---
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "10"))
CHECK_INTERVAL_MAX = int(os.getenv("CHECK_INTERVAL_MAX", "30"))

# --- Notifications ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Runtime ---
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "local_test")
HEADLESS       = os.getenv("HEADLESS", "true").lower() == "true"

# --- Paths ---
# Locally:  BASE_DIR = project root (where you run python -m app.main)
# Docker:   BASE_DIR = /app  (set via docker-compose environment)
BASE_DIR       = Path(os.getenv("BASE_DIR", "."))
LOG_DIR        = str(BASE_DIR / "logs")
SCREENSHOT_DIR = str(BASE_DIR / "logs" / "screenshots")

# --- URLs ---
BUPA_URL = os.getenv(
    "BUPA_URL",
    "https://bmvs.onlineappointmentscheduling.net.au/oasis/Search.aspx"
)

def validate_config():
    required = {
        "HAP_ID":       HAP_ID,
        "EMAIL":        EMAIL,
        "GIVEN_NAMES":  GIVEN_NAMES,
        "FAMILY_NAME":  FAMILY_NAME,
        "DOB":          DOB,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )