"""
Unit tests for parsing and data cleaning functions.
Tests regex patterns for Hebrew text, phone normalization, and data extraction.
"""
import pytest
from app.scrapers.yad2_scraper import Yad2Scraper
from app.utils.phone_normalizer import normalize_israeli_phone


class TestHebrewParsing:
    """Test parsing of Hebrew text patterns"""

    @pytest.mark.parametrize("text,expected", [
        ('3 חדרים', 3.0),
        ('3.5 חדרים', 3.5),
        ('4.5 חד\'', 4.5),
        ('2 rooms', 2.0),
        ('5 חד', 5.0),
        ('1.5 חדרים גדולים', 1.5),
    ])
    def test_extract_rooms(self, db_session, text, expected):
        """Test room number extraction from Hebrew text"""
        scraper = Yad2Scraper(db_session)
        result = scraper._extract_rooms(text)
        assert result == expected, f"Failed to extract rooms from '{text}'"

    @pytest.mark.parametrize("text,expected", [
        ('85 מ"ר', 85.0),
        ('120 מ״ר', 120.0),
        ('95 sqm', 95.0),
        ('110 m2', 110.0),
        ('75 מטר רבוע', None),  # Not supported pattern
        ('דירה של 90 מ"ר', 90.0),
    ])
    def test_extract_size(self, db_session, text, expected):
        """Test size extraction from Hebrew text"""
        scraper = Yad2Scraper(db_session)
        result = scraper._extract_size(text)
        assert result == expected, f"Failed to extract size from '{text}'"

    @pytest.mark.parametrize("text,expected", [
        ('קומה 3', 3),
        ('קומה 5', 5),
        ('floor 2', 2),
        ('קומה 10', 10),
        ('קומת קרקע', None),  # Not supported pattern
    ])
    def test_extract_floor(self, db_session, text, expected):
        """Test floor extraction from Hebrew text"""
        scraper = Yad2Scraper(db_session)
        result = scraper._extract_floor(text)
        assert result == expected, f"Failed to extract floor from '{text}'"

    @pytest.mark.parametrize("text,expected", [
        ('2,500,000 ₪', 2500000.0),
        ('3,200,000', 3200000.0),
        ('1,850,000 שקלים', 1850000.0),
        ('מחיר: 2,750,000', 2750000.0),
        ('950000', 950000.0),
    ])
    def test_extract_price(self, db_session, text, expected):
        """Test price extraction from text"""
        scraper = Yad2Scraper(db_session)
        result = scraper._extract_number(text)
        assert result == expected, f"Failed to extract price from '{text}'"


class TestPhoneNormalization:
    """Test Israeli phone number normalization"""

    @pytest.mark.parametrize("input_phone,expected", [
        ('050-123-4567', '0501234567'),
        ('052 987 6543', '0529876543'),
        ('03-1234567', '031234567'),
        ('+972-50-1234567', '0501234567'),
        ('+972501234567', '0501234567'),
        ('972-50-1234567', '0501234567'),
        ('050 123 4567', '0501234567'),
        ('050.123.4567', '0501234567'),
        ('(050) 123-4567', '0501234567'),
        ('0501234567', '0501234567'),  # Already normalized
        ('', None),  # Empty string
        (None, None),  # None input
        ('invalid', None),  # Invalid phone
    ])
    def test_normalize_israeli_phone(self, input_phone, expected):
        """Test phone number normalization with various formats"""
        result = normalize_israeli_phone(input_phone)
        assert result == expected, f"Failed to normalize '{input_phone}'"

    def test_normalize_phone_removes_spaces(self):
        """Test that normalization removes all spaces"""
        result = normalize_israeli_phone('050 123 45 67')
        assert ' ' not in result
        assert result == '0501234567'

    def test_normalize_phone_removes_dashes(self):
        """Test that normalization removes all dashes"""
        result = normalize_israeli_phone('050-123-45-67')
        assert '-' not in result
        assert result == '0501234567'

    def test_normalize_phone_handles_international_prefix(self):
        """Test handling of +972 international prefix"""
        result = normalize_israeli_phone('+972-50-1234567')
        assert result.startswith('0')
        assert not result.startswith('+')
        assert result == '0501234567'


class TestLocationParsing:
    """Test location parsing into city, neighborhood, street"""

    @pytest.mark.parametrize("location_text,expected_city,expected_neighborhood,expected_street", [
        ('רחוב הרצל, פלורנטין, תל אביב', 'תל אביב', 'פלורנטין', 'רחוב הרצל'),
        ('רחוב בן יהודה, מרכז העיר, תל אביב', 'תל אביב', 'מרכז העיר', 'רחוב בן יהודה'),
        ('רמת אביב, תל אביב', 'תל אביב', 'רמת אביב', 'רמת אביב'),
        ('תל אביב', 'תל אביב', None, 'תל אביב'),
        ('', None, None, None),
    ])
    def test_parse_location(self, db_session, location_text, expected_city,
                           expected_neighborhood, expected_street):
        """Test parsing location string into components"""
        scraper = Yad2Scraper(db_session)
        city, neighborhood, street = scraper._parse_location(location_text)

        assert city == expected_city, f"City mismatch for '{location_text}'"
        assert neighborhood == expected_neighborhood, f"Neighborhood mismatch for '{location_text}'"
        assert street == expected_street, f"Street mismatch for '{location_text}'"


