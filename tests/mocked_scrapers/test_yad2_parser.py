"""
Mocked tests for Yad2 scraper HTML parsing logic.
Tests scraper without real browser using mocked DrissionPage elements.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.scrapers.yad2_scraper import Yad2Scraper


class TestYad2ScraperMocked:
    """Test Yad2 scraper with mocked browser"""

    def test_scraper_initialization(self, db_session, mock_chromium_page):
        """Test that scraper can be initialized without real browser"""
        with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
            scraper = Yad2Scraper(db_session)
            scraper.initialize()

            assert scraper.page is not None
            assert scraper.source_name == 'yad2'

    def test_build_search_url(self, db_session):
        """Test search URL construction"""
        scraper = Yad2Scraper(db_session)
        url = scraper.build_search_url()

        assert 'yad2.co.il' in url
        assert 'realestate/forsale' in url
        assert 'price=' in url
        assert 'rooms=' in url

    def test_extract_listing_data_from_card(self, db_session, mock_listing_element):
        """Test extracting data from a mocked listing card"""
        scraper = Yad2Scraper(db_session)

        listing_data = scraper._extract_listing_data(mock_listing_element)

        assert listing_data is not None
        assert listing_data['external_id'] == '12345'
        assert listing_data['url'] == 'https://www.yad2.co.il/realestate/forsale/item/12345'
        assert 'דירת 3.5 חדרים' in listing_data['title']
        assert listing_data['price'] == 2500000
        assert listing_data['rooms'] == 3.5
        assert listing_data['size_sqm'] == 85.0
        assert listing_data['floor'] == 3
        assert listing_data['city'] == 'תל אביב'
        assert listing_data['neighborhood'] == 'פלורנטין'
        assert len(listing_data['images']) == 2

    def test_extract_listing_data_missing_elements(self, db_session):
        """Test extraction when elements are missing"""
        scraper = Yad2Scraper(db_session)

        # Create mock element with missing data
        mock_card = MagicMock()
        mock_card.ele = MagicMock(return_value=None)
        mock_card.eles = MagicMock(return_value=[])
        mock_card.text = ''

        listing_data = scraper._extract_listing_data(mock_card)

        # Should return None when link is missing
        assert listing_data is None

    def test_scrape_with_mocked_page(self, db_session, mock_chromium_page, mock_listing_element):
        """Test full scrape flow with mocked page"""
        # Configure mock page to return listing cards
        mock_chromium_page.eles = MagicMock(return_value=[mock_listing_element])

        with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
            scraper = Yad2Scraper(db_session)
            scraper.initialize()

            listings = scraper.scrape()

            assert len(listings) > 0
            assert listings[0]['source'] == 'yad2'
            assert listings[0]['price'] > 0

    def test_scrape_no_listings_found(self, db_session, mock_chromium_page):
        """Test scrape when no listings are found"""
        # Configure mock page to return empty list
        mock_chromium_page.eles = MagicMock(return_value=[])

        with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
            scraper = Yad2Scraper(db_session)
            scraper.initialize()

            listings = scraper.scrape()

            assert len(listings) == 0

    def test_scrape_handles_parsing_errors(self, db_session, mock_chromium_page):
        """Test that scraper handles parsing errors gracefully"""
        # Create mock element that raises exception
        mock_bad_element = MagicMock()
        mock_bad_element.ele = MagicMock(side_effect=Exception("Parse error"))

        mock_chromium_page.eles = MagicMock(return_value=[mock_bad_element])

        with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
            scraper = Yad2Scraper(db_session)
            scraper.initialize()

            # Should not raise exception, just return empty list
            listings = scraper.scrape()

            assert isinstance(listings, list)

    def test_parse_listing_calculates_price_per_sqm(self, db_session):
        """Test that parse_listing calculates price per sqm"""
        scraper = Yad2Scraper(db_session)

        raw_data = {
            'external_id': '12345',
            'url': 'https://example.com',
            'title': 'Test',
            'price': 2500000,
            'size_sqm': 100.0,
            'details_text': ''
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed['price_per_sqm'] == 25000.0

    def test_parse_listing_handles_missing_price_per_sqm(self, db_session):
        """Test that parse_listing handles missing size"""
        scraper = Yad2Scraper(db_session)

        raw_data = {
            'external_id': '12345',
            'url': 'https://example.com',
            'title': 'Test',
            'price': 2500000,
            'size_sqm': None,
            'details_text': ''
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed['price_per_sqm'] is None

    def test_parse_listing_detects_features(self, db_session):
        """Test that parse_listing detects features from text"""
        scraper = Yad2Scraper(db_session)

        raw_data = {
            'external_id': '12345',
            'url': 'https://example.com',
            'title': 'Test',
            'details_text': 'דירה עם מעלית, חניה, מרפסת וממ"ד'
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed['has_elevator'] is True
        assert parsed['has_parking'] is True
        assert parsed['has_balcony'] is True
        assert parsed['has_mamad'] is True

    def test_parse_listing_no_features(self, db_session):
        """Test that parse_listing handles no features"""
        scraper = Yad2Scraper(db_session)

        raw_data = {
            'external_id': '12345',
            'url': 'https://example.com',
            'title': 'Test',
            'details_text': 'דירה יפה'
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed['has_elevator'] is False
        assert parsed['has_parking'] is False
        assert parsed['has_balcony'] is False
        assert parsed['has_mamad'] is False


class TestYad2ScraperHelpers:
    """Test Yad2 scraper helper methods"""

    def test_extract_number_with_commas(self, db_session):
        """Test number extraction with comma separators"""
        scraper = Yad2Scraper(db_session)

        result = scraper._extract_number('2,500,000')
        assert result == 2500000.0

    def test_extract_number_with_currency(self, db_session):
        """Test number extraction with currency symbols"""
        scraper = Yad2Scraper(db_session)

        result = scraper._extract_number('2,500,000 ₪')
        assert result == 2500000.0

    def test_extract_number_empty_string(self, db_session):
        """Test number extraction with empty string"""
        scraper = Yad2Scraper(db_session)

        result = scraper._extract_number('')
        assert result is None

    def test_extract_rooms_various_formats(self, db_session):
        """Test room extraction with various Hebrew formats"""
        scraper = Yad2Scraper(db_session)

        test_cases = [
            ('3 חדרים', 3.0),
            ('3.5 חדרים', 3.5),
            ('4.5 חד\'', 4.5),
            ('דירת 2 חדרים', 2.0),
        ]

        for text, expected in test_cases:
            result = scraper._extract_rooms(text)
            assert result == expected, f"Failed for '{text}'"

    def test_extract_size_various_formats(self, db_session):
        """Test size extraction with various formats"""
        scraper = Yad2Scraper(db_session)

        test_cases = [
            ('85 מ"ר', 85.0),
            ('120 מ״ר', 120.0),
            ('95 sqm', 95.0),
        ]

        for text, expected in test_cases:
            result = scraper._extract_size(text)
            assert result == expected, f"Failed for '{text}'"

    def test_extract_floor_hebrew(self, db_session):
        """Test floor extraction from Hebrew text"""
        scraper = Yad2Scraper(db_session)

        result = scraper._extract_floor('קומה 3')
        assert result == 3

    def test_parse_location_full_address(self, db_session):
        """Test location parsing with full address"""
        scraper = Yad2Scraper(db_session)

        city, neighborhood, street = scraper._parse_location('רחוב הרצל, פלורנטין, תל אביב')

        assert city == 'תל אביב'
        assert neighborhood == 'פלורנטין'
        assert street == 'רחוב הרצל'

    def test_parse_location_partial_address(self, db_session):
        """Test location parsing with partial address"""
        scraper = Yad2Scraper(db_session)

        city, neighborhood, street = scraper._parse_location('פלורנטין, תל אביב')

        assert city == 'תל אביב'
        assert neighborhood == 'פלורנטין'
        assert street == 'פלורנטין'

    def test_parse_location_empty(self, db_session):
        """Test location parsing with empty string"""
        scraper = Yad2Scraper(db_session)

        city, neighborhood, street = scraper._parse_location('')

        assert city is None
        assert neighborhood is None
        assert street is None


class TestYad2ScraperIntegration:
    """Integration tests for Yad2 scraper with mocks"""

    def test_full_scrape_and_parse_flow(self, db_session, mock_chromium_page, mock_listing_element):
        """Test complete flow from scraping to parsing"""
        # Setup mock to return one listing
        mock_chromium_page.eles = MagicMock(return_value=[mock_listing_element])

        with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
            scraper = Yad2Scraper(db_session)
            scraper.initialize()

            # Scrape
            listings = scraper.scrape()

            # Verify results
            assert len(listings) == 1
            listing = listings[0]

            assert listing['source'] == 'yad2'
            assert listing['external_id'] == '12345'
            assert listing['price'] > 0
            assert listing['rooms'] > 0
            assert listing['size_sqm'] > 0
            assert 'has_elevator' in listing
            assert 'has_parking' in listing
            assert 'has_balcony' in listing
            assert 'has_mamad' in listing

    def test_scraper_cleanup_without_browser(self, db_session, mock_chromium_page):
        """Test that cleanup works without real browser"""
        with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
            scraper = Yad2Scraper(db_session)
            scraper.initialize()

            # Should not raise exception
            scraper.cleanup()

            assert True  # If we got here, cleanup succeeded
