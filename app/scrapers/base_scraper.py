from abc import ABC, abstractmethod
from DrissionPage import ChromiumPage, ChromiumOptions
from typing import List, Dict, Optional
import time
import random
import logging
from datetime import datetime, timedelta
from app.core.database import Listing, ScrapingState
from sqlalchemy.orm import Session
import json
import os

from app.utils.phone_normalizer import normalize_israeli_phone
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global CAPTCHA state singleton
class CaptchaState:
    """Singleton to track CAPTCHA status across all scrapers"""
    _instance = None
    _status = "NORMAL"  # NORMAL, WAITING_FOR_CAPTCHA
    _waiting_since = None
    _source = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CaptchaState, cls).__new__(cls)
        return cls._instance

    def set_waiting(self, source: str):
        """Set status to waiting for CAPTCHA"""
        self._status = "WAITING_FOR_CAPTCHA"
        self._waiting_since = datetime.utcnow()
        self._source = source
        logger.warning(f"⚠️ CAPTCHA State: Set to WAITING (source: {source})")

    def set_normal(self):
        """Reset to normal status"""
        self._status = "NORMAL"
        self._waiting_since = None
        self._source = None
        logger.info("✅ CAPTCHA State: Reset to NORMAL")

    def is_waiting(self) -> bool:
        """Check if currently waiting for CAPTCHA"""
        return self._status == "WAITING_FOR_CAPTCHA"

    def get_status(self) -> Dict:
        """Get current status as dictionary"""
        return {
            "status": self._status,
            "waiting_since": self._waiting_since.isoformat() if self._waiting_since else None,
            "source": self._source,
            "elapsed_minutes": (datetime.utcnow() - self._waiting_since).total_seconds() / 60 if self._waiting_since else 0
        }

    def is_timeout(self) -> bool:
        """Check if CAPTCHA wait has timed out"""
        if not self._waiting_since:
            return False
        elapsed = datetime.utcnow() - self._waiting_since
        return elapsed > timedelta(minutes=settings.captcha_timeout_minutes)

# Global instance
captcha_state = CaptchaState()


