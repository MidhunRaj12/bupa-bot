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
CURRENT_APPT_DATE = os.getenv("CURRENT_APPT_DATE", "")  # format: DD/MM/YYYY

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

def save_confirmed_appointment(date: str, time: str, location: str):
    """Write confirmed appointment details to a file for reference."""
    from pathlib import Path
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    record = (
        f"Confirmed appointment\n"
        f"Container : {CONTAINER_NAME}\n"
        f"Name      : {GIVEN_NAMES} {FAMILY_NAME}\n"
        f"Date      : {date}\n"
        f"Time      : {time}\n"
        f"Location  : {location}\n"
        f"Saved at  : {__import__('datetime').datetime.now()}\n"
    )
    path = log_dir / f"{CONTAINER_NAME}_confirmed.txt"
    path.write_text(record)