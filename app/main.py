# app/main.py
#
# Entry point — validates config, runs an immediate check on startup,
# then schedules recurring checks at a randomised interval.
# Retries failed jobs with exponential backoff before giving up.

import random
import traceback
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError
)
from app.bot import check_appointments, setup_logger
from app import config, notify


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------
# Retries up to 3 times on any exception.
# Waits: 30s -> 60s -> 120s between attempts.
# Logs a warning before each retry so you can see it in the log.

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=30, min=30, max=120),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=False           # we handle the final failure ourselves below
)
def _check_with_retry():
    """Runs check_appointments with retry policy applied."""
    check_appointments()


# ---------------------------------------------------------------------------
# Scheduler job
# ---------------------------------------------------------------------------

def run_job():
    """
    Scheduler callback.
    Wraps _check_with_retry with top-level error handling so the
    scheduler never crashes on a persistent failure.
    """
    logger.info("-" * 60)
    logger.info(f"Job triggered — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        _check_with_retry()

    except RetryError as e:
        # All retry attempts exhausted
        reason = f"All retry attempts failed: {e.last_attempt.exception()}"
        logger.error(reason)
        logger.error(traceback.format_exc())
        notify.notify_error(reason)

    except Exception as e:
        # Unexpected error outside retry scope
        reason = f"Unhandled error in job: {type(e).__name__}: {e}"
        logger.error(reason)
        logger.error(traceback.format_exc())
        notify.notify_error(reason)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    setup_logger()
    logger.info(f"Bot starting — container: {config.CONTAINER_NAME}")

    # Validate all required env vars before doing anything
    try:
        config.validate_config()
        logger.info("Config validated.")
    except EnvironmentError as e:
        logger.error(f"Config validation failed: {e}")
        notify.notify_error(f"Config validation failed — bot did not start: {e}")
        raise

    # Randomise interval so multiple containers don't hit the site together
    interval = random.randint(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX)
    logger.info(
        f"Schedule: every {interval} minutes "
        f"(range {config.CHECK_INTERVAL_MIN}–{config.CHECK_INTERVAL_MAX})"
    )

    notify.notify_startup()

    # Run once immediately on startup before handing off to scheduler
    logger.info("Running initial check on startup...")
    run_job()

    # Set up recurring schedule
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_job,
        trigger=IntervalTrigger(minutes=interval),
        id="appointment_check",
        name="BUPA appointment check",
        max_instances=1,        # never overlap two runs
        coalesce=True,          # skip missed runs if bot was paused
    )

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
        notify.notify_shutdown()


if __name__ == "__main__":
    main()