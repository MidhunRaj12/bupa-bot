# app/bot.py
#
# Core automation module for BUPA appointment rescheduling.
# Handles the full flow: search -> modify -> date/time selection -> confirmation.

import os
from datetime import datetime, timedelta
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from app import config, notify


def setup_logger():
    """Initialise loguru file + console sink."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    logger.add(
        os.path.join(config.LOG_DIR, f"{config.CONTAINER_NAME}.log"),
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )


def _screenshot(page, name: str):
    """Save a full-page screenshot to the configured screenshot directory."""
    path = os.path.join(config.SCREENSHOT_DIR, f"{config.CONTAINER_NAME}_{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved: {name}.png")


def _select_date_and_time(page) -> bool:
    """
    Scan available date buttons and timeslots.
    Select the earliest date/time that is:
      - Before the current appointment date
      - Not within 1 hour of now
    Returns True if a valid slot was selected and submitted, False otherwise.
    """
    try:
        current_appt = datetime.strptime(config.CURRENT_APPT_DATE, "%d/%m/%Y")
    except ValueError:
        logger.error(
            f"Invalid CURRENT_APPT_DATE: '{config.CURRENT_APPT_DATE}' "
            f"— expected DD/MM/YYYY"
        )
        return False

    now    = datetime.now()
    cutoff = now + timedelta(hours=1)

    logger.info(f"Current appointment : {current_appt.strftime('%d/%m/%Y')}")
    logger.info(f"Cutoff (now + 1hr)  : {cutoff.strftime('%d/%m/%Y %H:%M')}")

    # --- Collect and filter date buttons ---
    date_buttons = page.locator("button.pagination-navigation-btn").all()
    logger.info(f"Date buttons found  : {len(date_buttons)}")

    valid_dates = []
    for btn in date_buttons:
        raw = btn.get_attribute("data-value")
        if not raw:
            continue
        try:
            btn_date = datetime.strptime(raw, "%d/%m/%Y")
        except ValueError:
            continue

        if btn_date >= current_appt:
            continue
        if btn_date.date() < now.date():
            continue

        valid_dates.append((btn_date, btn, raw))

    if not valid_dates:
        logger.info("No earlier dates available — current appointment is already the earliest.")
        notify.notify_error("No earlier dates found.")
        return False

    valid_dates.sort(key=lambda x: x[0])
    earliest_date, earliest_btn, earliest_raw = valid_dates[0]
    logger.info(f"Earliest valid date : {earliest_raw}")

    # --- Click the date button and wait for timeslots ---
    earliest_btn.click()
    try:
        page.wait_for_selector(
            'input[type="radio"][name^="rblResults"]',
            timeout=10000,
            state="visible"
        )
    except Exception:
        logger.warning("Timeslots did not appear after clicking date.")
        return False

    _screenshot(page, "available_slots")

    # --- Collect and filter timeslots ---
    radio_buttons = page.locator('input[type="radio"][name^="rblResults"]').all()
    logger.info(f"Timeslots found     : {len(radio_buttons)}")

    valid_slots = []
    for radio in radio_buttons:
        time_text = radio.get_attribute("data-text")
        if not time_text:
            continue
        try:
            slot_dt = datetime.strptime(
                f"{earliest_raw} {time_text}", "%d/%m/%Y %I:%M %p"
            )
        except ValueError:
            continue

        if slot_dt <= cutoff:
            continue

        valid_slots.append((slot_dt, radio, time_text))

    if not valid_slots:
        logger.info(f"No valid timeslots on {earliest_raw} — all are within 1 hour or past.")
        notify.notify_error(f"No valid timeslots on {earliest_raw}.")
        return False

    valid_slots.sort(key=lambda x: x[0])
    _, earliest_radio, earliest_time = valid_slots[0]
    logger.info(f"Earliest valid slot : {earliest_time}")

    # --- Select timeslot and proceed ---
    earliest_radio.click()

    try:
        page.wait_for_selector(
            "#ContentPlaceHolder1_btnCont:not([disabled])",
            timeout=5000,
            state="visible"
        )
    except Exception:
        logger.warning("Next button did not activate — proceeding anyway.")

    page.locator("#ContentPlaceHolder1_btnCont").click()
    page.wait_for_load_state("networkidle", timeout=30000)
    logger.info("Slot selection submitted.")

    return True


def _confirm_and_save(page) -> bool:
    """
    Read the confirmed date and location from the confirmation page,
    click Save changes, and persist the result.
    Returns True on success, False otherwise.
    """
    try:
        page.wait_for_selector(
            'h2:has-text("New date and location")',
            timeout=10000,
            state="visible"
        )
    except Exception:
        logger.warning("Confirmation box not found — page may have changed.")
        _screenshot(page, "confirm_missing")
        return False

    # --- Read confirmed details ---
    confirmed_date     = "unknown"
    confirmed_location = "unknown"

    try:
        for row in page.locator(".appointments-row").all():
            label = row.locator("label").inner_text().strip().lower()
            value = row.locator(".fLeft").inner_text().strip()
            if "date" in label:
                confirmed_date = value
            elif "location" in label:
                confirmed_location = value
    except Exception as e:
        logger.warning(f"Could not read confirmation details: {e}")

    logger.info(f"Confirmed date     : {confirmed_date}")
    logger.info(f"Confirmed location : {confirmed_location}")

    _screenshot(page, "confirmation")

    # --- Click Save changes ---
    save_btn = page.locator('button:has-text("Save changes")')
    if save_btn.count() == 0:
        logger.warning("Save changes button not found.")
        notify.notify_error("Save changes button not found on confirmation page.")
        return False

    save_btn.click()
    page.wait_for_load_state("networkidle", timeout=30000)

    _screenshot(page, "saved")

    # --- Persist and notify ---
    config.save_confirmed_appointment(
        date=confirmed_date,
        time="",
        location=confirmed_location
    )
    notify.notify_slot_found(
        location=confirmed_location,
        date=confirmed_date,
        time=""
    )
    logger.info(f"Appointment updated — {confirmed_date} at {confirmed_location}")

    return True


def check_appointments():
    """
    Full automation flow:
      1. Load search page and submit credentials
      2. Click Modify on the existing appointment
      3. Click Next through the location page
      4. Select the earliest valid date and timeslot
      5. Read and confirm the summary page
      6. Save changes
    """
    logger.info(f"Starting check — container: {config.CONTAINER_NAME}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=config.HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            # -- 1. Search page --
            page.goto(config.BUPA_URL, wait_until="networkidle", timeout=30000)
            logger.info("Search page loaded.")

            page.locator("#txtHAPID").fill(config.HAP_ID)
            page.locator("#txtEmail").fill(config.EMAIL)
            page.locator("#txtFirstName").fill(config.GIVEN_NAMES)
            page.locator("#txtSurname").fill(config.FAMILY_NAME)
            page.locator("#txtDOB").fill(config.DOB)

            page.locator("#ContentPlaceHolder1_btnSearch").click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Search results loaded.")

            # -- 2. Modify existing appointment --
            modify_btn = page.locator(
                "#ContentPlaceHolder1_repAppointments_lnkChangeAppointment_0"
            )
            if modify_btn.count() == 0:
                logger.warning("Modify button not found — no existing appointment detected.")
                notify.notify_error("Modify button not found on results page.")
                return

            modify_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Modify page loaded.")

            # -- 3. Location page — click Next without changes --
            next_btn = page.locator("#ContentPlaceHolder1_btnCont")
            if next_btn.count() == 0:
                logger.warning("Next button not found on location page.")
                notify.notify_error("Next button not found on location page.")
                return

            next_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Date selection page loaded.")

            # -- 4. Select earliest valid date and timeslot --
            if not _select_date_and_time(page):
                logger.info("No suitable slot this run — will retry on next schedule.")
                return

            # -- 5. Confirmation page --
            if not _confirm_and_save(page):
                logger.warning("Confirmation step failed — check screenshots.")
                return

            logger.info("Flow complete — appointment successfully updated.")

        except PlaywrightTimeout as e:
            logger.error(f"Page timeout: {e}")
            try:
                _screenshot(page, "timeout")
            except Exception:
                pass
            notify.notify_error(f"Timeout: {e}")

        except Exception as e:
            logger.error(f"Unexpected error ({type(e).__name__}): {e}")
            try:
                _screenshot(page, "error")
            except Exception:
                pass
            notify.notify_error(str(e))

        finally:
            browser.close()