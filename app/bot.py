# app/bot.py
import os
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from app import config, notify

URL = "https://bmvs.onlineappointmentscheduling.net.au/oasis/Search.aspx"

def setup_logger():
    """Configure loguru to write to file + console."""
    # Create dirs first, before loguru tries to open the file
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

"""@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=30)
)"""
def check_appointments():
    """
    Phase 2: Fill form fields, click search, keep browser open for inspection.
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
            # --- Step 1: Load the page ---
            logger.info(f"Navigating to {config.BUPA_URL}")
            page.goto(config.BUPA_URL, wait_until="networkidle", timeout=30000)
            logger.info("Page loaded successfully.")

            # --- Step 2: Fill form fields ---
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

            # --- Step 3: Screenshot before submitting ---
            screenshot_path = os.path.join(
                config.SCREENSHOT_DIR,
                f"{config.CONTAINER_NAME}_before_submit.png"
            )
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Pre-submit screenshot saved → {screenshot_path}")

            # --- Step 4: Click search ---
            logger.info("Clicking search button...")
            page.locator('#ContentPlaceHolder1_btnSearch').click()

            # Wait for next page to fully load
            page.wait_for_load_state("networkidle", timeout=30000)
            logger.info("Search submitted — next page loaded.")
            logger.info(f"Current URL: {page.url}")
            logger.info(f"Page title:  {page.title()}")

            # --- Step 5: Screenshot of result page ---
            screenshot_path = os.path.join(
                config.SCREENSHOT_DIR,
                f"{config.CONTAINER_NAME}_after_submit.png"
            )
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Post-submit screenshot saved → {screenshot_path}")

            # --- Step 6: Find and click modify date/location ---
            logger.info("Looking for 'modify date/location' button...")

            modify_btn = page.locator(
                '#ContentPlaceHolder1_repAppointments_lnkChangeAppointment_0'
            )

            if modify_btn.count() > 0:
                logger.info("  ✅ Modify button found — clicking...")
                modify_btn.click()

                # ASP.NET postback — wait for full page reload
                page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("Modify page loaded.")
                logger.info(f"Current URL: {page.url}")
                logger.info(f"Page title:  {page.title()}")

                # Screenshot of modify page
                screenshot_path = os.path.join(
                    config.SCREENSHOT_DIR,
                    f"{config.CONTAINER_NAME}_modify_page.png"
                )
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"Modify page screenshot saved → {screenshot_path}")

            else:
                logger.warning("  ❌ Modify button not found on page.")
                logger.warning("  Possible reasons:")
                logger.warning("  - Credentials incorrect")
                logger.warning("  - No existing appointment found")
                logger.warning("  - Page structure different than expected")

            # --- Step 7: Keep browser open for inspection ---
            logger.info("=" * 50)
            logger.info("Browser staying open — inspect the modify page.")
            logger.info("Press Enter in terminal when done...")
            logger.info("=" * 50)



            input()     # ← pauses here, browser stays open

        except Exception as e:
            logger.error(f"Unexpected error type: {type(e).__name__}")
            logger.error(f"Unexpected error detail: {e}")
            try:
                screenshot_path = os.path.join(
                    config.SCREENSHOT_DIR,
                    f"{config.CONTAINER_NAME}_error.png"
                )
                page.screenshot(path=screenshot_path)
                logger.info(f"Error screenshot saved → {screenshot_path}")
            except Exception as ss_err:
                logger.warning(f"Could not take error screenshot: {ss_err}")
            raise

        finally:
            browser.close()