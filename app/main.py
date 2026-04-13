# app/main.py
#
# Entry point — validates config, runs an immediate check on startup,
# then schedules recurring checks at a randomised interval.
#
# ============================================================
# TIMING CONFIGURATION — adjust these to avoid site flagging:
#
# In .env:
#   CHECK_INTERVAL_MIN / CHECK_INTERVAL_MAX
#   — the scheduler picks a random value in this range after each run
#   — recommended: 15-45 minutes for production
#
# In _check_with_retry below:
#   stop_after_attempt(3)         — number of retry attempts per run
#   wait_exponential(min=60, max=300)
#   — waits 60s -> 120s -> 300s between retries
#   — increase min/max if you want longer gaps between retries
# ============================================================

import random
import traceback
import signal
import threading
import http.server
import socketserver
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


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/health'):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()


def run_health_server():
    with socketserver.TCPServer(("", 8000), HealthHandler) as httpd:
        httpd.serve_forever()


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------
# Adjust stop_after_attempt and wait_exponential below to control
# how aggressively the bot retries on failure.
#
# Current settings:
#   - 3 attempts per scheduled run
#   - Wait 60s -> 120s -> 300s between attempts
#   - Randomised jitter via random_interval() in scheduler below

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=60, max=300),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=False
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
        reason = f"All retry attempts exhausted: {e.last_attempt.exception()}"
        logger.error(reason)
        logger.error(traceback.format_exc())
        notify.notify_error(reason)

    except Exception as e:
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

    try:
        config.validate_config()
        logger.info("Config validated.")
    except EnvironmentError as e:
        logger.error(f"Config validation failed: {e}")
        notify.notify_error(f"Config validation failed — bot did not start: {e}")
        raise

    notify.notify_startup()

    # Start health check server
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("Health check server started on port 8000")

    # Run once immediately on startup
    logger.info("Running initial check on startup...")
    run_job()

    # ---------------------------------------------------------------------------
    # Scheduler — randomised interval
    # Each completed run reschedules itself with a NEW random interval.
    # This makes the check pattern unpredictable to the site.
    #
    # Adjust CHECK_INTERVAL_MIN / CHECK_INTERVAL_MAX in .env
    # Recommended production values: MIN=15, MAX=45
    # ---------------------------------------------------------------------------
    def scheduled_job():
        run_job()
        # Reschedule with a new random interval after each run
        interval = random.randint(
            config.CHECK_INTERVAL_MIN,
            config.CHECK_INTERVAL_MAX
        )
        logger.info(f"Next check in {interval} minutes.")
        scheduler.reschedule_job(
            "appointment_check",
            trigger=IntervalTrigger(minutes=interval)
        )

    initial_interval = random.randint(
        config.CHECK_INTERVAL_MIN,
        config.CHECK_INTERVAL_MAX
    )
    logger.info(
        f"First scheduled check in {initial_interval} minutes "
        f"(range {config.CHECK_INTERVAL_MIN}–{config.CHECK_INTERVAL_MAX})"
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(
        scheduled_job,
        trigger=IntervalTrigger(minutes=initial_interval),
        id="appointment_check",
        name="BUPA appointment check",
        max_instances=1,
        coalesce=True,
    )

    # Handle graceful shutdown on SIGTERM (for Docker)
    def shutdown_handler(signum, frame):
        logger.info("Received shutdown signal, stopping bot...")
        scheduler.shutdown(wait=True)
        notify.notify_shutdown()
        exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)

    # Run scheduler in a separate thread to allow signal handling in main thread
    scheduler_thread = threading.Thread(target=scheduler.start, daemon=True)
    scheduler_thread.start()

    # Wait for signals in main thread
    try:
        signal.pause()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        scheduler.shutdown(wait=True)
        notify.notify_shutdown()


if __name__ == "__main__":
    main()