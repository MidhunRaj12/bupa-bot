# app/main.py
import random
import time
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.bot import check_appointments, setup_logger
from app.notify import notify
from app import config

def run_job():
    """Wrapper so scheduler catches and logs exceptions cleanly."""
    try:
        logger.info("=" * 50)
        logger.info("Job triggered by scheduler")
        check_appointments()
    except Exception as e:
        logger.error(f"Job failed after all retries: {e}")

def main():
    setup_logger()
    logger.info(f"🤖 Bot starting — container: {config.CONTAINER_NAME}")

    # Validate env vars before doing anything
    try:
        config.validate_config()
        logger.info("✅ Config validated.")
    except EnvironmentError as e:
        logger.error(f"Config error: {e}")
        raise

    # Random interval between min and max
    interval_minutes = random.randint(
        config.CHECK_INTERVAL_MIN,
        config.CHECK_INTERVAL_MAX
    )
    logger.info(
        f"Scheduler set to every {interval_minutes} minutes "
        f"(range: {config.CHECK_INTERVAL_MIN}–{config.CHECK_INTERVAL_MAX})"
    )

    # Run once immediately on startup
    logger.info("Running first check immediately on startup...")
    run_job()

    # Then schedule recurring checks
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="appointment_check",
        name="BUPA appointment check",
        max_instances=1,        # never run two at once
        coalesce=True,          # skip missed runs
    )

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

if __name__ == "__main__":
    main()