class BaseScraper(ABC):
    """Base class for all scrapers with common functionality using DrissionPage"""

    def __init__(self, db_session: Session, source_name: str):
        self.db = db_session
        self.source_name = source_name
        self.page: Optional[ChromiumPage] = None

    def initialize(self):
        """Initialize browser by connecting to existing Chrome instance on debug port"""
        try:
            # Connect to existing Chrome instance on the configured debug port
            debug_address = f"127.0.0.1:{settings.chrome_debug_port}"

            logger.info(f"[{self.source_name}] Attempting to connect to Chrome on {debug_address}")

            try:
                # Connect to existing browser instead of launching new one
                self.page = ChromiumPage(addr_or_opts=debug_address)
                logger.info(f"[{self.source_name}] ✅ Successfully connected to existing Chrome instance")

            except Exception as conn_error:
                # Provide helpful error message if connection fails
                error_msg = (
                    f"❌ Failed to connect to Chrome on port {settings.chrome_debug_port}.\n"
                    f"Please start Chrome with remote debugging enabled:\n\n"
                    f"macOS:\n"
                    f'/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome '
                    f'--remote-debugging-port={settings.chrome_debug_port} '
                    f'--user-data-dir="$HOME/chrome-profile-bot"\n\n'
                    f"Error: {conn_error}"
                )
                logger.error(f"[{self.source_name}] {error_msg}")
                raise ConnectionError(error_msg)

            # Inject anti-detection scripts (still useful even with persistent browser)
            self._inject_anti_detection_scripts()

            logger.info(f"[{self.source_name}] Browser connection established in persistent mode")

            # Load cookies if available
            self._load_cookies()

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to initialize browser: {e}")
            raise

    def _inject_anti_detection_scripts(self):
        """Inject JavaScript to further mask automation detection"""
        if not self.page:
            return

        try:
            # Override navigator.webdriver
            self.page.run_js("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Mock plugins
            self.page.run_js("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)

            # Mock languages
            self.page.run_js("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['he-IL', 'he', 'en-US', 'en']
                });
            """)

            # Override permissions
            self.page.run_js("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            # Mock chrome runtime
            self.page.run_js("""
                window.chrome = {
                    runtime: {}
                };
            """)

            logger.debug(f"[{self.source_name}] Anti-detection scripts injected")
        except Exception as e:
            logger.warning(f"[{self.source_name}] Failed to inject anti-detection scripts: {e}")

    def _load_cookies(self):
        """Load saved cookies for this source"""
        state = self.db.query(ScrapingState).filter(
            ScrapingState.source == self.source_name
        ).first()

        if state and state.cookies_json:
            try:
                cookies = json.loads(state.cookies_json)
                if cookies and self.page:
                    # DrissionPage cookie format
                    for cookie in cookies:
                        # Convert Playwright cookie format to DrissionPage format if needed
                        if 'sameSite' in cookie:
                            cookie['sameSite'] = cookie['sameSite'].capitalize()
                        self.page.set.cookies(cookie)
                    logger.info(f"Loaded cookies for {self.source_name}")
            except Exception as e:
                logger.warning(f"Failed to load cookies for {self.source_name}: {e}")

    def _save_cookies(self):
        """Save current cookies"""
        if not self.page:
            return

        try:
            cookies = self.page.cookies(all_domains=True)

            state = self.db.query(ScrapingState).filter(
                ScrapingState.source == self.source_name
            ).first()

            if not state:
                state = ScrapingState(source=self.source_name)
                self.db.add(state)

            state.cookies_json = json.dumps(cookies)
            self.db.commit()

        except Exception as e:
            logger.warning(f"Failed to save cookies for {self.source_name}: {e}")

    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add random delay to appear human-like"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def debug_save_page(self, prefix: str = "debug"):
        """Save page screenshot and HTML for debugging"""
        if not self.page:
            return

        try:
            # Create debug directory if it doesn't exist
            debug_dir = "debug_output"
            os.makedirs(debug_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save screenshot
            screenshot_path = os.path.join(debug_dir, f"{prefix}_{self.source_name}_{timestamp}.png")
            self.page.get_screenshot(path=screenshot_path, full_page=True)
            logger.info(f"[{self.source_name}] Saved debug screenshot: {screenshot_path}")

            # Save HTML
            html_path = os.path.join(debug_dir, f"{prefix}_{self.source_name}_{timestamp}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.page.html)
            logger.info(f"[{self.source_name}] Saved debug HTML: {html_path}")

        except Exception as e:
            logger.warning(f"[{self.source_name}] Failed to save debug output: {e}")

    def human_like_mouse_movement(self):
        """Simulate human-like mouse movements"""
        if not self.page:
            return

        try:
            # Generate random mouse movements
            for _ in range(random.randint(2, 5)):
                x = random.randint(100, 1800)
                y = random.randint(100, 900)

                # DrissionPage doesn't have direct mouse movement, but we can simulate clicks
                # This is less critical with CDP-based control
                time.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            logger.debug(f"[{self.source_name}] Mouse movement simulation failed: {e}")

    def scroll_page(self, scrolls: int = 3):
        """Scroll page to load dynamic content with human-like behavior"""
        if not self.page:
            return

        for i in range(scrolls):
            # Variable scroll amounts to appear more human
            scroll_amount = random.randint(300, 800)

            # Smooth scroll
            self.page.scroll.down(scroll_amount)

            # Random delay between scrolls
            self.random_delay(0.8, 2.5)

            # Occasionally scroll back up a bit (human behavior)
            if random.random() < 0.3:
                self.page.scroll.up(random.randint(50, 150))
                self.random_delay(0.3, 0.8)

    def safe_click(self, selector: str, timeout: int = 5) -> bool:
        """Safely click element with error handling"""
        if not self.page:
            return False

        try:
            element = self.page.ele(selector, timeout=timeout)
            if element:
                element.click()
                return True
        except Exception as e:
            logger.debug(f"Could not click {selector}: {e}")
        return False

    def safe_fill(self, selector: str, value: str, timeout: int = 5) -> bool:
        """Safely fill input with error handling"""
        if not self.page:
            return False

        try:
            element = self.page.ele(selector, timeout=timeout)
            if element:
                element.input(value)
                return True
        except Exception as e:
            logger.debug(f"Could not fill {selector}: {e}")
        return False

    def safe_get_text(self, selector: str, timeout: int = 5) -> Optional[str]:
        """Safely get text content"""
        if not self.page:
            return None

        try:
            element = self.page.ele(selector, timeout=timeout)
            if element:
                return element.text
        except Exception as e:
            logger.debug(f"Could not get text from {selector}: {e}")
        return None

    def normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number for matching.

        Deprecated: Use utils.phone_normalizer.normalize_israeli_phone instead.
        This method is kept for backward compatibility.
        """
        return normalize_israeli_phone(phone) or ""

    def update_scraping_state(self, success: bool = True, error_msg: Optional[str] = None):
        """Update scraping state in database"""
        state = self.db.query(ScrapingState).filter(
            ScrapingState.source == self.source_name
        ).first()

        if not state:
            state = ScrapingState(source=self.source_name)
            self.db.add(state)

        state.last_scrape_time = datetime.utcnow()

        if success:
            state.status = 'active'
            state.error_count = 0
            state.error_message = None
        else:
            state.status = 'error'
            state.error_count = (state.error_count or 0) + 1
            state.error_message = error_msg

        self.db.commit()

    def _handle_anti_bot_protection(self):
        """
        Detect and handle anti-bot protection (CAPTCHA, security checks, etc.)
        Pauses execution and waits for manual intervention if detected.
        """
        if not self.page:
            return

        try:
            # Get page title and content for detection
            page_title = self.page.title.lower() if self.page.title else ""
            page_html = self.page.html.lower() if self.page.html else ""

            # Common anti-bot indicators
            anti_bot_indicators = [
                "shieldsquare",
                "perimeterx",
                "security check",
                "אבטחת אתר",  # Hebrew: "Site security"
                "captcha",
                "recaptcha",
                "cloudflare",
                "access denied",
                "blocked",
                "bot detection",
                "human verification",
                "verify you are human"
            ]

            # Check if any indicator is present
            detected = False
            for indicator in anti_bot_indicators:
                if indicator in page_title or indicator in page_html:
                    detected = True
                    logger.warning(f"[{self.source_name}] 🚨 Anti-bot protection detected: '{indicator}'")
                    break

            if not detected:
                # If we were waiting and now it's clear, reset state
                if captcha_state.is_waiting():
                    logger.info(f"[{self.source_name}] ✅ Anti-bot protection cleared! Resuming scraping...")
                    captcha_state.set_normal()
                return

            # Anti-bot protection detected - enter wait loop
            logger.warning(f"[{self.source_name}] ⚠️ CAPTCHA Detected! Pausing for user intervention...")
            captcha_state.set_waiting(self.source_name)

            # Wait loop
            start_time = datetime.utcnow()
            check_count = 0

            while True:
                check_count += 1

                # Check for timeout
                if captcha_state.is_timeout():
                    elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
                    error_msg = (
                        f"CAPTCHA timeout after {elapsed:.1f} minutes. "
                        f"Please solve the CAPTCHA in the Chrome window and restart the scraper."
                    )
                    logger.error(f"[{self.source_name}] ❌ {error_msg}")
                    captcha_state.set_normal()
                    raise TimeoutError(error_msg)

                # Log status every 5 checks
                if check_count % 5 == 0:
                    elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
                    logger.info(
                        f"[{self.source_name}] ⏳ Still waiting for CAPTCHA resolution... "
                        f"({elapsed:.1f}/{settings.captcha_timeout_minutes} minutes)"
                    )

                # Wait before checking again
                logger.debug(f"[{self.source_name}] Sleeping {settings.captcha_check_interval}s before next check...")
                time.sleep(settings.captcha_check_interval)

                # Refresh page content and check again
                try:
                    self.page.refresh()
                    time.sleep(2)  # Wait for page to load

                    # Re-check for anti-bot indicators
                    page_title = self.page.title.lower() if self.page.title else ""
                    page_html = self.page.html.lower() if self.page.html else ""

                    still_blocked = False
                    for indicator in anti_bot_indicators:
                        if indicator in page_title or indicator in page_html:
                            still_blocked = True
                            break

                    if not still_blocked:
                        # CAPTCHA solved!
                        elapsed = (datetime.utcnow() - start_time).total_seconds() / 60
                        logger.info(
                            f"[{self.source_name}] ✅ CAPTCHA resolved after {elapsed:.1f} minutes! "
                            f"Resuming scraping..."
                        )
                        captcha_state.set_normal()
                        return

                except Exception as check_error:
                    logger.warning(f"[{self.source_name}] Error checking CAPTCHA status: {check_error}")
                    # Continue waiting

        except TimeoutError:
            # Re-raise timeout errors
            raise
        except Exception as e:
            logger.error(f"[{self.source_name}] Error in anti-bot protection handler: {e}")
            # Don't block scraping on handler errors
            captcha_state.set_normal()

    def cleanup(self):
        """Clean up browser resources (but don't close the persistent browser)"""
        try:
            self._save_cookies()
        except Exception as e:
            logger.warning(f"Error saving cookies during cleanup: {e}")

        # DO NOT close the browser in persistent mode
        # The browser stays open for the next scraping run
        logger.info(f"[{self.source_name}] Cleanup complete (browser remains open in persistent mode)")

    @abstractmethod
    def scrape(self) -> List[Dict]:
        """
        Scrape listings from source
        Must be implemented by subclass
        Returns list of listing dictionaries
        """
        pass

    @abstractmethod
    def parse_listing(self, raw_data: Dict) -> Optional[Dict]:
        """
        Parse raw listing data into standardized format
        Must be implemented by subclass
        """
        pass


class ScraperWithRetry:
    """Wrapper to add retry logic to scrapers"""

    def __init__(self, scraper: BaseScraper, max_retries: int = 3, retry_delay: int = 60):
        self.scraper = scraper
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def scrape_with_retry(self) -> List[Dict]:
        """Execute scraping with retry logic"""
        source = self.scraper.source_name
        logger.info(f"[Scraper Retry] Starting scrape with retry, source: {source}, max_retries: {self.max_retries}")
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.info(f"[Scraper Retry] Attempt {attempt + 1}/{self.max_retries}, source: {source}")

                logger.debug(f"[Scraper Retry] Initializing browser, source: {source}")
                self.scraper.initialize()

                logger.info(f"[Scraper Retry] Executing scrape, source: {source}")
                listings = self.scraper.scrape()

                logger.debug(f"[Scraper Retry] Cleaning up browser, source: {source}")
                self.scraper.cleanup()

                self.scraper.update_scraping_state(success=True)
                logger.info(f"[Scraper Retry] ✅ Scrape successful, source: {source}, listings_count: {len(listings)}")

                return listings

            except Exception as e:
                last_error = e
                logger.error(f"[Scraper Retry] ❌ Attempt {attempt + 1} failed, source: {source}, error: {e}")

                try:
                    logger.debug(f"[Scraper Retry] Attempting cleanup after error, source: {source}")
                    self.scraper.cleanup()
                except Exception as cleanup_error:
                    logger.warning(f"[Scraper Retry] Cleanup failed, source: {source}, error: {cleanup_error}")

                if attempt < self.max_retries - 1:
                    logger.info(f"[Scraper Retry] Retrying in {self.retry_delay} seconds, source: {source}")
                    time.sleep(self.retry_delay)

        # All retries failed
        error_msg = f"Failed after {self.max_retries} attempts: {last_error}"
        self.scraper.update_scraping_state(success=False, error_msg=error_msg)
        logger.error(f"[Scraper Retry] ❌ All retries exhausted, source: {source}, error: {error_msg}")

        return []
