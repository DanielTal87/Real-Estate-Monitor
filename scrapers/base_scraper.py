from abc import ABC, abstractmethod
from playwright.async_api import async_playwright, Browser, Page
from typing import List, Dict, Optional
import asyncio
import random
import logging
from datetime import datetime
from database import Listing, ScrapingState
from sqlalchemy.orm import Session
import json

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers with common functionality"""

    def __init__(self, db_session: Session, source_name: str):
        self.db = db_session
        self.source_name = source_name
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def initialize(self):
        """Initialize browser and page"""
        playwright = await async_playwright().start()

        self.browser = await playwright.webkit.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )

        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        self.page = await context.new_page()

        # Load cookies if available
        await self._load_cookies()

    async def _load_cookies(self):
        """Load saved cookies for this source"""
        state = self.db.query(ScrapingState).filter(
            ScrapingState.source == self.source_name
        ).first()

        if state and state.cookies_json:
            try:
                cookies = json.loads(state.cookies_json)
                if cookies and self.page:
                    await self.page.context.add_cookies(cookies)
                    logger.info(f"Loaded cookies for {self.source_name}")
            except Exception as e:
                logger.warning(f"Failed to load cookies for {self.source_name}: {e}")

    async def _save_cookies(self):
        """Save current cookies"""
        if not self.page:
            return

        try:
            cookies = await self.page.context.cookies()

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

    async def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add random delay to appear human-like"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def scroll_page(self, scrolls: int = 3):
        """Scroll page to load dynamic content"""
        if not self.page:
            return

        for _ in range(scrolls):
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await self.random_delay(0.5, 1.5)

    async def safe_click(self, selector: str, timeout: int = 5000):
        """Safely click element with error handling"""
        if not self.page:
            return False

        try:
            await self.page.click(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.debug(f"Could not click {selector}: {e}")
            return False

    async def safe_fill(self, selector: str, value: str, timeout: int = 5000):
        """Safely fill input with error handling"""
        if not self.page:
            return False

        try:
            await self.page.fill(selector, value, timeout=timeout)
            return True
        except Exception as e:
            logger.debug(f"Could not fill {selector}: {e}")
            return False

    async def safe_get_text(self, selector: str, timeout: int = 5000) -> Optional[str]:
        """Safely get text content"""
        if not self.page:
            return None

        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                return await element.text_content()
        except Exception as e:
            logger.debug(f"Could not get text from {selector}: {e}")
        return None

    def normalize_phone(self, phone: str) -> str:
        """Normalize phone number for matching"""
        if not phone:
            return ""

        # Remove all non-digit characters
        digits = ''.join(c for c in phone if c.isdigit())

        # Handle Israeli phone numbers
        if digits.startswith('972'):
            digits = '0' + digits[3:]
        elif digits.startswith('+972'):
            digits = '0' + digits[4:]

        return digits

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

    async def cleanup(self):
        """Clean up browser resources"""
        try:
            await self._save_cookies()
        except Exception as e:
            logger.warning(f"Error saving cookies during cleanup: {e}")

        if self.browser:
            await self.browser.close()

    @abstractmethod
    async def scrape(self) -> List[Dict]:
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

    async def scrape_with_retry(self) -> List[Dict]:
        """Execute scraping with retry logic"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Scraping {self.scraper.source_name} (attempt {attempt + 1}/{self.max_retries})")

                await self.scraper.initialize()
                listings = await self.scraper.scrape()
                await self.scraper.cleanup()

                self.scraper.update_scraping_state(success=True)
                logger.info(f"Successfully scraped {len(listings)} listings from {self.scraper.source_name}")

                return listings

            except Exception as e:
                last_error = e
                logger.error(f"Error scraping {self.scraper.source_name} (attempt {attempt + 1}): {e}")

                try:
                    await self.scraper.cleanup()
                except:
                    pass

                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)

        # All retries failed
        error_msg = f"Failed after {self.max_retries} attempts: {last_error}"
        self.scraper.update_scraping_state(success=False, error_msg=error_msg)
        logger.error(f"Giving up on {self.scraper.source_name}: {error_msg}")

        return []
