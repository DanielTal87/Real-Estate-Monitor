from app.scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
import logging
import re
import json
import os

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    """Scraper for Facebook Marketplace and Groups"""

    def __init__(self, db_session, cookies_file: Optional[str] = None):
        super().__init__(db_session, 'facebook')
        self.base_url = "https://www.facebook.com"
        self.cookies_file = cookies_file

    def _load_cookies(self):
        """Load Facebook cookies from file"""
        if not self.cookies_file or not os.path.exists(self.cookies_file):
            logger.warning("Facebook cookies file not found. Facebook scraping may not work.")
            return

        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            if cookies and self.page:
                for cookie in cookies:
                    # Convert cookie format if needed
                    if 'sameSite' in cookie:
                        cookie['sameSite'] = cookie['sameSite'].capitalize()
                    self.page.set.cookies(cookie)
                logger.info("Loaded Facebook cookies from file")
        except Exception as e:
            logger.warning(f"Failed to load Facebook cookies: {e}")

    def scrape(self) -> List[Dict]:
        """Scrape Facebook Marketplace listings"""
        if not self.page:
            logger.error("[Facebook Scraper] Browser page not initialized")
            return []

        listings = []

        try:
            # Navigate to Facebook Marketplace - search for apartments in Tel Aviv area
            search_url = f"{self.base_url}/marketplace/telaviv/search?query=דירה%20להשכרה&exact=false"
            logger.info(f"[Facebook Scraper] Navigating to search page, url: {search_url}")

            # Navigate to the page
            self.page.get(search_url)
            logger.info("[Facebook Scraper] Page loaded successfully")

            # Wait for page to settle
            self.random_delay(2, 3)

            # Longer initial delay to let anti-bot scripts run
            self.random_delay(4, 7)
            logger.debug("[Facebook Scraper] Initial delay completed")

            # Check if login is required
            current_url = self.page.url
            logger.debug(f"[Facebook Scraper] Checking current URL, url: {current_url}")

            if 'login' in current_url.lower():
                logger.warning("[Facebook Scraper] Login required - cookies missing or expired")
                return []

            # Simulate human-like mouse movements
            self.human_like_mouse_movement()
            logger.debug("[Facebook Scraper] Mouse movements simulated")

            # Scroll to load more results with human-like behavior
            logger.info("[Facebook Scraper] Scrolling page to load dynamic content, scrolls: 4")
            self.scroll_page(scrolls=4)
            self.random_delay(2, 4)

            # Get listing cards
            logger.info("[Facebook Scraper] Attempting to find listing cards with selector: css:[data-testid=\"marketplace-feed-item\"]")
            listing_cards = self.page.eles('css:[data-testid="marketplace-feed-item"]')

            if not listing_cards:
                logger.info("[Facebook Scraper] Primary selector failed, trying alternative: css:div[role=\"article\"]")
                listing_cards = self.page.eles('css:div[role="article"]')

            if not listing_cards:
                logger.info("[Facebook Scraper] Second selector failed, trying: css:[class*=\"marketplace\"]")
                listing_cards = self.page.eles('css:[class*="marketplace"]')

            if not listing_cards:
                logger.info("[Facebook Scraper] Third selector failed, trying generic: css:div[class*=\"feed\"] > div")
                listing_cards = self.page.eles('css:div[class*="feed"] > div')
                if not listing_cards:
                    listing_cards = self.page.eles('css:div[class*="item"]')

            logger.info(f"[Facebook Scraper] Found listing cards, count: {len(listing_cards)}")

            # Debug: Save page if no listings found
            if len(listing_cards) == 0:
                logger.warning("[Facebook Scraper] No listing cards found - saving debug output")
                self.debug_save_page("no_listings")

            # Process listings
            max_listings = min(len(listing_cards), 30)
            logger.info(f"[Facebook Scraper] Processing listings, max_count: {max_listings}")

            for idx, card in enumerate(listing_cards[:30], 1):
                try:
                    logger.debug(f"[Facebook Scraper] Extracting listing data, index: {idx}/{max_listings}")
                    listing_data = self._extract_listing_data(card)
                    if listing_data:
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            listings.append(parsed)
                            logger.debug(f"[Facebook Scraper] Successfully parsed listing, title: {parsed.get('title', 'N/A')[:50]}")
                        else:
                            logger.debug(f"[Facebook Scraper] Failed to parse listing data, index: {idx}")
                    else:
                        logger.debug(f"[Facebook Scraper] Failed to extract listing data, index: {idx}")
                except Exception as e:
                    logger.warning(f"[Facebook Scraper] Error extracting listing, index: {idx}, error: {e}")
                    continue

            logger.info(f"[Facebook Scraper] Scraping completed, total_listings: {len(listings)}")

        except Exception as e:
            logger.error(f"[Facebook Scraper] Fatal error during scraping, error: {e}")
            raise

        return listings

    def _extract_listing_data(self, card) -> Optional[Dict]:
        """Extract data from a single Facebook listing card"""
        try:
            # Extract link
            link_element = card.ele('tag:a', timeout=2)
            if not link_element:
                return None

            href = link_element.link
            if not href:
                return None

            # Facebook URLs can be complex, extract clean URL
            if '/marketplace/item/' in href:
                id_match = re.search(r'/marketplace/item/(\d+)', href)
                external_id = id_match.group(1) if id_match else None
                full_url = f"{self.base_url}/marketplace/item/{external_id}" if external_id else href
            else:
                external_id = None
                full_url = href

            # Extract all text content
            card_text = card.text

            # Extract title
            title = ""
            title_selectors = ['css:span[class*="title"]', 'tag:h2', 'tag:h3']
            for selector in title_selectors:
                title_element = card.ele(selector, timeout=2)
                if title_element:
                    title = title_element.text
                    break

            # Extract price
            price = self._extract_price_from_text(card_text)

            # Extract details
            rooms = self._extract_rooms(card_text)
            size_sqm = self._extract_size(card_text)

            # Location (often in description or title)
            city, neighborhood, street = self._extract_location_from_text(card_text)

            # Extract images
            images = []
            img_elements = card.eles('tag:img')
            for img in img_elements[:5]:
                src = img.attr('src')
                if src and 'http' in src:
                    images.append(src)

            return {
                'external_id': external_id,
                'url': full_url,
                'title': title.strip(),
                'price': price,
                'rooms': rooms,
                'size_sqm': size_sqm,
                'floor': None,
                'city': city,
                'neighborhood': neighborhood,
                'street': street,
                'location_text': '',
                'details_text': card_text,
                'contact_name': '',
                'contact_phone': '',
                'images': images
            }

        except Exception as e:
            logger.debug(f"Error extracting Facebook listing data: {e}")
            return None

    def parse_listing(self, raw_data: Dict) -> Optional[Dict]:
        """Parse raw listing data into standardized format"""
        try:
            # Calculate price per sqm
            price_per_sqm = None
            if raw_data.get('price') and raw_data.get('size_sqm') and raw_data['size_sqm'] > 0:
                price_per_sqm = raw_data['price'] / raw_data['size_sqm']

            # Detect features from text
            details_lower = raw_data.get('details_text', '').lower()

            has_elevator = any(word in details_lower for word in ['מעלית', 'elevator'])
            has_parking = any(word in details_lower for word in ['חניה', 'parking', 'חנייה'])
            has_balcony = any(word in details_lower for word in ['מרפסת', 'balcony', 'mirpeset'])
            has_mamad = any(word in details_lower for word in ['ממ"ד', 'ממד', 'mamad', 'מרחב מוגן', 'מקלט'])


            return {
                'source': 'facebook',
                'external_id': raw_data.get('external_id'),
                'url': raw_data.get('url'),
                'title': raw_data.get('title'),
                'description': raw_data.get('details_text', ''),
                'address': f"{raw_data.get('street', '')}, {raw_data.get('neighborhood', '')}, {raw_data.get('city', '')}".strip(', '),
                'city': raw_data.get('city'),
                'neighborhood': raw_data.get('neighborhood'),
                'street': raw_data.get('street'),
                'rooms': raw_data.get('rooms'),
                'size_sqm': raw_data.get('size_sqm'),
                'floor': raw_data.get('floor'),
                'price': raw_data.get('price'),
                'price_per_sqm': price_per_sqm,
                'has_elevator': has_elevator,
                'has_parking': has_parking,
                'has_balcony': has_balcony,
                'has_mamad': has_mamad,
                'contact_name': raw_data.get('contact_name'),
                'contact_phone': raw_data.get('contact_phone'),
                'images': raw_data.get('images', [])
            }

        except Exception as e:
            logger.warning(f"Error parsing Facebook listing: {e}")
            return None

    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract price from text"""
        # Look for patterns like "₪5,000" or "5000 ₪" or "5,000 shekels"
        patterns = [
            r'₪\s*([\d,]+)',
            r'([\d,]+)\s*₪',
            r'([\d,]+)\s*(?:ש"ח|שקל)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    return float(price_str)
                except:
                    pass
        return None

    def _extract_rooms(self, text: str) -> Optional[float]:
        """Extract number of rooms"""
        match = re.search(r'(\d+\.?\d*)\s*(?:חדרים|חד\'|rooms)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_size(self, text: str) -> Optional[float]:
        """Extract size in sqm"""
        match = re.search(r'(\d+)\s*(?:מ"ר|מ״ר|sqm|m2)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_location_from_text(self, text: str) -> tuple:
        """Extract location information from text"""
        # Common Israeli cities
        cities = [
            'תל אביב', 'תל אביב-יפו', 'רמת גן', 'גבעתיים',
            'הרצליה', 'רמת השרון', 'פתח תקווה', 'ראשון לציון'
        ]

        city = None
        neighborhood = None
        street = None

        # Find city
        for c in cities:
            if c in text:
                city = c
                break

        # Common neighborhoods in Tel Aviv (example)
        neighborhoods = [
            'רמת אביב', 'בבלי', 'יד אליהו', 'נווה אביבים',
            'פלורנטין', 'נווה צדק', 'רמת החייל'
        ]

        for n in neighborhoods:
            if n in text:
                neighborhood = n
                break

        return city, neighborhood, street