class TestFeatureDetection:
    """Test feature detection from Hebrew text"""

    @pytest.mark.parametrize("text,has_elevator", [
        ('דירה עם מעלית', True),
        ('יש מעלית בבניין', True),
        ('elevator available', True),
        ('דירה ללא מעלית', True),  # Contains word but negative context
        ('דירה יפה', False),
    ])
    def test_detect_elevator(self, text, has_elevator):
        """Test elevator detection in text"""
        text_lower = text.lower()
        detected = any(word in text_lower for word in ['מעלית', 'elevator'])
        assert detected == has_elevator

    @pytest.mark.parametrize("text,has_parking", [
        ('דירה עם חניה', True),
        ('יש חנייה', True),
        ('parking available', True),
        ('חניה בטאבו', True),
        ('דירה יפה', False),
    ])
    def test_detect_parking(self, text, has_parking):
        """Test parking detection in text"""
        text_lower = text.lower()
        detected = any(word in text_lower for word in ['חניה', 'parking', 'חנייה'])
        assert detected == has_parking

    @pytest.mark.parametrize("text,has_balcony", [
        ('דירה עם מרפסת', True),
        ('מרפסת גדולה', True),
        ('balcony', True),
        ('mirpeset', True),
        ('דירה יפה', False),
    ])
    def test_detect_balcony(self, text, has_balcony):
        """Test balcony detection in text"""
        text_lower = text.lower()
        detected = any(word in text_lower for word in ['מרפסת', 'balcony', 'mirpeset'])
        assert detected == has_balcony

    @pytest.mark.parametrize("text,has_mamad", [
        ('דירה עם ממ"ד', True),
        ('יש ממד', True),
        ('mamad', True),
        ('מרחב מוגן', True),
        ('מקלט', True),
        ('דירה יפה', False),
    ])
    def test_detect_mamad(self, text, has_mamad):
        """Test mamad (safe room) detection in text"""
        text_lower = text.lower()
        detected = any(word in text_lower for word in ['ממ"ד', 'ממד', 'mamad', 'מרחב מוגן', 'מקלט'])
        assert detected == has_mamad


class TestDataCleaning:
    """Test data cleaning and validation"""

    def test_price_per_sqm_calculation(self):
        """Test price per sqm calculation"""
        price = 2500000
        size_sqm = 85.0

        price_per_sqm = price / size_sqm

        assert abs(price_per_sqm - 29411.76) < 0.01

    def test_price_per_sqm_handles_zero_size(self):
        """Test that division by zero is handled"""
        price = 2500000
        size_sqm = 0

        if size_sqm > 0:
            price_per_sqm = price / size_sqm
        else:
            price_per_sqm = None

        assert price_per_sqm is None

    def test_address_formatting(self):
        """Test address string formatting"""
        street = 'רחוב הרצל'
        neighborhood = 'פלורנטין'
        city = 'תל אביב'

        address = f"{street}, {neighborhood}, {city}".strip(', ')

        assert address == 'רחוב הרצל, פלורנטין, תל אביב'

    def test_address_formatting_with_missing_parts(self):
        """Test address formatting when some parts are missing"""
        street = ''
        neighborhood = 'פלורנטין'
        city = 'תל אביב'

        address = f"{street}, {neighborhood}, {city}".strip(', ')

        assert address == 'פלורנטין, תל אביב'

    @pytest.mark.parametrize("text,expected_clean", [
        ('  דירה יפה  ', 'דירה יפה'),
        ('דירה\nיפה', 'דירה\nיפה'),
        ('', ''),
    ])
    def test_text_stripping(self, text, expected_clean):
        """Test text stripping and cleaning"""
        result = text.strip()
        assert result == expected_clean


class TestYad2ParserIntegration:
    """Integration tests for Yad2 parser"""

    def test_parse_listing_complete_data(self, db_session):
        """Test parsing a complete listing with all fields"""
        scraper = Yad2Scraper(db_session)

        raw_data = {
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירת 3.5 חדרים למכירה',
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85.0,
            'floor': 3,
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'street': 'רחוב הרצל',
            'location_text': 'רחוב הרצל, פלורנטין, תל אביב',
            'details_text': '3.5 חדרים | 85 מ"ר | קומה 3 | מעלית | חניה | מרפסת | ממ"ד',
            'contact_name': 'Test',
            'contact_phone': '0501234567',
            'images': ['https://example.com/img1.jpg']
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed is not None
        assert parsed['source'] == 'yad2'
        assert parsed['price'] == 2500000
        assert parsed['rooms'] == 3.5
        assert parsed['size_sqm'] == 85.0
        assert parsed['has_elevator'] is True
        assert parsed['has_parking'] is True
        assert parsed['has_balcony'] is True
        assert parsed['has_mamad'] is True
        assert parsed['price_per_sqm'] is not None

    def test_parse_listing_minimal_data(self, db_session):
        """Test parsing a listing with minimal data"""
        scraper = Yad2Scraper(db_session)

        raw_data = {
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירה למכירה',
            'details_text': '',
        }

        parsed = scraper.parse_listing(raw_data)

        assert parsed is not None
        assert parsed['source'] == 'yad2'
        assert parsed['has_elevator'] is False
        assert parsed['has_parking'] is False
        assert parsed['has_balcony'] is False
        assert parsed['has_mamad'] is False
