"""
Unit tests for base scraper
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.scrapers.base_scraper import (
    BaseScraper,
    ScraperWithRetry,
    CaptchaState,
    captcha_state
)
from app.core.database import ScrapingState


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    return Mock()


@pytest.fixture
def mock_page():
    """Create mock ChromiumPage"""
    page = Mock()
    page.title = "Test Page"
    page.html = "<html>Test</html>"
    page.url = "https://example.com"
    page.cookies = Mock(return_value=[])
    return page


class ConcreteScraper(BaseScraper):
    """Concrete implementation for testing"""

    def scrape(self):
        return [{"title": "Test"}]

    def parse_listing(self, raw_data):
        return raw_data


class TestCaptchaState:
    """Test CaptchaState singleton"""

    def test_singleton(self):
        """Test that CaptchaState is a singleton"""
        state1 = CaptchaState()
        state2 = CaptchaState()
        assert state1 is state2

    def test_set_waiting(self):
        """Test setting waiting state"""
        state = CaptchaState()
        state.set_waiting("test_source")

        assert state.is_waiting() is True
        assert state._source == "test_source"
        assert state._waiting_since is not None

    def test_set_normal(self):
        """Test resetting to normal state"""
        state = CaptchaState()
        state.set_waiting("test_source")
        state.set_normal()

        assert state.is_waiting() is False
        assert state._source is None
        assert state._waiting_since is None

    def test_get_status(self):
        """Test getting status"""
        state = CaptchaState()
        state.set_normal()

        status = state.get_status()

        assert status["status"] == "NORMAL"
        assert status["waiting_since"] is None
        assert status["source"] is None

    def test_get_status_waiting(self):
        """Test getting status when waiting"""
        state = CaptchaState()
        state.set_waiting("test_source")

        status = state.get_status()

        assert status["status"] == "WAITING_FOR_CAPTCHA"
        assert status["source"] == "test_source"
        assert status["waiting_since"] is not None

    def test_is_timeout_false(self):
        """Test timeout check when not timed out"""
        state = CaptchaState()
        state.set_waiting("test_source")

        assert state.is_timeout() is False

    def test_is_timeout_true(self):
        """Test timeout check when timed out"""
        state = CaptchaState()
        state.set_waiting("test_source")
        # Manually set old timestamp
        state._waiting_since = datetime.utcnow() - timedelta(minutes=100)

        with patch('app.scrapers.base_scraper.settings') as mock_settings:
            mock_settings.captcha_timeout_minutes = 30
            assert state.is_timeout() is True


class TestBaseScraper:
    """Test BaseScraper class"""

    def test_init(self, mock_db_session):
        """Test scraper initialization"""
        scraper = ConcreteScraper(mock_db_session, "test_source")

        assert scraper.db == mock_db_session
        assert scraper.source_name == "test_source"
        assert scraper.page is None

    @patch('app.scrapers.base_scraper.ChromiumPage')
    def test_initialize_success(self, mock_chromium_page, mock_db_session):
        """Test successful browser initialization"""
        mock_page = Mock()
        mock_chromium_page.return_value = mock_page

        scraper = ConcreteScraper(mock_db_session, "test_source")

        with patch.object(scraper, '_inject_anti_detection_scripts'):
            with patch.object(scraper, '_load_cookies'):
                scraper.initialize()

                assert scraper.page is not None

    @patch('app.scrapers.base_scraper.ChromiumPage')
    def test_initialize_connection_error(self, mock_chromium_page, mock_db_session):
        """Test initialization with connection error"""
        mock_chromium_page.side_effect = ConnectionError("Connection failed")

        scraper = ConcreteScraper(mock_db_session, "test_source")

        with pytest.raises(ConnectionError):
            scraper.initialize()

    def test_inject_anti_detection_scripts(self, mock_db_session, mock_page):
        """Test injecting anti-detection scripts"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        scraper._inject_anti_detection_scripts()

        # Should call run_js multiple times
        assert mock_page.run_js.call_count > 0

    def test_inject_anti_detection_scripts_no_page(self, mock_db_session):
        """Test injecting scripts with no page"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = None

        # Should not raise error
        scraper._inject_anti_detection_scripts()

    def test_load_cookies(self, mock_db_session, mock_page):
        """Test loading cookies"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_state = Mock(spec=ScrapingState)
        mock_state.cookies_json = '[{"name": "test", "value": "value"}]'

        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_state

        scraper._load_cookies()

        mock_page.set.cookies.assert_called()

    def test_save_cookies(self, mock_db_session, mock_page):
        """Test saving cookies"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_page.cookies.return_value = [{"name": "test", "value": "value"}]

        mock_state = Mock(spec=ScrapingState)
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_state

        scraper._save_cookies()

        mock_db_session.commit.assert_called_once()

    def test_random_delay(self, mock_db_session):
        """Test random delay"""
        scraper = ConcreteScraper(mock_db_session, "test_source")

        with patch('time.sleep') as mock_sleep:
            scraper.random_delay(0.1, 0.2)
            mock_sleep.assert_called_once()

    def test_scroll_page(self, mock_db_session, mock_page):
        """Test scrolling page"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        with patch('time.sleep'):
            with patch('random.randint', return_value=500):
                with patch('random.random', return_value=0.5):
                    scraper.scroll_page(scrolls=2)

                    assert mock_page.scroll.down.call_count == 2

    def test_safe_click_success(self, mock_db_session, mock_page):
        """Test safe click success"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_element = Mock()
        mock_page.ele.return_value = mock_element

        result = scraper.safe_click("test_selector")

        assert result is True
        mock_element.click.assert_called_once()

    def test_safe_click_failure(self, mock_db_session, mock_page):
        """Test safe click failure"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_page.ele.return_value = None

        result = scraper.safe_click("test_selector")

        assert result is False

    def test_safe_fill_success(self, mock_db_session, mock_page):
        """Test safe fill success"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_element = Mock()
        mock_page.ele.return_value = mock_element

        result = scraper.safe_fill("test_selector", "test_value")

        assert result is True
        mock_element.input.assert_called_once_with("test_value")

    def test_safe_get_text_success(self, mock_db_session, mock_page):
        """Test safe get text success"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_element = Mock()
        mock_element.text = "Test text"
        mock_page.ele.return_value = mock_element

        result = scraper.safe_get_text("test_selector")

        assert result == "Test text"

    def test_normalize_phone(self, mock_db_session):
        """Test phone normalization"""
        scraper = ConcreteScraper(mock_db_session, "test_source")

        result = scraper.normalize_phone("050-123-4567")

        assert result is not None

    def test_update_scraping_state_success(self, mock_db_session):
        """Test updating scraping state on success"""
        scraper = ConcreteScraper(mock_db_session, "test_source")

        mock_state = Mock(spec=ScrapingState)
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_state

        scraper.update_scraping_state(success=True)

        assert mock_state.status == 'active'
        assert mock_state.error_count == 0
        mock_db_session.commit.assert_called_once()

    def test_update_scraping_state_failure(self, mock_db_session):
        """Test updating scraping state on failure"""
        scraper = ConcreteScraper(mock_db_session, "test_source")

        mock_state = Mock(spec=ScrapingState)
        mock_state.error_count = 0
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_state

        scraper.update_scraping_state(success=False, error_msg="Test error")

        assert mock_state.status == 'error'
        assert mock_state.error_count == 1
        assert mock_state.error_message == "Test error"

    def test_check_for_captcha_detected(self, mock_db_session, mock_page):
        """Test CAPTCHA detection"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_page.title = "CAPTCHA Required"
        mock_page.html = "<html>captcha</html>"

        result = scraper._check_for_captcha()

        assert result is True

    def test_check_for_captcha_not_detected(self, mock_db_session, mock_page):
        """Test no CAPTCHA detection"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_page.title = "Normal Page"
        mock_page.html = "<html>normal content</html>"

        result = scraper._check_for_captcha()

        assert result is False

    def test_is_blocked(self, mock_db_session, mock_page):
        """Test is_blocked method"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        scraper.page = mock_page

        mock_page.title = "Blocked"
        mock_page.html = "<html>access denied</html>"

        result = scraper._is_blocked()

        assert result is True

    def test_cleanup(self, mock_db_session):
        """Test cleanup"""
        scraper = ConcreteScraper(mock_db_session, "test_source")

        with patch.object(scraper, '_save_cookies'):
            scraper.cleanup()
            # Should complete without errors


class TestScraperWithRetry:
    """Test ScraperWithRetry wrapper"""

    def test_init(self, mock_db_session):
        """Test initialization"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        retry_scraper = ScraperWithRetry(scraper, max_retries=3, retry_delay=1)

        assert retry_scraper.scraper == scraper
        assert retry_scraper.max_retries == 3
        assert retry_scraper.retry_delay == 1

    def test_scrape_with_retry_success(self, mock_db_session):
        """Test successful scrape on first attempt"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        retry_scraper = ScraperWithRetry(scraper, max_retries=3, retry_delay=1)

        with patch.object(scraper, 'initialize'):
            with patch.object(scraper, 'scrape', return_value=[{"title": "Test"}]):
                with patch.object(scraper, 'cleanup'):
                    with patch.object(scraper, 'update_scraping_state'):
                        result = retry_scraper.scrape_with_retry()

                        assert len(result) == 1
                        assert result[0]["title"] == "Test"

    def test_scrape_with_retry_failure_then_success(self, mock_db_session):
        """Test scrape fails then succeeds"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        retry_scraper = ScraperWithRetry(scraper, max_retries=3, retry_delay=1)

        call_count = [0]

        def scrape_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First attempt failed")
            return [{"title": "Test"}]

        with patch.object(scraper, 'initialize'):
            with patch.object(scraper, 'scrape', side_effect=scrape_side_effect):
                with patch.object(scraper, 'cleanup'):
                    with patch.object(scraper, 'update_scraping_state'):
                        with patch('time.sleep'):
                            result = retry_scraper.scrape_with_retry()

                            assert len(result) == 1

    def test_scrape_with_retry_all_failures(self, mock_db_session):
        """Test all retry attempts fail"""
        scraper = ConcreteScraper(mock_db_session, "test_source")
        retry_scraper = ScraperWithRetry(scraper, max_retries=2, retry_delay=1)

        with patch.object(scraper, 'initialize'):
            with patch.object(scraper, 'scrape', side_effect=Exception("Failed")):
                with patch.object(scraper, 'cleanup'):
                    with patch.object(scraper, 'update_scraping_state'):
                        with patch('time.sleep'):
                            result = retry_scraper.scrape_with_retry()

                            assert result == []

    def test_scrape_with_retry_shutdown(self, mock_db_session):
        """Test scrape with shutdown signal"""
        import asyncio
        scraper = ConcreteScraper(mock_db_session, "test_source")
        shutdown_event = asyncio.Event()
        shutdown_event.set()

        retry_scraper = ScraperWithRetry(
            scraper,
            max_retries=3,
            retry_delay=1,
            shutdown_event=shutdown_event
        )

        result = retry_scraper.scrape_with_retry()

        assert result == []
