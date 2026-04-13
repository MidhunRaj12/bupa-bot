# app/notify.py
#
# Notification service — sends Telegram messages via direct HTTP requests.
# Synchronous implementation avoids asyncio conflicts with APScheduler.
# Falls back to console log if Telegram is not configured.

import requests
from pathlib import Path
from loguru import logger
from app import config


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _telegram_url(method: str) -> str:
    """Build Telegram Bot API URL for a given method."""
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"


def _send_message(text: str):
    """Send a plain text message via Telegram Bot API."""
    response = requests.post(
        _telegram_url("sendMessage"),
        data={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text":    text,
            "parse_mode": "HTML"
        },
        timeout=15
    )
    response.raise_for_status()


def _send_photo(photo_path: str, caption: str):
    """
    Send a photo with caption via Telegram Bot API.
    Falls back to text message if the photo file does not exist.
    """
    path = Path(photo_path)
    if not path.exists():
        logger.warning(f"Screenshot not found, sending text only: {photo_path}")
        _send_message(caption)
        return

    with open(path, "rb") as f:
        response = requests.post(
            _telegram_url("sendPhoto"),
            data={
                "chat_id":    config.TELEGRAM_CHAT_ID,
                "caption":    caption,
                "parse_mode": "HTML"
            },
            files={"photo": f},
            timeout=30
        )
    response.raise_for_status()


def _dispatch(fn, *args, **kwargs):
    """
    Call a notify function safely.
    Logs warning on failure — never raises so the bot keeps running.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.info("[NOTIFY] Telegram not configured — console only.")
        return
    try:
        fn(*args, **kwargs)
    except requests.exceptions.RequestException as e:
        logger.warning(f"Telegram request failed: {e}")
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def notify_startup():
    """Called once when the bot starts."""
    message = (
        f"<b>Bot started</b>\n\n"
        f"Person    : {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
        f"Container : {config.CONTAINER_NAME}\n"
        f"Schedule  : every {config.CHECK_INTERVAL_MIN}–"
        f"{config.CHECK_INTERVAL_MAX} min\n"
        f"Current appointment : {config.CURRENT_APPT_DATE}"
    )
    logger.info("[NOTIFY] Bot started.")
    _dispatch(_send_message, message)


def notify_shutdown():
    """Called when the bot stops."""
    message = (
        f"<b>Bot stopped</b>\n\n"
        f"Person    : {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
        f"Container : {config.CONTAINER_NAME}"
    )
    logger.info("[NOTIFY] Bot stopped.")
    _dispatch(_send_message, message)


def notify_result(success: bool, detail: str, screenshot: str = None):
    """
    Single unified result notification — called after every check.
    Always attaches the available_slots screenshot so you can see
    what dates/times were on the page during that run.
    On success, also sends the confirmation screenshot as a second message.
    """
    status  = "Appointment updated" if success else "No update"
    marker  = "[+]" if success else "[-]"
    message = (
        f"<b>Check result</b> {marker}\n\n"
        f"Person    : {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
        f"Container : {config.CONTAINER_NAME}\n"
        f"Status    : {status}\n"
        f"Detail    : {detail}"
    )
    logger.info(f"[NOTIFY] {status} — {detail}")

    # Always send available_slots screenshot — shows what was on page this run
    base_photo = (
        f"{config.SCREENSHOT_DIR}/"
        f"{config.CONTAINER_NAME}_available_slots.png"
    )
    _dispatch(_send_photo, base_photo, message)

    # On success also send the confirmation page as a second message
    if success and screenshot and screenshot != "available_slots":
        confirm_photo = (
            f"{config.SCREENSHOT_DIR}/"
            f"{config.CONTAINER_NAME}_{screenshot}.png"
        )
        confirm_message = (
            f"<b>Booking confirmation</b>\n\n"
            f"Person    : {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
            f"Container : {config.CONTAINER_NAME}\n"
            f"Detail    : {detail}"
        )
        _dispatch(_send_photo, confirm_photo, confirm_message)


def notify_error(detail: str):
    """Called on any unexpected failure — attaches error screenshot if available."""
    message = (
        f"<b>Bot error</b> [!]\n\n"
        f"Person    : {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
        f"Container : {config.CONTAINER_NAME}\n"
        f"Detail    : {detail}"
    )
    logger.error(f"[NOTIFY] Error — {detail}")
    error_photo = (
        f"{config.SCREENSHOT_DIR}/"
        f"{config.CONTAINER_NAME}_error.png"
    )
    _dispatch(_send_photo, error_photo, message)