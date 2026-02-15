"""
Unit tests for scheduler service
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from app.services.scheduler import ScrapingScheduler


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    return Mock()


@pytest.fixture
def mock_shutdown_event():
    """Create mock shutdown event"""
    event = asyncio.Event()
    return event


@pytest.fixture
def scheduler(mock_shutdown_event):
    """Create scheduler instance"""
    with patch('app.services.scheduler.init_db') as mock_init:
        mock_engine = Mock()
        mock_session_local = Mock()
        mock_init.return_value = (mock_engine, mock_session_local)

        scheduler = ScrapingScheduler(shutdown_event=mock_shutdown_event)
        yield scheduler

        # Cleanup
        if scheduler.is_running:
            scheduler.stop()


class TestScrapingScheduler:
    """Test ScrapingScheduler class"""

    def test_init(self, scheduler):
        """Test scheduler initialization"""
        assert scheduler is not None
        assert scheduler.is_running is False
        assert scheduler.shutdown_event is not None

    @patch('app.services.scheduler.AsyncIOScheduler')
    def test_start(self, mock_scheduler_class, scheduler):
        """Test starting the scheduler"""
        mock_scheduler_instance = Mock()
        mock_scheduler_class.return_value = mock_scheduler_instance
        scheduler.scheduler = mock_scheduler_instance

        with patch.object(scheduler, 'run_initial_scrape', new_callable=AsyncMock):
            with patch('asyncio.create_task'):
                scheduler.start()

                assert scheduler.is_running is True
                mock_scheduler_instance.start.assert_called_once()

    def test_stop(self, scheduler):
        """Test stopping the scheduler"""
        scheduler.is_running = True
        mock_scheduler = Mock()
        scheduler.scheduler = mock_scheduler

        scheduler.stop()

        assert scheduler.is_running is False
        mock_scheduler.shutdown.assert_called_once()

    def test_stop_when_not_running(self, scheduler):
        """Test stopping when not running"""
        scheduler.is_running = False
        scheduler.stop()
        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_run_initial_scrape(self, scheduler):
        """Test initial scrape sequence"""
        with patch.object(scheduler, 'scrape_yad2', new_callable=AsyncMock) as mock_yad2:
            with patch.object(scheduler, 'scrape_madlan', new_callable=AsyncMock) as mock_madlan:
                with patch.object(scheduler, 'scrape_facebook', new_callable=AsyncMock) as mock_facebook:
                    with patch.object(scheduler, 'update_stats', new_callable=AsyncMock) as mock_stats:
                        with patch('asyncio.sleep', new_callable=AsyncMock):
                            await scheduler.run_initial_scrape()

                            mock_yad2.assert_called_once()
                            mock_madlan.assert_called_once()
                            mock_facebook.assert_called_once()
                            mock_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_yad2(self, scheduler):
        """Test Yad2 scraping"""
        mock_db = Mock()
        scheduler.SessionLocal = Mock(return_value=mock_db)

        with patch('app.services.scheduler.Yad2Scraper') as mock_scraper_class:
            with patch('app.services.scheduler.ScraperWithRetry') as mock_retry_class:
                with patch('app.services.scheduler.ListingProcessor') as mock_processor_class:
                    # Setup mocks
                    mock_scraper = Mock()
                    mock_scraper_class.return_value = mock_scraper

                    mock_retry = Mock()
                    mock_retry.scrape_with_retry.return_value = [{'title': 'Test'}]
                    mock_retry_class.return_value = mock_retry

                    mock_processor = Mock()
                    mock_processor.process_listings.return_value = {
                        'new': 1,
                        'updated': 0,
                        'price_drops': 0
                    }
                    mock_processor_class.return_value = mock_processor

                    with patch.object(scheduler, '_notify_new_listings', new_callable=AsyncMock):
                        with patch('asyncio.get_event_loop') as mock_loop:
                            mock_loop.return_value.run_in_executor = AsyncMock(
                                return_value=[{'title': 'Test'}]
                            )

                            await scheduler.scrape_yad2()

                            mock_scraper_class.assert_called_once()
                            mock_processor.process_listings.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_yad2_shutdown(self, scheduler):
        """Test Yad2 scraping with shutdown signal"""
        scheduler.shutdown_event.set()

        await scheduler.scrape_yad2()
        # Should return early without scraping

    @pytest.mark.asyncio
    async def test_scrape_yad2_no_listings(self, scheduler):
        """Test Yad2 scraping with no listings"""
        mock_db = Mock()
        scheduler.SessionLocal = Mock(return_value=mock_db)

        with patch('app.services.scheduler.Yad2Scraper'):
            with patch('app.services.scheduler.ScraperWithRetry') as mock_retry_class:
                mock_retry = Mock()
                mock_retry.scrape_with_retry.return_value = []
                mock_retry_class.return_value = mock_retry

                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(return_value=[])

                    await scheduler.scrape_yad2()
                    # Should complete without errors

    @pytest.mark.asyncio
    async def test_scrape_madlan(self, scheduler):
        """Test Madlan scraping"""
        mock_db = Mock()
        scheduler.SessionLocal = Mock(return_value=mock_db)

        with patch('app.services.scheduler.MadlanScraper') as mock_scraper_class:
            with patch('app.services.scheduler.ScraperWithRetry') as mock_retry_class:
                with patch('app.services.scheduler.ListingProcessor') as mock_processor_class:
                    mock_scraper = Mock()
                    mock_scraper_class.return_value = mock_scraper

                    mock_retry = Mock()
                    mock_retry.scrape_with_retry.return_value = [{'title': 'Test'}]
                    mock_retry_class.return_value = mock_retry

                    mock_processor = Mock()
                    mock_processor.process_listings.return_value = {
                        'new': 0,
                        'updated': 1,
                        'price_drops': 0
                    }
                    mock_processor_class.return_value = mock_processor

                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock(
                            return_value=[{'title': 'Test'}]
                        )

                        await scheduler.scrape_madlan()

                        mock_scraper_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_facebook(self, scheduler):
        """Test Facebook scraping"""
        mock_db = Mock()
        scheduler.SessionLocal = Mock(return_value=mock_db)

        with patch('app.services.scheduler.FacebookScraper') as mock_scraper_class:
            with patch('app.services.scheduler.ScraperWithRetry') as mock_retry_class:
                with patch('app.services.scheduler.ListingProcessor') as mock_processor_class:
                    mock_scraper = Mock()
                    mock_scraper_class.return_value = mock_scraper

                    mock_retry = Mock()
                    mock_retry.scrape_with_retry.return_value = [{'title': 'Test'}]
                    mock_retry_class.return_value = mock_retry

                    mock_processor = Mock()
                    mock_processor.process_listings.return_value = {
                        'new': 0,
                        'updated': 0,
                        'price_drops': 1
                    }
                    mock_processor_class.return_value = mock_processor

                    with patch('asyncio.get_event_loop') as mock_loop:
                        mock_loop.return_value.run_in_executor = AsyncMock(
                            return_value=[{'title': 'Test'}]
                        )

                        await scheduler.scrape_facebook()

                        mock_scraper_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stats(self, scheduler):
        """Test updating neighborhood stats"""
        mock_db = Mock()
        scheduler.SessionLocal = Mock(return_value=mock_db)

        with patch('app.services.scheduler.update_neighborhood_stats') as mock_update:
            await scheduler.update_stats()

            mock_update.assert_called_once_with(mock_db)

    @pytest.mark.asyncio
    async def test_update_stats_error(self, scheduler):
        """Test updating stats with error"""
        mock_db = Mock()
        scheduler.SessionLocal = Mock(return_value=mock_db)

        with patch('app.services.scheduler.update_neighborhood_stats') as mock_update:
            mock_update.side_effect = Exception("Test error")

            # Should not raise, just log error
            await scheduler.update_stats()

    @pytest.mark.asyncio
    async def test_notify_new_listings(self, scheduler):
        """Test notifying new listings"""
        mock_db = Mock()
        mock_listing = Mock()
        mock_listing.deal_score = 85
        mock_listing.first_seen = datetime.utcnow()
        mock_listing.status = 'unseen'

        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_listing]

        stats = {'new': 1, 'price_drops': 0}

        with patch('app.services.scheduler.TelegramNotifier') as mock_notifier_class:
            with patch('asyncio.sleep', new_callable=AsyncMock):
                mock_notifier = Mock()
                mock_notifier.notify_high_score = AsyncMock()
                mock_notifier_class.return_value = mock_notifier

                await scheduler._notify_new_listings(mock_db, stats)

                mock_notifier.notify_high_score.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_new_listings_no_new(self, scheduler):
        """Test notifying with no new listings"""
        mock_db = Mock()
        stats = {'new': 0, 'price_drops': 0}

        await scheduler._notify_new_listings(mock_db, stats)
        # Should return early

    @pytest.mark.asyncio
    async def test_notify_new_listings_error(self, scheduler):
        """Test notifying with error"""
        mock_db = Mock()
        mock_db.query.side_effect = Exception("Test error")

        stats = {'new': 1, 'price_drops': 0}

        # Should not raise, just log error
        await scheduler._notify_new_listings(mock_db, stats)

    def test_get_status(self, scheduler):
        """Test getting scheduler status"""
        mock_job = Mock()
        mock_job.id = 'test_job'
        mock_job.name = 'Test Job'
        mock_job.next_run_time = datetime.utcnow()

        scheduler.scheduler.get_jobs = Mock(return_value=[mock_job])
        scheduler.is_running = True

        status = scheduler.get_status()

        assert status['running'] is True
        assert len(status['jobs']) == 1
        assert status['jobs'][0]['id'] == 'test_job'

    def test_get_status_not_running(self, scheduler):
        """Test getting status when not running"""
        scheduler.is_running = False
        scheduler.scheduler.get_jobs = Mock(return_value=[])

        status = scheduler.get_status()

        assert status['running'] is False
        assert len(status['jobs']) == 0
