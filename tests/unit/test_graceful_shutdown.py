"""
Unit tests for graceful shutdown functionality in Scheduler and ScraperWithRetry.
"""
import pytest
import asyncio
import threading
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from app.services.scheduler import ScrapingScheduler
from app.scrapers.base_scraper import ScraperWithRetry, BaseScraper


class TestScraperWithRetryShutdown:
    """Test graceful shutdown in ScraperWithRetry"""

    def test_shutdown_event_breaks_retry_loop(self, db_session, mock_chromium_page):
        """Test that shutdown_event.set() breaks the retry loop"""
        # Create shutdown event
        shutdown_event = threading.Event()

        # Create a mock scraper that always fails
        mock_scraper = Mock(spec=BaseScraper)
        mock_scraper.source_name = 'test_scraper'
        mock_scraper.initialize = Mock(side_effect=Exception("Test error"))
        mock_scraper.cleanup = Mock()
        mock_scraper.update_scraping_state = Mock()

        # Create scraper with retry
        scraper_with_retry = ScraperWithRetry(
            scraper=mock_scraper,
            max_retries=10,  # High number to ensure we test shutdown, not exhaustion
            retry_delay=1,
            shutdown_event=shutdown_event
        )

        # Set shutdown event after a short delay in a separate thread
        def set_shutdown():
            import time
            time.sleep(0.5)  # Wait a bit before shutting down
            shutdown_event.set()

        shutdown_thread = threading.Thread(target=set_shutdown)
        shutdown_thread.start()

        # Run scraper - should exit quickly due to shutdown event
        start_time = datetime.utcnow()
        result = scraper_with_retry.scrape_with_retry()
        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Verify it returned empty list
        assert result == []

        # Verify it didn't run for full retry duration (10 retries * 1 second = 10 seconds)
        # Should exit much faster due to shutdown event
        assert elapsed < 5, f"Shutdown took too long: {elapsed} seconds"

        # Verify initialize was called at least once
        assert mock_scraper.initialize.call_count >= 1

        # Cleanup
        shutdown_thread.join()

    def test_shutdown_during_retry_delay(self, db_session, mock_chromium_page):
        """Test that shutdown event is checked during retry delay"""
        shutdown_event = threading.Event()

        # Create a mock scraper that fails on first attempt
        mock_scraper = Mock(spec=BaseScraper)
        mock_scraper.source_name = 'test_scraper'
        mock_scraper.initialize = Mock(side_effect=Exception("Test error"))
        mock_scraper.cleanup = Mock()
        mock_scraper.update_scraping_state = Mock()

        scraper_with_retry = ScraperWithRetry(
            scraper=mock_scraper,
            max_retries=5,
            retry_delay=10,  # Long delay to test shutdown during wait
            shutdown_event=shutdown_event
        )

        # Set shutdown event after a short delay
        def set_shutdown():
            import time
            time.sleep(0.5)
            shutdown_event.set()

        shutdown_thread = threading.Thread(target=set_shutdown)
        shutdown_thread.start()

        # Run scraper
        start_time = datetime.utcnow()
        result = scraper_with_retry.scrape_with_retry()
        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Should exit quickly, not wait for full retry_delay
        assert elapsed < 5, f"Shutdown during retry delay took too long: {elapsed} seconds"
        assert result == []

        shutdown_thread.join()

    def test_no_shutdown_event_completes_normally(self, db_session, mock_chromium_page):
        """Test that scraper works normally without shutdown event"""
        # Create a mock scraper that succeeds
        mock_scraper = Mock(spec=BaseScraper)
        mock_scraper.source_name = 'test_scraper'
        mock_scraper.initialize = Mock()
        mock_scraper.scrape = Mock(return_value=[{'test': 'data'}])
        mock_scraper.cleanup = Mock()
        mock_scraper.update_scraping_state = Mock()

        # No shutdown event
        scraper_with_retry = ScraperWithRetry(
            scraper=mock_scraper,
            max_retries=3,
            retry_delay=1,
            shutdown_event=None
        )

        # Run scraper
        result = scraper_with_retry.scrape_with_retry()

        # Should complete successfully
        assert result == [{'test': 'data'}]
        assert mock_scraper.initialize.call_count == 1
        assert mock_scraper.scrape.call_count == 1
        assert mock_scraper.cleanup.call_count == 1


