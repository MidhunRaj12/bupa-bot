# app/bot.py
import os
from datetime import datetime, timedelta
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from app import config, notify

URL = "https://bmvs.onlineappointmentscheduling.net.au/oasis/Search.aspx"

def setup_logger():
    """Configure loguru to write to file + console."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)

    log_path = os.path.join(config.LOG_DIR, f"{config.CONTAINER_NAME}.log")

    logger.add(
        log_path,
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    logger.info(f"Logger initialised → {log_path}")


def _select_date_and_time(page):
    """
    Find the earliest available date before current appointment,
    select the earliest valid timeslot, and click Next.
    Returns True if a slot was selected and submitted, False otherwise.
    """

    # --- Parse current appointment date ---
    try:
        current_appt = datetime.strptime(config.CURRENT_APPT_DATE, "%d/%m/%Y")
    except ValueError:
        logger.error(
            f"Invalid CURRENT_APPT_DATE format: '{config.CURRENT_APPT_DATE}' "
            f"— expected DD/MM/YYYY"
        )
        return False

    now      = datetime.now()
    cutoff   = now + timedelta(hours=1)
    logger.info(f"Current appointment : {current_appt.strftime('%d/%m/%Y')}")
    logger.info(f"Now                 : {now.strftime('%d/%m/%Y %H:%M')}")
    logger.info(f"Cutoff (now +1hr)   : {cutoff.strftime('%d/%m/%Y %H:%M')}")

    # --- Step 1: Get all date buttons ---
    date_buttons = page.locator('button.pagination-navigation-btn').all()
    logger.info(f"Found {len(date_buttons)} date buttons on page.")

    if not date_buttons:
        logger.warning("No date buttons found on page.")
        return False

    # --- Step 2: Filter valid dates ---
    valid_dates = []

    for btn in date_buttons:
        raw_date = btn.get_attribute("data-value")   # e.g. "30/04/2026"
        if not raw_date:
            continue

        try:
            btn_date = datetime.strptime(raw_date, "%d/%m/%Y")
        except ValueError:
            logger.warning(f"  Could not parse date: {raw_date!r}")
            continue

        # Must be strictly earlier than current appointment
        if btn_date >= current_appt:
            logger.info(f"  Skip {raw_date} — not earlier than current appt.")
            continue

        # Must not be in the past
        if btn_date.date() < now.date():
            logger.info(f"  Skip {raw_date} — date is in the past.")
            continue

        valid_dates.append((btn_date, btn, raw_date))
        logger.info(f"  ✅ Valid date candidate: {raw_date}")

    if not valid_dates:
        logger.info("No earlier dates found — current appointment is already the earliest.")
        notify.notify_error("No earlier dates found — nothing to change.")
        return False

    # Sort ascending — pick earliest
    valid_dates.sort(key=lambda x: x[0])
    earliest_date, earliest_btn, earliest_raw = valid_dates[0]
    logger.info(f"Selecting earliest valid date: {earliest_raw}")

    # --- Step 3: Click the date button ---
    earliest_btn.click()

    # Wait for timeslots to load (AJAX, same page)
    try:
        page.wait_for_selector(
            'input[type="radio"][name^="rblResults"]',
            timeout=10000,
            state="visible"
        )
        logger.info("Timeslots loaded.")
    except Exception:
        logger.warning("Timeslots did not appear after clicking date.")
        return False

    # Screenshot with timeslots visible
    screenshot_path = os.path.join(
        config.SCREENSHOT_DIR,
        f"{config.CONTAINER_NAME}_timeslots.png"
    )
    page.screenshot(path=screenshot_path, full_page=True)
    logger.info(f"Timeslot screenshot → {screenshot_path}")

    # --- Step 4: Get all timeslot radio buttons ---
    radio_buttons = page.locator(
        'input[type="radio"][name^="rblResults"]'
    ).all()
    logger.info(f"Found {len(radio_buttons)} timeslots.")

    if not radio_buttons:
        logger.warning("No timeslots found after clicking date.")
        return False

    # --- Step 5: Filter valid timeslots ---
    valid_slots = []

    for radio in radio_buttons:
        time_text = radio.get_attribute("data-text")   # e.g. "8:15 AM"
        if not time_text:
            continue

        try:
            slot_dt = datetime.strptime(
                f"{earliest_raw} {time_text}", "%d/%m/%Y %I:%M %p"
            )
        except ValueError:
            logger.warning(f"  Could not parse timeslot: {time_text!r}")
            continue

        # Must be at least 1 hour from now
        if slot_dt <= cutoff:
            logger.info(f"  Skip {time_text} — within 1 hour of now.")
            continue

        valid_slots.append((slot_dt, radio, time_text))
        logger.info(f"  ✅ Valid timeslot: {time_text}")

    if not valid_slots:
        logger.info(
            f"No valid timeslots on {earliest_raw} "
            f"— all are too soon or in the past."
        )
        notify.notify_error(
            f"No valid timeslots found on {earliest_raw}."
        )
        return False

    # Sort ascending — pick earliest
    valid_slots.sort(key=lambda x: x[0])
    earliest_slot_dt, earliest_radio, earliest_time = valid_slots[0]
    logger.info(f"Selecting earliest timeslot: {earliest_time}")

    # --- Step 6: Click the radio button ---
    earliest_radio.click()

    # Wait for Next button to activate after selection
    try:
        page.wait_for_selector(
            '#ContentPlaceHolder1_btnCont:not([disabled])',
            timeout=5000,
            state="visible"
        )
        logger.info("Next button is active.")
    except Exception:
        logger.warning("Next button did not activate — proceeding anyway.")

    # Screenshot with slot selected
    screenshot_path = os.path.join(
        config.SCREENSHOT_DIR,
        f"{config.CONTAINER_NAME}_slot_selected.png"
    )
    page.screenshot(path=screenshot_path, full_page=True)
    logger.info(f"Slot selected screenshot → {screenshot_path}")

    # --- Step 7: Click Next ---
    logger.info("Clicking Next to confirm slot...")
    page.locator('#ContentPlaceHolder1_btnCont').click()
    page.wait_for_load_state("networkidle", timeout=30000)
    logger.info("✅ Slot submitted.")
    logger.info(f"URL  : {page.url}")
    logger.info(f"Title: {page.title()}")

    # Screenshot of confirmation page
    screenshot_path = os.path.join(
        config.SCREENSHOT_DIR,
        f"{config.CONTAINER_NAME}_confirmation.png"
    )
    page.screenshot(path=screenshot_path, full_page=True)
    logger.info(f"Confirmation screenshot → {screenshot_path}")

    # Save confirmed appointment to file
    config.save_confirmed_appointment(
        date=earliest_raw,
        time=earliest_time,
        location=config.PREFERRED_LOCATION
    )
    logger.info(
        f"✅ Appointment saved — {earliest_raw} at {earliest_time}"
    )
    notify.notify_slot_found(
        location=config.PREFERRED_LOCATION,
        date=earliest_raw,
        time=earliest_time
    )

    return True


def check_appointments():
    """
    Full automation flow:
    1. Load search page
    2. Fill credentials and search
    3. Click modify on existing appointment
    4. Click Next on location page
    5. Select earliest valid date and timeslot
    6. Submit and save confirmation
    """
    logger.info(f"[{config.CONTAINER_NAME}] Starting appointment check...")

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
            # ── 1. Load page ──────────────────────────────────────────
            logger.info(f"Navigating to {config.BUPA_URL}")
            page.goto(
                config.BUPA_URL,
                wait_until="networkidle",
                timeout=30000
            )
            logger.info("Page loaded successfully.")

            # ── 2. Fill credentials ───────────────────────────────────
            logger.info("Filling form fields...")
            page.locator('#txtHAPID').fill(config.HAP_ID)
            logger.info("  HAP ID filled.")
            page.locator('#txtEmail').fill(config.EMAIL)
            logger.info("  Email filled.")
            page.locator('#txtFirstName').fill(config.GIVEN_NAMES)
            logger.info("  Given name filled.")
            page.locator('#txtSurname').fill(config.FAMILY_NAME)
            logger.info("  Family name filled.")
            page.locator('#txtDOB').fill(config.DOB)
            logger.info("  DOB filled.")

            # Screenshot before submit
            page.screenshot(
                path=os.path.join(
                    config.SCREENSHOT_DIR,
                    f"{config.CONTAINER_NAME}_before_submit.png"
                ),
                full_page=True
            )

            # ── 3. Click Search ───────────────────────────────────────
            logger.info("Clicking Search...")
            page.locator('#ContentPlaceHolder1_btnSearch').click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info(f"Search results loaded — {page.title()}")

            page.screenshot(
                path=os.path.join(
                    config.SCREENSHOT_DIR,
                    f"{config.CONTAINER_NAME}_after_submit.png"
                ),
                full_page=True
            )

            # ── 4. Click Modify ───────────────────────────────────────
            logger.info("Looking for Modify button...")
            modify_btn = page.locator(
                '#ContentPlaceHolder1_repAppointments_lnkChangeAppointment_0'
            )

            if modify_btn.count() == 0:
                logger.warning("Modify button not found — no existing appointment?")
                notify.notify_error("Modify button not found on results page.")
                return

            logger.info("  ✅ Modify button found — clicking...")
            modify_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info(f"Modify page loaded — {page.title()}")

            page.screenshot(
                path=os.path.join(
                    config.SCREENSHOT_DIR,
                    f"{config.CONTAINER_NAME}_modify_page.png"
                ),
                full_page=True
            )

            # ── 5. Click Next on location page ────────────────────────
            logger.info("Clicking Next on location page...")
            next_btn = page.locator('#ContentPlaceHolder1_btnCont')

            if next_btn.count() == 0:
                logger.warning("Next button not found on location page.")
                notify.notify_error("Next button not found on location page.")
                return

            next_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info(f"Date selection page loaded — {page.title()}")

            page.screenshot(
                path=os.path.join(
                    config.SCREENSHOT_DIR,
                    f"{config.CONTAINER_NAME}_date_page.png"
                ),
                full_page=True
            )

            # ── 6. Select date and timeslot ───────────────────────────
            result = _select_date_and_time(page)

            if not result:
                logger.info("No suitable slot found this run — will retry on next schedule.")

            # ── 7. Keep browser open for inspection ───────────────────
            logger.info("=" * 50)
            logger.info("Browser staying open — press Enter to close.")
            logger.info("=" * 50)
            input()

        except PlaywrightTimeout as e:
            logger.error(f"Timeout: {e}")
            try:
                page.screenshot(
                    path=os.path.join(
                        config.SCREENSHOT_DIR,
                        f"{config.CONTAINER_NAME}_timeout.png"
                    )
                )
            except Exception:
                pass
            notify.notify_error(f"Timeout: {e}")

        except Exception as e:
            logger.error(f"Error type   : {type(e).__name__}")
            logger.error(f"Error detail : {e}")
            try:
                page.screenshot(
                    path=os.path.join(
                        config.SCREENSHOT_DIR,
                        f"{config.CONTAINER_NAME}_error.png"
                    )
                )
            except Exception:
                pass
            notify.notify_error(str(e))

        finally:
            browser.close()