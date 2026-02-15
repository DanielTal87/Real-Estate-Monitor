from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Database
    database_url: str = Field(default="sqlite:///./real_estate.db", env="DATABASE_URL")

    # Scraping
    scraping_interval_minutes: int = Field(default=15, env="SCRAPING_INTERVAL_MINUTES")
    yad2_interval_minutes: int = Field(default=15, env="YAD2_INTERVAL_MINUTES")
    madlan_interval_minutes: int = Field(default=15, env="MADLAN_INTERVAL_MINUTES")
    facebook_interval_minutes: int = Field(default=20, env="FACEBOOK_INTERVAL_MINUTES")

    # Telegram
    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")

    # Dashboard
    dashboard_host: str = Field(default="127.0.0.1", env="DASHBOARD_HOST")
    dashboard_port: int = Field(default=8000, env="DASHBOARD_PORT")

    # Search Filters
    cities: str = Field(default="תל אביב-יפו,רמת גן,גבעתיים", env="CITIES")
    max_price: float = Field(default=3000000, env="MAX_PRICE")  # For sale properties (₪3M)
    min_rooms: float = Field(default=2.5, env="MIN_ROOMS")
    min_size_sqm: float = Field(default=65, env="MIN_SIZE_SQM")

    # High Priority
    high_priority_neighborhoods: str = Field(default="רמת אביב,בבלי", env="HIGH_PRIORITY_NEIGHBORHOODS")

    # Deal Breakers
    exclude_ground_floor: bool = Field(default=True, env="EXCLUDE_GROUND_FLOOR")
    require_elevator_above_floor: int = Field(default=2, env="REQUIRE_ELEVATOR_ABOVE_FLOOR")
    require_parking: bool = Field(default=False, env="REQUIRE_PARKING")
    require_mamad: bool = Field(default=False, env="REQUIRE_MAMAD")

    # Preferences
    prefer_balcony: bool = Field(default=True, env="PREFER_BALCONY")
    prefer_parking: bool = Field(default=True, env="PREFER_PARKING")
    prefer_elevator: bool = Field(default=True, env="PREFER_ELEVATOR")
    prefer_top_floors: bool = Field(default=True, env="PREFER_TOP_FLOORS")
    prefer_mamad: bool = Field(default=True, env="PREFER_MAMAD")

    # Notifications
    min_deal_score_notify: float = Field(default=80, env="MIN_DEAL_SCORE_NOTIFY")
    min_price_drop_percent_notify: float = Field(default=3, env="MIN_PRICE_DROP_PERCENT_NOTIFY")

    # Facebook
    facebook_cookies_file: str = Field(default="facebook_cookies.json", env="FACEBOOK_COOKIES_FILE")

    # Persistent Browser Mode (Anti-Bot Protection)
    chrome_debug_port: int = Field(default=9222, env="CHROME_DEBUG_PORT")
    captcha_check_interval: int = Field(default=30, env="CAPTCHA_CHECK_INTERVAL")
    captcha_timeout_minutes: int = Field(default=30, env="CAPTCHA_TIMEOUT_MINUTES")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="real_estate_monitor.log", env="LOG_FILE")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_cities_list(self) -> List[str]:
        """Get cities as list"""
        return [city.strip() for city in self.cities.split(',') if city.strip()]

    def get_high_priority_neighborhoods_list(self) -> List[str]:
        """Get high priority neighborhoods as list"""
        return [n.strip() for n in self.high_priority_neighborhoods.split(',') if n.strip()]

    def is_telegram_enabled(self) -> bool:
        """Check if Telegram is configured"""
        return bool(self.telegram_bot_token and self.telegram_chat_id)


# Global settings instance
settings = Settings()
