# app/main.py
#
# Entry point — validates config, runs an immediate check on startup,
# then schedules recurring checks at a randomised interval.

import random
import traceback
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.bot import check_appointments, setup_logger
from app import config, notify


def run_job():
    """Scheduler callback — wraps check_appointments with top-level error handling."""
    logger.info("-" * 60)
    logger.info("Job triggered.")
    try:
        check_appointments()
    except Exception as e:
        logger.error(f"Job failed: {e}")
        logger.error(traceback.format_exc())


def main():
    setup_logger()
    logger.info(f"Bot starting — container: {config.CONTAINER_NAME}")

    try:
        config.validate_config()
    except EnvironmentError as e:
        logger.error(f"Config validation failed: {e}")
        raise

    interval = random.randint(config.CHECK_INTERVAL_MIN, config.CHECK_INTERVAL_MAX)
    logger.info(
        f"Schedule: every {interval} minutes "
        f"(range {config.CHECK_INTERVAL_MIN}–{config.CHECK_INTERVAL_MAX})"
    )

    # Run once immediately on startup before handing off to scheduler
    run_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_job,
        trigger=IntervalTrigger(minutes=interval),
        id="appointment_check",
        max_instances=1,
        coalesce=True,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")


if __name__ == "__main__":
    main()