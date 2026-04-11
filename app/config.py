# app/config.py
from dotenv import load_dotenv
import os

load_dotenv()

# --- Person details ---
HAP_ID          = os.getenv("HAP_ID", "")
EMAIL           = os.getenv("EMAIL", "")
GIVEN_NAMES     = os.getenv("GIVEN_NAMES", "")
FAMILY_NAME     = os.getenv("FAMILY_NAME", "")
DOB             = os.getenv("DOB", "")            # format: DD/MM/YYYY
PREFERRED_LOCATION = os.getenv("PREFERRED_LOCATION", "")

# --- Scheduler ---
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "10"))
CHECK_INTERVAL_MAX = int(os.getenv("CHECK_INTERVAL_MAX", "30"))

# --- Notifications ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Runtime ---
CONTAINER_NAME  = os.getenv("CONTAINER_NAME", "container_1")
HEADLESS        = os.getenv("HEADLESS", "true").lower() == "true"
SCREENSHOT_DIR  = "/app/logs/screenshots"

def validate_config():
    """Call on startup — crash early if critical vars are missing."""
    required = {
        "HAP_ID": HAP_ID,
        "EMAIL": EMAIL,
        "GIVEN_NAMES": GIVEN_NAMES,
        "FAMILY_NAME": FAMILY_NAME,
        "DOB": DOB,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )