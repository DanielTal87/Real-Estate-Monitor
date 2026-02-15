"""
Pytest configuration and shared fixtures for Real Estate Monitor tests.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Dict, List

from app.core.database import Base, Listing, NeighborhoodStats
from app.core.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings with mock values"""
    return Settings(
        # Database
        database_url="sqlite:///:memory:",

        # Search criteria
        cities="Tel Aviv,Ramat Gan",
        max_price=3000000,
        min_rooms=3.0,
        min_size_sqm=70,

        # Preferences
        prefer_parking=True,
        prefer_balcony=True,
        prefer_elevator=True,
        prefer_mamad=True,
        prefer_top_floors=True,

        # Chrome settings (not used in tests)
        chrome_debug_port=9222,
        chrome_user_data_dir="~/chrome_bot_profile",

        # Scraping settings
        default_max_scrolls=3,
        min_wait_after_scroll=1.0,
        max_wait_after_scroll=2.0,

        # Notification settings
        min_price_drop_percent_notify=5.0,

        # CAPTCHA settings
        captcha_timeout_minutes=10,
        captcha_check_interval=5,

        # Telegram (optional)
        telegram_bot_token="",
        telegram_chat_id=""
    )


@pytest.fixture(scope="function")
def db_session(test_settings):
    """Create a fresh in-memory database session for each test"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def mock_chromium_page():
    """Mock DrissionPage ChromiumPage for testing scrapers without browser"""
    mock_page = MagicMock()

    # Mock basic page properties
    mock_page.title = "Test Page"
    mock_page.html = "<html><body>Test HTML</body></html>"
    mock_page.url = "https://example.com"

    # Mock navigation methods
    mock_page.get = MagicMock(return_value=True)
    mock_page.refresh = MagicMock(return_value=True)

    # Mock element finding methods
    mock_page.ele = MagicMock(return_value=None)
    mock_page.eles = MagicMock(return_value=[])

    # Mock scrolling
    mock_page.scroll = MagicMock()
    mock_page.scroll.down = MagicMock()
    mock_page.scroll.up = MagicMock()

    # Mock JavaScript execution
    mock_page.run_js = MagicMock(return_value=None)

    # Mock cookies
    mock_page.cookies = MagicMock(return_value=[])
    mock_page.set = MagicMock()
    mock_page.set.cookies = MagicMock()

    # Mock screenshot
    mock_page.get_screenshot = MagicMock(return_value=True)

    return mock_page


@pytest.fixture
def mock_listing_element():
    """Mock a single listing card element from Yad2"""
    mock_element = MagicMock()

    # Mock link element
    mock_link = MagicMock()
    mock_link.link = "/realestate/forsale/item/12345"
    mock_link.attr = MagicMock(return_value="https://www.yad2.co.il/realestate/forsale/item/12345")

    # Mock title element
    mock_title = MagicMock()
    mock_title.text = "דירת 3.5 חדרים למכירה בתל אביב"

    # Mock price element
    mock_price = MagicMock()
    mock_price.text = "2,500,000 ₪"

    # Mock location element
    mock_location = MagicMock()
    mock_location.text = "רחוב הרצל, פלורנטין, תל אביב"

    # Mock image elements
    mock_img1 = MagicMock()
    mock_img1.attr = MagicMock(return_value="https://example.com/image1.jpg")
    mock_img2 = MagicMock()
    mock_img2.attr = MagicMock(return_value="https://example.com/image2.jpg")

    # Configure element to return mocked sub-elements
    def ele_side_effect(selector, timeout=2):
        if 'a.feed_item' in selector or 'css:a.feed_item' in selector:
            return mock_link
        elif '.title' in selector:
            return mock_title
        elif '.price' in selector:
            return mock_price
        elif '.subtitle' in selector:
            return mock_location
        return None

    def eles_side_effect(selector):
        if 'tag:img' in selector:
            return [mock_img1, mock_img2]
        return []

    mock_element.ele = MagicMock(side_effect=ele_side_effect)
    mock_element.eles = MagicMock(side_effect=eles_side_effect)
    mock_element.text = "3.5 חדרים | 85 מ\"ר | קומה 3 | מעלית | חניה | מרפסת | ממ\"ד"

    return mock_element


@pytest.fixture
def sample_listing_data():
    """Sample listing data for testing"""
    return {
        'source': 'yad2',
        'external_id': '12345',
        'url': 'https://www.yad2.co.il/realestate/forsale/item/12345',
        'title': 'דירת 3.5 חדרים למכירה בתל אביב',
        'description': '3.5 חדרים | 85 מ"ר | קומה 3 | מעלית | חניה | מרפסת | ממ"ד',
        'address': 'רחוב הרצל, פלורנטין, תל אביב',
        'city': 'תל אביב',
        'neighborhood': 'פלורנטין',
        'street': 'רחוב הרצל',
        'rooms': 3.5,
        'size_sqm': 85.0,
        'floor': 3,
        'total_floors': 5,
        'price': 2500000,
        'price_per_sqm': 29411.76,
        'has_elevator': True,
        'has_parking': True,
        'has_balcony': True,
        'has_mamad': True,
        'contact_name': 'Test Contact',
        'contact_phone': '0501234567',
        'images': ['https://example.com/image1.jpg', 'https://example.com/image2.jpg']
    }


@pytest.fixture
def sample_listing(db_session, sample_listing_data):
    """Create a sample listing in the database"""
    listing = Listing(
        property_hash=Listing.generate_property_hash(
            sample_listing_data['address'],
            sample_listing_data['rooms'],
            sample_listing_data['size_sqm']
        ),
        source=sample_listing_data['source'],
        external_id=sample_listing_data['external_id'],
        url=sample_listing_data['url'],
        title=sample_listing_data['title'],
        description=sample_listing_data['description'],
        address=sample_listing_data['address'],
        city=sample_listing_data['city'],
        neighborhood=sample_listing_data['neighborhood'],
        street=sample_listing_data['street'],
        rooms=sample_listing_data['rooms'],
        size_sqm=sample_listing_data['size_sqm'],
        floor=sample_listing_data['floor'],
        total_floors=sample_listing_data['total_floors'],
        price=sample_listing_data['price'],
        price_per_sqm=sample_listing_data['price_per_sqm'],
        has_elevator=sample_listing_data['has_elevator'],
        has_parking=sample_listing_data['has_parking'],
        has_balcony=sample_listing_data['has_balcony'],
        has_mamad=sample_listing_data['has_mamad'],
        contact_name=sample_listing_data['contact_name'],
        contact_phone=sample_listing_data['contact_phone'],
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        last_checked=datetime.utcnow(),
        status='unseen',
        deal_score=0.0
    )

    if sample_listing_data.get('images'):
        listing.set_images(sample_listing_data['images'])

    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)

    return listing


@pytest.fixture
def sample_neighborhood_stats(db_session):
    """Create sample neighborhood statistics"""
    stats = NeighborhoodStats(
        city='תל אביב',
        neighborhood='פלורנטין',
        avg_price=2800000,
        avg_price_per_sqm=32000,
        median_price=2750000,
        median_price_per_sqm=31500,
        sample_size=25,
        last_updated=datetime.utcnow()
    )

    db_session.add(stats)
    db_session.commit()
    db_session.refresh(stats)

    return stats


@pytest.fixture
def mock_browser_env(monkeypatch):
    """Mock environment variable to disable browser in tests"""
    monkeypatch.setenv("MOCK_BROWSER", "true")
    return True


@pytest.fixture
def hebrew_test_strings():
    """Sample Hebrew strings for parser testing"""
    return {
        'rooms': [
            ('3 חדרים', 3.0),
            ('3.5 חדרים', 3.5),
            ('4.5 חד\'', 4.5),
            ('2 rooms', 2.0),
        ],
        'size': [
            ('85 מ"ר', 85.0),
            ('120 מ״ר', 120.0),
            ('95 sqm', 95.0),
            ('110 m2', 110.0),
        ],
        'floor': [
            ('קומה 3', 3),
            ('קומה ג\'', 3),
            ('floor 5', 5),
            ('קומת קרקע', 0),
        ],
        'price': [
            ('2,500,000 ₪', 2500000),
            ('3,200,000', 3200000),
            ('1,850,000 שקלים', 1850000),
        ],
        'phone': [
            ('050-123-4567', '0501234567'),
            ('052 987 6543', '0529876543'),
            ('03-1234567', '031234567'),
            ('+972-50-1234567', '0501234567'),
        ]
    }


# Patch ChromiumPage globally for all tests
@pytest.fixture(autouse=True)
def mock_chromium_page_class(mock_chromium_page):
    """Automatically mock ChromiumPage for all tests"""
    with patch('app.scrapers.base_scraper.ChromiumPage', return_value=mock_chromium_page):
        yield mock_chromium_page
