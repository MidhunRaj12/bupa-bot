# app/config.py
#
# Centralised configuration — loads all environment variables in one place.
# Every other module imports from here, never reads .env directly.
# On successful booking, saves record and updates CURRENT_APPT_DATE in .env.

import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Person details
# ---------------------------------------------------------------------------
HAP_ID             = os.getenv("HAP_ID", "")
EMAIL              = os.getenv("EMAIL", "")
GIVEN_NAMES        = os.getenv("GIVEN_NAMES", "")
FAMILY_NAME        = os.getenv("FAMILY_NAME", "")
DOB                = os.getenv("DOB", "")               # format: DD/MM/YYYY
PREFERRED_LOCATION = os.getenv("PREFERRED_LOCATION", "")
CURRENT_APPT_DATE  = os.getenv("CURRENT_APPT_DATE", "") # format: DD/MM/YYYY

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "10"))
CHECK_INTERVAL_MAX = int(os.getenv("CHECK_INTERVAL_MAX", "30"))

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "local_test")
HEADLESS       = os.getenv("HEADLESS", "true").lower() == "true"
BUPA_URL       = os.getenv(
    "BUPA_URL",
    "https://bmvs.onlineappointmentscheduling.net.au/oasis/Search.aspx"
)

# ---------------------------------------------------------------------------
# Paths
# Locally:  BASE_DIR defaults to "." (project root)
# Docker:   BASE_DIR set to /app via docker-compose environment
# ---------------------------------------------------------------------------
BASE_DIR       = Path(os.getenv("BASE_DIR", "."))
LOG_DIR        = str(BASE_DIR / "logs")
SCREENSHOT_DIR = str(BASE_DIR / "logs" / "screenshots")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_config():
    """
    Called on startup — raises EnvironmentError if any
    required variable is missing so the bot fails fast.
    """
    required = {
        "HAP_ID":            HAP_ID,
        "EMAIL":             EMAIL,
        "GIVEN_NAMES":       GIVEN_NAMES,
        "FAMILY_NAME":       FAMILY_NAME,
        "DOB":               DOB,
        "CURRENT_APPT_DATE": CURRENT_APPT_DATE,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


# ---------------------------------------------------------------------------
# Confirmed appointment persistence
# ---------------------------------------------------------------------------

def save_confirmed_appointment(date: str, time: str, location: str):
    """
    Persist confirmed appointment details to a record file.
    Parses the confirmed date string from the BUPA confirmation page
    (e.g. "Monday, 20 April 2026 @ 01:00 PM") and:
      - Writes a human-readable record to logs/
      - Updates CURRENT_APPT_DATE in .env
      - Reloads CURRENT_APPT_DATE into the running process immediately
        so the next scheduled check uses the new date without a restart
    """
    from datetime import datetime
    from loguru import logger

    global CURRENT_APPT_DATE

    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # --- Write human-readable record ---
    record = (
        f"Confirmed appointment\n"
        f"Container : {CONTAINER_NAME}\n"
        f"Name      : {GIVEN_NAMES} {FAMILY_NAME}\n"
        f"Date      : {date}\n"
        f"Time      : {time}\n"
        f"Location  : {location}\n"
        f"Saved at  : {datetime.now()}\n"
    )
    record_path = log_dir / f"{CONTAINER_NAME}_confirmed.txt"
    record_path.write_text(record)
    logger.info(f"Confirmed appointment record saved: {record_path}")

    # --- Parse DD/MM/YYYY from confirmation string ---
    # BUPA returns e.g. "Monday, 20 April 2026 @ 01:00 PM"
    # Strip weekday prefix and time suffix to get "20 April 2026"
    try:
        date_part = re.sub(r"^[^,]+,\s*", "", date)        # remove "Monday, "
        date_part = re.sub(r"\s*@.*$", "", date_part).strip()  # remove "@ 01:00 PM"
        parsed    = datetime.strptime(date_part, "%d %B %Y")
        new_date  = parsed.strftime("%d/%m/%Y")
    except Exception as e:
        logging.warning(f"Could not parse confirmed date for .env update: {e}")
        return

    # --- Update CURRENT_APPT_DATE in .env ---
    # Use the mounted envs directory
    env_file_name = CONTAINER_NAME.replace("bot_", "") + ".env"
    env_path = Path("/app/envs") / env_file_name

    if env_path.exists():
        content = env_path.read_text()
        updated = re.sub(
            r"^CURRENT_APPT_DATE=.*$",
            f"CURRENT_APPT_DATE={new_date}",
            content,
            flags=re.MULTILINE
        )
        env_path.write_text(updated)
        logger.info(f".env updated — CURRENT_APPT_DATE={new_date}")
    else:
        logger.warning(
            f".env file not found at {env_path} — CURRENT_APPT_DATE not persisted. "
            "Update it manually before next run."
        )

    # --- Reload into running process immediately ---
    # Ensures the next scheduled check in this session uses the new date
    # without requiring a bot restart.
    CURRENT_APPT_DATE = new_date
    logger.info(
        f"CURRENT_APPT_DATE reloaded in config — "
        f"next check will compare against {new_date}"
    )


