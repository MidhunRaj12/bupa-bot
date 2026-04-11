# app/notify.py
import asyncio
from loguru import logger
from app import config

async def _send_telegram(message: str):
    """Send message via Telegram bot."""
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML"
        )
        logger.info("Telegram notification sent.")
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")

def notify(message: str):
    """
    Main notification function — call this from anywhere.
    Falls back to console log if Telegram is not configured.
    """
    logger.info(f"NOTIFY: {message}")

    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        asyncio.run(_send_telegram(message))
    else:
        logger.warning("Telegram not configured — logged to console only.")

def notify_slot_found(location: str, date: str, time: str):
    """Pre-formatted message when a slot is found."""
    message = (
        f"✅ <b>Appointment slot found!</b>\n\n"
        f"👤 <b>Person:</b> {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
        f"📍 <b>Location:</b> {location}\n"
        f"📅 <b>Date:</b> {date}\n"
        f"🕐 <b>Time:</b> {time}\n\n"
        f"🤖 Container: {config.CONTAINER_NAME}"
    )
    notify(message)

def notify_error(error: str):
    """Pre-formatted message when something goes wrong."""
    message = (
        f"❌ <b>Bot error</b>\n\n"
        f"🤖 Container: {config.CONTAINER_NAME}\n"
        f"⚠️ {error}"
    )
    notify(message)
# app/notify.py
# STUB — full implementation in feature/telegram-notify branch
# All functions are no-ops until that branch is merged into main.
# No other files need to change when notify is enabled.

from loguru import logger
from app import config

async def _send_telegram(message: str):
    """Send message via Telegram bot."""
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML"
        )
        logger.info("Telegram notification sent.")
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")

def notify(message: str):
    """
    Main notification function — call this from anywhere.
    Falls back to console log if Telegram is not configured.
    """
    logger.info(f"NOTIFY: {message}")

    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        asyncio.run(_send_telegram(message))
    else:
        logger.warning("Telegram not configured — logged to console only.")

def notify_slot_found(location: str, date: str, time: str):
    """Pre-formatted message when a slot is found."""
    message = (
        f"✅ <b>Appointment slot found!</b>\n\n"
        f"👤 <b>Person:</b> {config.GIVEN_NAMES} {config.FAMILY_NAME}\n"
        f"📍 <b>Location:</b> {location}\n"
        f"📅 <b>Date:</b> {date}\n"
        f"🕐 <b>Time:</b> {time}\n\n"
        f"🤖 Container: {config.CONTAINER_NAME}"
    )
    notify(message)

def notify_error(error: str):
    """Pre-formatted message when something goes wrong."""
    message = (
        f"❌ <b>Bot error</b>\n\n"
        f"🤖 Container: {config.CONTAINER_NAME}\n"
        f"⚠️ {error}"
    )
    notify(message)