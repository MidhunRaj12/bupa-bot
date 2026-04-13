# app/notify.py
# STUB — full implementation in feature/telegram-notify branch
# All functions are no-ops until that branch is merged into main.
# No other files need to change when notify is enabled.

from loguru import logger

def notify(message: str):
    # TODO: wire up Telegram in feature/telegram-notify
    logger.info(f"[NOTIFY STUB] {message}")

def notify_slot_found(location: str, date: str, time: str):
    # TODO: wire up Telegram in feature/telegram-notify
    logger.info(f"[NOTIFY STUB] Slot found — {location} {date} {time}")

def notify_error(error: str):
    # TODO: wire up Telegram in feature/telegram-notify
    logger.info(f"[NOTIFY STUB] Error — {error}")