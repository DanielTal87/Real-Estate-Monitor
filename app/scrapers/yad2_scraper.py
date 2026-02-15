from app.scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
import logging
import re
from app.core.config import settings

logger = logging.getLogger(__name__)


class Yad2Scraper(BaseScraper):
    """Scraper for Yad2.co.il real estate listings"""

    def __init__(self, db_session):
        super().__init__(db_session, 'yad2')
        self.base_url = "https://www.yad2.co.il"

    def build_search_url(self) -> str:
        """Build Yad2 search URL with filters"""
        cities = settings.get_cities_list()

        # Yad2 uses specific city codes - this is simplified
        # In production, you'd need to map city names to Yad2 city IDs
        params = {
            'price': f'-{int(settings.max_price)}',
            'rooms': f'{settings.min_rooms}-',
            'Order': '1'  # Sort by newest
        }

        # Build URL
        url = f"{self.base_url}/realestate/forsale?"
        url += "&".join([f"{k}={v}" for k, v in params.items()])

        return url

    def scrape(self) -> List[Dict]:
        """Scrape Yad2 listings"""
        if not self.page:
            logger.error("[Yad2 Scraper] Browser page not initialized")
            return []

        listings = []

        try:
            # Navigate to search results
            search_url = self.build_search_url()
            logger.info(f"[Yad2 Scraper] Navigating to search page, url: {search_url}")

            # Navigate to the page
            self.page.get(search_url)
            logger.info("[Yad2 Scraper] Page loaded successfully")

            # Wait for page to settle
            self.random_delay(2, 3)

            # Check for anti-bot protection (CAPTCHA, etc.)
            self._handle_anti_bot_protection()

            # Longer initial delay to let anti-bot scripts run
            self.random_delay(3, 6)
            logger.debug("[Yad2 Scraper] Initial delay completed")

            # Simulate human-like mouse movements
            self.human_like_mouse_movement()
            logger.debug("[Yad2 Scraper] Mouse movements simulated")

            # Scroll to load more results with human-like behavior
            logger.info("[Yad2 Scraper] Scrolling page to load dynamic content, scrolls: 3")
            self.scroll_page(scrolls=3)
            self.random_delay(2, 4)

            # Get listing cards - try multiple selectors as Yad2 changes frequently
            logger.info("[Yad2 Scraper] Attempting to find listing cards with selector: .feeditem")
            listing_cards = self.page.eles('.feeditem')

            if not listing_cards:
                logger.info("[Yad2 Scraper] Primary selector failed, trying alternative: css:[class*=\"feed_item\"]")
                listing_cards = self.page.eles('css:[class*="feed_item"]')

            if not listing_cards:
                logger.info("[Yad2 Scraper] Second selector failed, trying: css:[data-testid*=\"item\"]")
                listing_cards = self.page.eles('css:[data-testid*="item"]')

            if not listing_cards:
                logger.info("[Yad2 Scraper] Third selector failed, trying generic: article, css:div[class*=\"item\"]")
                listing_cards = self.page.eles('tag:article')
                if not listing_cards:
                    listing_cards = self.page.eles('css:div[class*="item"]')

            logger.info(f"[Yad2 Scraper] Found listing cards, count: {len(listing_cards)}")

            # Debug: Save page if no listings found
            if len(listing_cards) == 0:
                logger.warning("[Yad2 Scraper] No listing cards found - saving debug output")
                self.debug_save_page("no_listings")

            # Process only first 20-30 newest listings per scrape
            max_listings = min(len(listing_cards), 30)
            logger.info(f"[Yad2 Scraper] Processing listings, max_count: {max_listings}")

            for idx, card in enumerate(listing_cards[:30], 1):
                try:
                    logger.debug(f"[Yad2 Scraper] Extracting listing data, index: {idx}/{max_listings}")
                    listing_data = self._extract_listing_data(card)
                    if listing_data:
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            listings.append(parsed)
                            logger.debug(f"[Yad2 Scraper] Successfully parsed listing, title: {parsed.get('title', 'N/A')[:50]}")
                        else:
                            logger.debug(f"[Yad2 Scraper] Failed to parse listing data, index: {idx}")
                    else:
                        logger.debug(f"[Yad2 Scraper] Failed to extract listing data, index: {idx}")
                except Exception as e:
                    logger.warning(f"[Yad2 Scraper] Error extracting listing, index: {idx}, error: {e}")
                    continue

            logger.info(f"[Yad2 Scraper] Scraping completed, total_listings: {len(listings)}")

        except Exception as e:
            logger.error(f"[Yad2 Scraper] Fatal error during scraping, error: {e}")
            raise

        return listings

    def _extract_listing_data(self, card) -> Optional[Dict]:
        """Extract data from a single listing card"""
        try:
            # Extract link and ID
            link_element = card.ele('css:a.feed_item', timeout=2)
            if not link_element:
                return None

            href = link_element.link
            if not href:
                return None

            full_url = self.base_url + href if href.startswith('/') else href

            # Extract ID from URL
            id_match = re.search(r'/item/(\d+)', href)
            external_id = id_match.group(1) if id_match else None

            # Extract title
            title_element = card.ele('.title', timeout=2)
            title = title_element.text if title_element else ""

            # Extract price
            price_element = card.ele('.price', timeout=2)
            price_text = price_element.text if price_element else ""
            price = self._extract_number(price_text)

            # Extract details
            details_text = card.text

            # Extract rooms
            rooms = self._extract_rooms(details_text)

            # Extract size
            size_sqm = self._extract_size(details_text)

            # Extract floor
            floor = self._extract_floor(details_text)

            # Extract address/location
            location_element = card.ele('.subtitle', timeout=2)
            location_text = location_element.text if location_element else ""

            city, neighborhood, street = self._parse_location(location_text)

            # Extract contact
            contact_name = ""
            contact_phone = ""

            # Extract images
            images = []
            img_elements = card.eles('tag:img')
            for img in img_elements[:5]:  # Max 5 images
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
                'floor': floor,
                'city': city,
                'neighborhood': neighborhood,
                'street': street,
                'location_text': location_text,
                'details_text': details_text,
                'contact_name': contact_name,
                'contact_phone': contact_phone,
                'images': images
            }

        except Exception as e:
            logger.debug(f"Error extracting Yad2 listing data: {e}")
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
                'source': 'yad2',
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
            logger.warning(f"Error parsing Yad2 listing: {e}")
            return None

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract number from text"""
        if not text:
            return None

        # Remove commas and extract numbers
        numbers = re.findall(r'[\d,]+', text.replace(',', ''))
        if numbers:
            try:
                return float(numbers[0])
            except:
                pass
        return None

    def _extract_rooms(self, text: str) -> Optional[float]:
        """Extract number of rooms"""
        # Look for patterns like "3 חדרים", "3.5 חד'", or "5 חד"
        match = re.search(r'(\d+\.?\d*)\s*(?:חדרים|חד\'|חד|rooms)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_size(self, text: str) -> Optional[float]:
        """Extract size in sqm"""
        # Look for patterns like "80 מ\"ר" or "80 sqm"
        match = re.search(r'(\d+)\s*(?:מ"ר|מ״ר|sqm|m2)', text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _extract_floor(self, text: str) -> Optional[int]:
        """Extract floor number"""
        # Look for patterns like "קומה 3" or "floor 3"
        match = re.search(r'(?:קומה|floor)\s*(\d+)', text)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None

    def _parse_location(self, location_text: str) -> tuple:
        """Parse location into city, neighborhood, street"""
        if not location_text:
            return None, None, None

        # Location usually in format: "Street, Neighborhood, City"
        parts = [p.strip() for p in location_text.split(',')]

        city = parts[-1] if len(parts) > 0 else None
        neighborhood = parts[-2] if len(parts) > 1 else None
        street = parts[0] if len(parts) > 0 else None

        return city, neighborhood, street
