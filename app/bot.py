# app/bot.py
#
# Core automation module for BUPA appointment rescheduling.
# Flow: search -> modify -> location -> date/time selection -> confirmation.

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
    path = os.path.join(
        config.SCREENSHOT_DIR,
        f"{config.CONTAINER_NAME}_{name}.png"
    )
    logger.info(f"Taking screenshot — path: {path}")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved: {name}.png")


def _select_date_and_time(page) -> tuple[bool, str]:
    """
    Scan available date buttons and timeslots.
    Selects the earliest date/time that is:
      - Before the current appointment date
      - Not within 1 hour of now
    Returns (True, detail) on success, (False, reason) otherwise.
    """
    try:
        current_appt = datetime.strptime(config.CURRENT_APPT_DATE, "%d/%m/%Y")
    except ValueError:
        reason = (
            f"Invalid CURRENT_APPT_DATE format: '{config.CURRENT_APPT_DATE}'"
            f" — expected DD/MM/YYYY"
        )
        logger.error(reason)
        return False, reason

    now    = datetime.now()
    cutoff = now + timedelta(hours=1)

    logger.info(f"Current appointment : {current_appt.strftime('%d/%m/%Y')}")
    logger.info(f"Cutoff (now + 1hr)  : {cutoff.strftime('%d/%m/%Y %H:%M')}")

    # --- Collect all date buttons ---
    date_buttons = page.locator("button.pagination-navigation-btn").all()
    logger.info(f"Date buttons found  : {len(date_buttons)}")

    for i, btn in enumerate(date_buttons):
        logger.info(
            f"  [{i}] "
            f"data-value={btn.get_attribute('data-value')!r} "
            f"class={btn.get_attribute('class')!r}"
        )

    # --- Filter valid dates ---
    valid_dates = []
    for btn in date_buttons:
        raw = btn.get_attribute("data-value")
        if not raw:
            continue
        try:
            btn_date = datetime.strptime(raw, "%d/%m/%Y")
        except ValueError:
            logger.warning(f"  Could not parse date: {raw!r}")
            continue

        if btn_date >= current_appt:
            logger.info(f"  Skip {raw} — not earlier than current appointment.")
            continue
        if btn_date.date() < now.date():
            logger.info(f"  Skip {raw} — date is in the past.")
            continue

        logger.info(f"  Valid date candidate: {raw}")
        valid_dates.append((btn_date, btn, raw))

    if not valid_dates:
        reason = "No dates earlier than current appointment found."
        logger.info(reason)
        logger.info(
            f"Taking screenshot before returning "
            f"— SCREENSHOT_DIR: {config.SCREENSHOT_DIR}"
        )
        _screenshot(page, "available_slots")
        return False, reason

    valid_dates.sort(key=lambda x: x[0])
    # --- Try each valid date until we find one with timeslots ---
    for earliest_date, earliest_btn, earliest_raw in valid_dates:
        logger.info(f"Trying date : {earliest_raw}")

        # --- Click date and wait for timeslots ---
        earliest_btn.click()
        try:
            page.wait_for_selector(
                'input[type="radio"][name^="rblResults"]',
                timeout=10000,
                state="visible"
            )
            logger.info("Timeslots loaded.")
        except Exception:
            logger.warning(f"Timeslots did not appear after clicking {earliest_raw}.")
            continue  # Try next date

        _screenshot(page, "available_slots")

        # --- Collect and filter timeslots ---
        radio_buttons = page.locator(
            'input[type="radio"][name^="rblResults"]'
        ).all()
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
                logger.warning(f"  Could not parse timeslot: {time_text!r}")
                continue

            if slot_dt <= cutoff:
                logger.info(f"  Skip {time_text} — within 1 hour of now.")
                continue

            logger.info(f"  Valid timeslot: {time_text}")
            valid_slots.append((slot_dt, radio, time_text))

        if valid_slots:
            # Found valid slots on this date
            break
        else:
            logger.warning(f"No valid timeslots on {earliest_raw}.")
            continue  # Try next date

    if not valid_slots:
        reason = "No valid timeslots found on any earlier date."
        logger.info(reason)
        logger.info(
            f"Taking screenshot before returning "
            f"— SCREENSHOT_DIR: {config.SCREENSHOT_DIR}"
        )
        _screenshot(page, "available_slots")
        return False, reason

    valid_slots.sort(key=lambda x: x[0])
    _, earliest_radio, earliest_time = valid_slots[0]
    logger.info(f"Earliest valid slot : {earliest_time}")

    # --- Select timeslot and click Next ---
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

    detail = f"Slot selected: {earliest_raw} at {earliest_time}"
    logger.info(detail)
    return True, detail


