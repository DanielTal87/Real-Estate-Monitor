"""
Unit tests for Facebook scraper
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from app.scrapers.facebook_scraper import FacebookScraper


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    return Mock()


@pytest.fixture
def mock_page():
    """Create mock ChromiumPage"""
    page = Mock()
    page.url = "https://www.facebook.com/marketplace"
    page.html = "<html>Test</html>"
    return page


@pytest.fixture
def scraper(mock_db_session):
    """Create FacebookScraper instance"""
    return FacebookScraper(mock_db_session, cookies_file="test_cookies.json")


class TestFacebookScraper:
    """Test FacebookScraper class"""

    def test_init(self, mock_db_session):
        """Test scraper initialization"""
        scraper = FacebookScraper(mock_db_session, cookies_file="test.json")

        assert scraper.source_name == "facebook"
        assert scraper.base_url == "https://www.facebook.com"
        assert scraper.cookies_file == "test.json"

    def test_load_cookies_file_exists(self, scraper, mock_page):
        """Test loading cookies from file"""
        scraper.page = mock_page

        cookies_data = '[{"name": "test", "value": "value"}]'

        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = cookies_data

                scraper._load_cookies()

                mock_page.set.cookies.assert_called()

    def test_load_cookies_file_not_exists(self, scraper):
        """Test loading cookies when file doesn't exist"""
        scraper.page = Mock()

        with patch('os.path.exists', return_value=False):
            # Should not raise error
            scraper._load_cookies()

    def test_load_cookies_no_file(self, mock_db_session):
        """Test loading cookies with no file specified"""
        scraper = FacebookScraper(mock_db_session, cookies_file=None)
        scraper.page = Mock()

        # Should not raise error
        scraper._load_cookies()

    def test_extract_price_from_text(self, scraper):
        """Test extracting price from text"""
        text = "Great apartment for ₪5,000 per month"
        price = scraper._extract_price_from_text(text)

        assert price == 5000.0

    def test_extract_price_from_text_no_price(self, scraper):
        """Test extracting price when none found"""
        text = "Great apartment"
        price = scraper._extract_price_from_text(text)

        assert price is None

    def test_extract_rooms(self, scraper):
        """Test extracting number of rooms"""
        text = "3 חדרים apartment"
        rooms = scraper._extract_rooms(text)

        assert rooms == 3.0

    def test_extract_rooms_decimal(self, scraper):
        """Test extracting decimal rooms"""
        text = "3.5 rooms available"
        rooms = scraper._extract_rooms(text)

        assert rooms == 3.5

    def test_extract_rooms_no_rooms(self, scraper):
        """Test extracting rooms when none found"""
        text = "Great apartment"
        rooms = scraper._extract_rooms(text)

        assert rooms is None

    def test_extract_size(self, scraper):
        """Test extracting size"""
        text = "Apartment 80 מ״ר"
        size = scraper._extract_size(text)

        assert size == 80.0

    def test_extract_size_no_size(self, scraper):
        """Test extracting size when none found"""
        text = "Great apartment"
        size = scraper._extract_size(text)

        assert size is None

    def test_extract_location_from_text(self, scraper):
        """Test extracting location"""
        text = "Apartment in תל אביב, רמת אביב"
        city, neighborhood, street = scraper._extract_location_from_text(text)

        assert city == "תל אביב"
        assert neighborhood == "רמת אביב"

    def test_extract_location_no_location(self, scraper):
        """Test extracting location when none found"""
        text = "Great apartment"
        city, neighborhood, street = scraper._extract_location_from_text(text)

        assert city is None
        assert neighborhood is None
        assert street is None

    def test_extract_listing_data_success(self, scraper):
        """Test extracting listing data from card"""
        mock_card = Mock()
        mock_card.text = "3 חדרים, 80 מ״ר, ₪5,000, תל אביב"

        mock_link = Mock()
        mock_link.link = "https://www.facebook.com/marketplace/item/123456"
        mock_card.ele.return_value = mock_link

        mock_title = Mock()
        mock_title.text = "Test Apartment"

        def ele_side_effect(selector, timeout=2):
            if 'title' in selector or selector == 'tag:h2':
                return mock_title
            if selector == 'tag:a':
                return mock_link
            return None

        mock_card.ele = Mock(side_effect=ele_side_effect)
        mock_card.eles.return_value = []

        data = scraper._extract_listing_data(mock_card)

        assert data is not None
        assert data['external_id'] == '123456'
        assert data['title'] == "Test Apartment"
        assert data['price'] == 5000.0
        assert data['rooms'] == 3.0
        assert data['size_sqm'] == 80.0

    def test_extract_listing_data_no_link(self, scraper):
        """Test extracting data with no link"""
        mock_card = Mock()
        mock_card.ele.return_value = None

        data = scraper._extract_listing_data(mock_card)

        assert data is None

    def test_parse_listing_success(self, scraper):
        """Test parsing listing data"""
        raw_data = {
            'external_id': '123456',
            'url': 'https://example.com',
            'title': 'Test Apartment',
            'price': 5000,
            'rooms': 3,
            'size_sqm': 80,
            'floor': 2,
            'city': 'Tel Aviv',
            'neighborhood': 'Center',
            'street': 'Main St',
            'details_text': 'Great apartment with מעלית and חניה',
            'contact_name': 'John',
            'contact_phone': '0501234567',
            'images': ['img1.jpg']
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed is not None
        assert parsed['source'] == 'facebook'
        assert parsed['title'] == 'Test Apartment'
        assert parsed['price'] == 5000
        assert parsed['has_elevator'] is True
        assert parsed['has_parking'] is True
        assert parsed['price_per_sqm'] == 5000 / 80

    def test_parse_listing_with_features(self, scraper):
        """Test parsing listing with features"""
        raw_data = {
            'external_id': '123',
            'url': 'https://example.com',
            'title': 'Test',
            'price': 5000,
            'size_sqm': 50,
            'details_text': 'מעלית, חניה, מרפסת, ממ"ד',
            'city': 'Tel Aviv',
            'neighborhood': 'Center',
            'street': 'Main St',
            'contact_name': '',
            'contact_phone': '',
            'images': []
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed['has_elevator'] is True
        assert parsed['has_parking'] is True
        assert parsed['has_balcony'] is True
        assert parsed['has_mamad'] is True

    def test_parse_listing_no_features(self, scraper):
        """Test parsing listing without features"""
        raw_data = {
            'external_id': '123',
            'url': 'https://example.com',
            'title': 'Test',
            'price': 5000,
            'size_sqm': 50,
            'details_text': 'Simple apartment',
            'city': 'Tel Aviv',
            'neighborhood': 'Center',
            'street': 'Main St',
            'contact_name': '',
            'contact_phone': '',
            'images': []
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed['has_elevator'] is False
        assert parsed['has_parking'] is False
        assert parsed['has_balcony'] is False
        assert parsed['has_mamad'] is False

    def test_parse_listing_error(self, scraper):
        """Test parsing with error"""
        raw_data = None

        parsed = scraper.parse_listing(raw_data)

        assert parsed is None

    @patch('app.scrapers.facebook_scraper.BaseScraper.initialize')
    def test_scrape_no_page(self, mock_init, scraper):
        """Test scraping with no page"""
        scraper.page = None

        result = scraper.scrape()

        assert result == []

    @patch('app.scrapers.facebook_scraper.BaseScraper.initialize')
    def test_scrape_login_required(self, mock_init, scraper, mock_page):
        """Test scraping when login is required"""
        scraper.page = mock_page
        mock_page.url = "https://www.facebook.com/login"

        with patch.object(scraper, '_handle_anti_bot_protection'):
            with patch.object(scraper, 'human_like_mouse_movement'):
                with patch.object(scraper, 'scroll_page'):
                    with patch.object(scraper, 'random_delay'):
                        result = scraper.scrape()

                        assert result == []

    @patch('app.scrapers.facebook_scraper.BaseScraper.initialize')
    def test_scrape_success(self, mock_init, scraper, mock_page):
        """Test successful scraping"""
        scraper.page = mock_page

        # Mock listing cards
        mock_card = Mock()
        mock_card.text = "3 חדרים, 80 מ״ר, ₪5,000"

        mock_link = Mock()
        mock_link.link = "https://www.facebook.com/marketplace/item/123456"

        def ele_side_effect(selector, timeout=2):
            if selector == 'tag:a':
                return mock_link
            if 'title' in selector or selector == 'tag:h2':
                mock_title = Mock()
                mock_title.text = "Test Apartment"
                return mock_title
            return None

        mock_card.ele = Mock(side_effect=ele_side_effect)
        mock_card.eles.return_value = []

        mock_page.eles.return_value = [mock_card]

        with patch.object(scraper, '_handle_anti_bot_protection'):
            with patch.object(scraper, 'human_like_mouse_movement'):
                with patch.object(scraper, 'scroll_page'):
                    with patch.object(scraper, 'random_delay'):
                        result = scraper.scrape()

                        assert len(result) > 0

    @patch('app.scrapers.facebook_scraper.BaseScraper.initialize')
    def test_scrape_no_listings(self, mock_init, scraper, mock_page):
        """Test scraping with no listings found"""
        scraper.page = mock_page
        mock_page.eles.return_value = []

        with patch.object(scraper, '_handle_anti_bot_protection'):
            with patch.object(scraper, 'human_like_mouse_movement'):
                with patch.object(scraper, 'scroll_page'):
                    with patch.object(scraper, 'random_delay'):
                        with patch.object(scraper, 'debug_save_page'):
                            result = scraper.scrape()

                            assert result == []

    @patch('app.scrapers.facebook_scraper.BaseScraper.initialize')
    def test_scrape_error(self, mock_init, scraper, mock_page):
        """Test scraping with error"""
        scraper.page = mock_page
        mock_page.get.side_effect = Exception("Test error")

        with pytest.raises(Exception):
            scraper.scrape()
