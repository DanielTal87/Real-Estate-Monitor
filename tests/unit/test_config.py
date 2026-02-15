"""
Unit tests for Settings and configuration.
Tests configuration loading and helper methods.
"""
import pytest
from app.core.config import Settings


class TestSettings:
    """Test Settings configuration"""

    def test_default_settings(self):
        """Test that default settings are loaded"""
        settings = Settings()

        assert settings.database_url is not None
        assert settings.max_price > 0
        assert settings.min_rooms > 0
        assert settings.min_size_sqm > 0

    def test_get_cities_list(self, test_settings):
        """Test parsing cities from comma-separated string"""
        cities = test_settings.get_cities_list()

        assert isinstance(cities, list)
        assert len(cities) == 2
        assert 'Tel Aviv' in cities
        assert 'Ramat Gan' in cities

    def test_get_cities_list_empty(self):
        """Test get_cities_list with empty string"""
        settings = Settings(cities="")

        cities = settings.get_cities_list()

        assert isinstance(cities, list)
        assert len(cities) == 0

    def test_get_cities_list_with_spaces(self):
        """Test get_cities_list handles extra spaces"""
        settings = Settings(cities="  Tel Aviv  ,  Ramat Gan  ,  ")

        cities = settings.get_cities_list()

        assert len(cities) == 2
        assert 'Tel Aviv' in cities
        assert 'Ramat Gan' in cities

    def test_get_high_priority_neighborhoods_list(self):
        """Test parsing high priority neighborhoods"""
        settings = Settings(high_priority_neighborhoods="רמת אביב,בבלי,פלורנטין")

        neighborhoods = settings.get_high_priority_neighborhoods_list()

        assert isinstance(neighborhoods, list)
        assert len(neighborhoods) == 3
        assert 'רמת אביב' in neighborhoods

    def test_is_telegram_enabled_true(self):
        """Test telegram enabled check when configured"""
        settings = Settings(
            telegram_bot_token="test_token",
            telegram_chat_id="test_chat_id"
        )

        assert settings.is_telegram_enabled() is True

    def test_is_telegram_enabled_false_no_token(self):
        """Test telegram disabled when token missing"""
        settings = Settings(
            telegram_bot_token=None,
            telegram_chat_id="test_chat_id"
        )

        assert settings.is_telegram_enabled() is False

    def test_is_telegram_enabled_false_no_chat_id(self):
        """Test telegram disabled when chat ID missing"""
        settings = Settings(
            telegram_bot_token="test_token",
            telegram_chat_id=None
        )

        assert settings.is_telegram_enabled() is False

    def test_custom_settings_override(self):
        """Test that custom settings override defaults"""
        settings = Settings(
            max_price=5000000,
            min_rooms=4.0,
            min_size_sqm=100
        )

        assert settings.max_price == 5000000
        assert settings.min_rooms == 4.0
        assert settings.min_size_sqm == 100

    def test_deal_breaker_settings(self):
        """Test deal breaker configuration"""
        settings = Settings(
            exclude_ground_floor=True,
            require_elevator_above_floor=3,
            require_parking=True,
            require_mamad=True
        )

        assert settings.exclude_ground_floor is True
        assert settings.require_elevator_above_floor == 3
        assert settings.require_parking is True
        assert settings.require_mamad is True

    def test_preference_settings(self):
        """Test preference configuration"""
        settings = Settings(
            prefer_balcony=True,
            prefer_parking=True,
            prefer_elevator=True,
            prefer_top_floors=True,
            prefer_mamad=True
        )

        assert settings.prefer_balcony is True
        assert settings.prefer_parking is True
        assert settings.prefer_elevator is True
        assert settings.prefer_top_floors is True
        assert settings.prefer_mamad is True

    def test_chrome_settings(self):
        """Test Chrome browser configuration"""
        settings = Settings(
            chrome_debug_port=9223,
            chrome_user_data_dir="/custom/path",
            headless=True
        )

        assert settings.chrome_debug_port == 9223
        assert settings.chrome_user_data_dir == "/custom/path"
        assert settings.headless is True

    def test_scraping_interval_settings(self):
        """Test scraping interval configuration"""
        settings = Settings(
            scraping_interval_minutes=30,
            yad2_interval_minutes=20,
            madlan_interval_minutes=25,
            facebook_interval_minutes=40
        )

        assert settings.scraping_interval_minutes == 30
        assert settings.yad2_interval_minutes == 20
        assert settings.madlan_interval_minutes == 25
        assert settings.facebook_interval_minutes == 40

    def test_notification_settings(self):
        """Test notification threshold configuration"""
        settings = Settings(
            min_deal_score_notify=85,
            min_price_drop_percent_notify=5.0
        )

        assert settings.min_deal_score_notify == 85
        assert settings.min_price_drop_percent_notify == 5.0

    def test_captcha_settings(self):
        """Test CAPTCHA handling configuration"""
        settings = Settings(
            captcha_check_interval=45,
            captcha_timeout_minutes=20
        )

        assert settings.captcha_check_interval == 45
        assert settings.captcha_timeout_minutes == 20