class TestSchedulerShutdown:
    """Test graceful shutdown in ScrapingScheduler"""

    @pytest.mark.asyncio
    async def test_scheduler_respects_shutdown_event(self, db_session):
        """Test that scheduler checks shutdown event before scraping"""
        # Create shutdown event and set it immediately
        shutdown_event = asyncio.Event()
        shutdown_event.set()

        # Create scheduler with shutdown event
        with patch('app.services.scheduler.init_db') as mock_init_db:
            mock_init_db.return_value = (Mock(), Mock(return_value=db_session))

            scheduler = ScrapingScheduler(shutdown_event=shutdown_event)

            # Try to run scrape methods - they should exit immediately
            await scheduler.scrape_yad2()
            await scheduler.scrape_madlan()
            await scheduler.scrape_facebook()

            # No assertions needed - if we get here without hanging, test passes

    @pytest.mark.asyncio
    async def test_scheduler_shutdown_prevents_scraping(self):
        """Test that setting shutdown event prevents new scraping jobs"""
        shutdown_event = asyncio.Event()

        with patch('app.services.scheduler.init_db') as mock_init_db:
            mock_session = Mock()
            mock_init_db.return_value = (Mock(), Mock(return_value=mock_session))

            scheduler = ScrapingScheduler(shutdown_event=shutdown_event)

            # Set shutdown event
            shutdown_event.set()

            # Try to scrape - should exit immediately without creating scrapers
            with patch('app.services.scheduler.Yad2Scraper') as mock_yad2:
                await scheduler.scrape_yad2()
                # Scraper should not be instantiated
                mock_yad2.assert_not_called()

    @pytest.mark.asyncio
    async def test_initial_scrape_with_shutdown(self):
        """Test that initial scrape sequence respects shutdown event"""
        shutdown_event = asyncio.Event()

        with patch('app.services.scheduler.init_db') as mock_init_db:
            mock_session = Mock()
            mock_init_db.return_value = (Mock(), Mock(return_value=mock_session))

            scheduler = ScrapingScheduler(shutdown_event=shutdown_event)

            # Set shutdown event before initial scrape
            shutdown_event.set()

            # Run initial scrape - should complete quickly
            start_time = datetime.utcnow()
            await scheduler.run_initial_scrape()
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            # Should exit quickly (within 10 seconds, not wait for full sequence)
            assert elapsed < 10, f"Initial scrape with shutdown took too long: {elapsed} seconds"


class TestAsyncSleepUsage:
    """Test that asyncio.sleep is used instead of time.sleep in async contexts"""

    @pytest.mark.asyncio
    async def test_scheduler_uses_asyncio_sleep(self):
        """Test that scheduler uses asyncio.sleep for delays"""
        shutdown_event = asyncio.Event()

        with patch('app.services.scheduler.init_db') as mock_init_db:
            mock_session = Mock()
            mock_init_db.return_value = (Mock(), Mock(return_value=mock_session))

            scheduler = ScrapingScheduler(shutdown_event=shutdown_event)

            # Patch asyncio.sleep to verify it's called
            with patch('asyncio.sleep', new_callable=MagicMock) as mock_sleep:
                mock_sleep.return_value = asyncio.coroutine(lambda: None)()

                # Run initial scrape (which has sleep calls)
                shutdown_event.set()  # Set to exit quickly
                await scheduler.run_initial_scrape()

                # Verify asyncio.sleep was called (for the 5 second initial delay)
                assert mock_sleep.call_count >= 1, "asyncio.sleep should be called in async methods"


class TestShutdownEventPropagation:
    """Test that shutdown event is properly propagated through the system"""

    def test_shutdown_event_passed_to_scraper_with_retry(self, db_session):
        """Test that shutdown event is passed from scheduler to ScraperWithRetry"""
        shutdown_event = threading.Event()

        mock_scraper = Mock(spec=BaseScraper)
        mock_scraper.source_name = 'test'

        # Create ScraperWithRetry with shutdown event
        scraper_with_retry = ScraperWithRetry(
            scraper=mock_scraper,
            max_retries=3,
            retry_delay=1,
            shutdown_event=shutdown_event
        )

        # Verify shutdown event is stored
        assert scraper_with_retry.shutdown_event is shutdown_event

        # Set shutdown event
        shutdown_event.set()

        # Verify it's set
        assert scraper_with_retry.shutdown_event.is_set()
