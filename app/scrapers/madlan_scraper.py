from app.scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)


class MadlanScraper(BaseScraper):
    """Scraper for Madlan.co.il real estate listings"""

    def __init__(self, db_session):
        super().__init__(db_session, 'madlan')
        self.base_url = "https://www.madlan.co.il"

    def scrape(self) -> List[Dict]:
        """Scrape Madlan listings"""
        if not self.page:
            logger.error("[Madlan Scraper] Browser page not initialized")
            return []

        listings = []

        try:
            # Navigate to Madlan for-sale page
            search_url = f"{self.base_url}/for-sale"
            logger.info(f"[Madlan Scraper] Navigating to search page, url: {search_url}")

            # Navigate to the page
            self.page.get(search_url)
            logger.info("[Madlan Scraper] Page loaded successfully")

            # Wait for page to settle
            self.random_delay(2, 3)

            # Longer initial delay to let anti-bot scripts run
            self.random_delay(3, 6)
            logger.debug("[Madlan Scraper] Initial delay completed")

            # Simulate human-like mouse movements
            self.human_like_mouse_movement()
            logger.debug("[Madlan Scraper] Mouse movements simulated")

            # Scroll to load more results with human-like behavior
            logger.info("[Madlan Scraper] Scrolling page to load dynamic content, scrolls: 3")
            self.scroll_page(scrolls=3)
            self.random_delay(2, 4)

            # Get listing cards - Madlan uses different selectors
            logger.info("[Madlan Scraper] Attempting to find listing cards with selector: css:[data-testid=\"listing-card\"]")
            listing_cards = self.page.eles('css:[data-testid="listing-card"]')

            if not listing_cards:
                logger.info("[Madlan Scraper] Primary selector failed, trying alternative: .listing-card")
                listing_cards = self.page.eles('.listing-card')

            if not listing_cards:
                logger.info("[Madlan Scraper] Second selector failed, trying: css:[class*=\"listing\"]")
                listing_cards = self.page.eles('css:[class*="listing"]')

            if not listing_cards:
                logger.info("[Madlan Scraper] Third selector failed, trying: css:[class*=\"card\"]")
                listing_cards = self.page.eles('css:[class*="card"]')

            if not listing_cards:
                logger.info("[Madlan Scraper] Fourth selector failed, trying generic: tag:article")
                listing_cards = self.page.eles('tag:article')

            logger.info(f"[Madlan Scraper] Found listing cards, count: {len(listing_cards)}")

            # Debug: Save page if no listings found
            if len(listing_cards) == 0:
                logger.warning("[Madlan Scraper] No listing cards found - saving debug output")
                self.debug_save_page("no_listings")

            # Process only first 30 newest listings per scrape
            max_listings = min(len(listing_cards), 30)
            logger.info(f"[Madlan Scraper] Processing listings, max_count: {max_listings}")

            for idx, card in enumerate(listing_cards[:30], 1):
                try:
                    logger.debug(f"[Madlan Scraper] Extracting listing data, index: {idx}/{max_listings}")
                    listing_data = self._extract_listing_data(card)
                    if listing_data:
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            listings.append(parsed)
                            logger.debug(f"[Madlan Scraper] Successfully parsed listing, title: {parsed.get('title', 'N/A')[:50]}")
                        else:
                            logger.debug(f"[Madlan Scraper] Failed to parse listing data, index: {idx}")
                    else:
                        logger.debug(f"[Madlan Scraper] Failed to extract listing data, index: {idx}")
                except Exception as e:
                    logger.warning(f"[Madlan Scraper] Error extracting listing, index: {idx}, error: {e}")
                    continue

            logger.info(f"[Madlan Scraper] Scraping completed, total_listings: {len(listings)}")

        except Exception as e:
            logger.error(f"[Madlan Scraper] Fatal error during scraping, error: {e}")
            raise

        return listings

    def _extract_listing_data(self, card) -> Optional[Dict]:
        """Extract data from a single listing card"""
        try:
            # Extract link and ID
            link_element = card.ele('tag:a', timeout=2)
            if not link_element:
                return None

            href = link_element.link
            if not href:
                return None

            full_url = self.base_url + href if href.startswith('/') else href

            # Extract ID from URL
            id_match = re.search(r'/(\d+)/?$', href)
            external_id = id_match.group(1) if id_match else None

            # Extract all text content
            card_text = card.text

            # Extract title (usually the first line or prominent text)
            title_element = card.ele('tag:h2', timeout=2)
            if not title_element:
                title_element = card.ele('tag:h3', timeout=2)
            if not title_element:
                title_element = card.ele('.title', timeout=2)
            if not title_element:
                title_element = card.ele('css:[class*="title"]', timeout=2)
            title = title_element.text if title_element else ""

            # Extract price
            price_element = card.ele('css:[class*="price"]', timeout=2)
            price_text = price_element.text if price_element else ""
            price = self._extract_number(price_text)

            # Extract details
            rooms = self._extract_rooms(card_text)
            size_sqm = self._extract_size(card_text)
            floor = self._extract_floor(card_text)

            # Extract location
            location_element = card.ele('css:[class*="location"]', timeout=2)
            if not location_element:
                location_element = card.ele('css:[class*="address"]', timeout=2)
            location_text = location_element.text if location_element else ""

            if not location_text:
                # Try to find location in card text
                location_text = self._extract_location_from_text(card_text)

            city, neighborhood, street = self._parse_location(location_text)

            # Extract images
            images = []
            img_elements = card.eles('tag:img')
            for img in img_elements[:5]:
                src = img.attr('src')
                if src and ('http' in src or src.startswith('//')):
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)

            return {
                'external_id': external_id,
                'url': full_url,
                'title': title.strip(),
                'price': price,
                'rooms': rooms,
                'size_sqm': size_sqm,
                'floor': floor,
                'city': city,
                'neighborhood': neighborhood,
                'street': street,
                'location_text': location_text,
                'details_text': card_text,
                'contact_name': '',
                'contact_phone': '',
                'images': images
            }

        except Exception as e:
            logger.debug(f"Error extracting Madlan listing data: {e}")
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
                'source': 'madlan',
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
            logger.warning(f"Error parsing Madlan listing: {e}")
            return None

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract number from text"""
        if not text:
            return None

        numbers = re.findall(r'[\d,]+', text.replace(',', ''))
        if numbers:
            try:
                return float(numbers[0])
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

    def _extract_floor(self, text: str) -> Optional[int]:
        """Extract floor number"""
        match = re.search(r'(?:קומה|floor)\s*(\d+)', text)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None

    def _extract_location_from_text(self, text: str) -> str:
        """Try to extract location from general text"""
        # Look for common Israeli city names
        cities = ['תל אביב', 'רמת גן', 'גבעתיים', 'הרצליה', 'רמת השרון', 'פתח תקווה']
        for city in cities:
            if city in text:
                # Try to find surrounding context
                idx = text.find(city)
                # Get ~50 chars before and after
                start = max(0, idx - 50)
                end = min(len(text), idx + len(city) + 50)
                return text[start:end].strip()
        return ""

    def _parse_location(self, location_text: str) -> tuple:
        """Parse location into city, neighborhood, street"""
        if not location_text:
            return None, None, None

        parts = [p.strip() for p in location_text.split(',')]

        city = parts[-1] if len(parts) > 0 else None
        neighborhood = parts[-2] if len(parts) > 1 else None
        street = parts[0] if len(parts) > 0 else None

        return city, neighborhood, street
