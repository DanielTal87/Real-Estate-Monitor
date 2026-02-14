from scrapers.base_scraper import BaseScraper
from typing import List, Dict, Optional
import logging
import re
import json
import os

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    """Scraper for Facebook Marketplace and Groups"""

    def __init__(self, db_session, cookies_file: str = None):
        super().__init__(db_session, 'facebook')
        self.base_url = "https://www.facebook.com"
        self.cookies_file = cookies_file

    async def _load_cookies(self):
        """Load Facebook cookies from file"""
        if not self.cookies_file or not os.path.exists(self.cookies_file):
            logger.warning("Facebook cookies file not found. Facebook scraping may not work.")
            return

        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            if cookies and self.page:
                await self.page.context.add_cookies(cookies)
                logger.info("Loaded Facebook cookies from file")
        except Exception as e:
            logger.warning(f"Failed to load Facebook cookies: {e}")

    async def scrape(self) -> List[Dict]:
        """Scrape Facebook Marketplace listings"""
        if not self.page:
            return []

        listings = []

        try:
            # Navigate to Facebook Marketplace - search for apartments in Tel Aviv area
            # This URL needs to be customized based on your search criteria
            search_url = f"{self.base_url}/marketplace/telaviv/search?query=דירה%20להשכרה&exact=false"

            logger.info(f"Navigating to: {search_url}")

            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
            await self.random_delay(3, 5)

            # Check if login is required
            current_url = self.page.url
            if 'login' in current_url.lower():
                logger.warning("Facebook requires login. Please provide valid cookies.")
                return []

            # Scroll to load more results
            await self.scroll_page(scrolls=4)
            await self.random_delay(2, 3)

            # Get listing cards
            # Facebook's DOM structure changes frequently, these selectors may need updates
            listing_cards = await self.page.query_selector_all('[data-testid="marketplace-feed-item"]')

            if not listing_cards:
                # Try alternative selectors
                listing_cards = await self.page.query_selector_all('div[role="article"]')

            logger.info(f"Found {len(listing_cards)} listing cards on Facebook")

            # Process listings
            for card in listing_cards[:30]:
                try:
                    listing_data = await self._extract_listing_data(card)
                    if listing_data:
                        parsed = self.parse_listing(listing_data)
                        if parsed:
                            listings.append(parsed)
                except Exception as e:
                    logger.warning(f"Error extracting Facebook listing: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping Facebook: {e}")
            raise

        return listings

    async def _extract_listing_data(self, card) -> Optional[Dict]:
        """Extract data from a single Facebook listing card"""
        try:
            # Extract link
            link_element = await card.query_selector('a')
            if not link_element:
                return None

            href = await link_element.get_attribute('href')
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
            card_text = await card.text_content()

            # Extract title
            title = ""
            title_selectors = ['span[class*="title"]', 'h2', 'h3']
            for selector in title_selectors:
                title_element = await card.query_selector(selector)
                if title_element:
                    title = await title_element.text_content()
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
            img_elements = await card.query_selector_all('img')
            for img in img_elements[:5]:
                src = await img.get_attribute('src')
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
