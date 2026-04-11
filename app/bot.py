# app/bot.py
import os
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from app import config, notify

URL = "https://bmvs.onlineappointmentscheduling.net.au/oasis/Search.aspx"

def setup_logger():
    """Configure loguru to write to file + console."""
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    log_path = f"/app/logs/{config.CONTAINER_NAME}.log"
    logger.add(
        log_path,
        rotation="10 MB",
        retention="7 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    logger.info(f"Logger initialised → {log_path}")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=5, max=30)
)
def check_appointments():
    """
    Main automation function.
    Phase 1: Load page, verify form fields exist, take screenshot.
    Phase 2 (next): fill form and check for slots.
    """
    logger.info(f"[{config.CONTAINER_NAME}] Starting appointment check...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=config.HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"]  # required in Docker
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
            logger.info(f"Navigating to {URL}")
            page.goto(URL, wait_until="networkidle", timeout=30000)
            logger.info("Page loaded successfully.")

            # --- Step 2: Verify key form fields exist ---
            fields = {
                "HAP ID field":     'input[name*="HapId"], input[id*="HapId"]',
                "Email field":      'input[type="email"], input[id*="Email"]',
                "Given name field": 'input[id*="Given"], input[id*="First"]',
                "Family name field":'input[id*="Family"], input[id*="Last"]',
                "DOB field":        'input[id*="Dob"], input[id*="Birth"]',
                "Submit button":    'input[type="submit"], button[type="submit"]',
            }

            results = {}
            for label, selector in fields.items():
                found = page.locator(selector).count() > 0
                results[label] = "✅ found" if found else "❌ NOT found"
                logger.info(f"  {label}: {results[label]}")

            # --- Step 3: Screenshot ---
            screenshot_path = (
                f"{config.SCREENSHOT_DIR}/"
                f"{config.CONTAINER_NAME}_check.png"
            )
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved → {screenshot_path}")

            # --- Step 4: Report ---
            all_found = all("✅" in v for v in results.values())
            if all_found:
                logger.info("✅ All form fields detected — bot is ready for Phase 2.")
            else:
                missing = [k for k, v in results.items() if "❌" in v]
                logger.warning(f"Some fields not found: {missing}")
                notify.notify_error(f"Fields not found: {missing}")

            return results

        except PlaywrightTimeout as e:
            screenshot_path = (
                f"{config.SCREENSHOT_DIR}/"
                f"{config.CONTAINER_NAME}_timeout.png"
            )
            page.screenshot(path=screenshot_path)
            logger.error(f"Timeout: {e}")
            notify.notify_error(f"Page timeout: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            notify.notify_error(str(e))
            raise

        finally:
            browser.close()