def _confirm_and_save(page) -> tuple[bool, str]:
    """
    Read confirmed date and location from the confirmation page,
    click Save changes, and persist the result.
    Returns (True, detail) on success, (False, reason) otherwise.
    """
    try:
        page.wait_for_selector(
            'h2:has-text("New date and location")',
            timeout=10000,
            state="visible"
        )
    except Exception:
        reason = "Confirmation page not detected — page structure may have changed."
        logger.warning(reason)
        _screenshot(page, "error")
        return False, reason

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
        reason = "Save changes button not found on confirmation page."
        logger.warning(reason)
        return False, reason

    save_btn.click()
    page.wait_for_load_state("networkidle", timeout=30000)

    _screenshot(page, "saved")

    # --- Persist confirmed appointment ---
    config.save_confirmed_appointment(
        date=confirmed_date,
        time="",
        location=confirmed_location
    )

    detail = f"Appointment updated — {confirmed_date} at {confirmed_location}"
    logger.info(detail)
    return True, detail


def check_appointments():
    """
    Full automation flow:
      1. Load search page and submit credentials
      2. Click Modify on existing appointment
      3. Click Next through the location page
      4. Select earliest valid date and timeslot
      5. Read and confirm the summary page
      6. Save changes and notify result
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
            ),
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        page = context.new_page()
        import time
        import random
        time.sleep(random.uniform(1, 3))  # Random delay to mimic human

        try:
            # -- 1. Search page --
            logger.info("Step 1: Loading search page...")
            page.goto(
                config.BUPA_URL,
                wait_until="load",
                timeout=30000
            )
            logger.info("Step 1: Search page loaded.")

            page.locator("#txtHAPID").fill(config.HAP_ID)
            page.locator("#txtEmail").fill(config.EMAIL)
            page.locator("#txtFirstName").fill(config.GIVEN_NAMES)
            page.locator("#txtSurname").fill(config.FAMILY_NAME)
            page.locator("#txtDOB").fill(config.DOB)
            logger.info("Step 1: Credentials filled.")

            page.locator("#ContentPlaceHolder1_btnSearch").click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Step 1: Search results loaded.")

            # -- 2. Modify existing appointment --
            logger.info("Step 2: Looking for Modify button...")
            modify_btn = page.locator(
                "#ContentPlaceHolder1_repAppointments_lnkChangeAppointment_0"
            )
            if modify_btn.count() == 0:
                reason = "Modify button not found — no existing appointment detected."
                logger.warning(f"Step 2 FAILED: {reason}")
                _screenshot(page, "error")
                notify.notify_error(reason)
                return

            modify_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Step 2: Modify page loaded.")

            # -- 3. Location page — click Next without changes --
            logger.info("Step 3: Looking for Next button on location page...")
            next_btn = page.locator("#ContentPlaceHolder1_btnCont")
            if next_btn.count() == 0:
                reason = "Next button not found on location page."
                logger.warning(f"Step 3 FAILED: {reason}")
                _screenshot(page, "error")
                notify.notify_error(reason)
                return

            next_btn.click()
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Step 3: Date selection page loaded.")

            # -- 4. Select earliest valid date and timeslot --
            logger.info("Step 4: Selecting date and timeslot...")
            slot_found, slot_detail = _select_date_and_time(page)
            logger.info(
                f"Step 4: slot_found={slot_found} "
                f"detail={slot_detail!r}"
            )

            if not slot_found:
                notify.notify_result(
                    success=False,
                    detail=slot_detail,
                    screenshot="available_slots"
                )
                return

            # -- 5. Confirmation page --
            logger.info("Step 5: Reading confirmation page...")
            confirmed, confirm_detail = _confirm_and_save(page)
            logger.info(
                f"Step 5: confirmed={confirmed} "
                f"detail={confirm_detail!r}"
            )

            if not confirmed:
                logger.warning(f"Step 5 FAILED: {confirm_detail}")
                notify.notify_result(
                    success=False,
                    detail=confirm_detail,
                    screenshot="error"
                )
                return

            # -- 6. Success --
            logger.info("Step 6: Full flow complete.")
            notify.notify_result(
                success=True,
                detail=confirm_detail,
                screenshot="confirmation"
            )
            logger.info("Step 6: Appointment successfully updated.")

        except PlaywrightTimeout as e:
            reason = f"Page timeout: {e}"
            logger.error(reason)
            try:
                _screenshot(page, "error")
            except Exception:
                pass
            notify.notify_error(reason)

        except Exception as e:
            reason = f"Unexpected error ({type(e).__name__}): {e}"
            logger.error(reason)
            try:
                _screenshot(page, "error")
            except Exception:
                pass
            notify.notify_error(reason)

        finally:
            browser.close()