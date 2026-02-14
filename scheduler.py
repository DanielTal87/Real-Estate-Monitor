from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from scrapers.yad2_scraper import Yad2Scraper
from scrapers.madlan_scraper import MadlanScraper
from scrapers.facebook_scraper import FacebookScraper
from scrapers.base_scraper import ScraperWithRetry
from listing_processor import ListingProcessor
from telegram_notifier import TelegramNotifier
from deal_score import update_neighborhood_stats
from database import init_db
from config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)


class ScrapingScheduler:
    """Manage scheduled scraping jobs"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.engine, self.SessionLocal = init_db(settings.database_url)
        self.is_running = False

    def start(self):
        """Start the scheduler"""
        logger.info("Starting scraping scheduler...")

        # Schedule Yad2
        self.scheduler.add_job(
            self.scrape_yad2,
            trigger=IntervalTrigger(minutes=settings.yad2_interval_minutes),
            id='yad2_scraper',
            name='Yad2 Scraper',
            replace_existing=True
        )

        # Schedule Madlan
        self.scheduler.add_job(
            self.scrape_madlan,
            trigger=IntervalTrigger(minutes=settings.madlan_interval_minutes),
            id='madlan_scraper',
            name='Madlan Scraper',
            replace_existing=True
        )

        # Schedule Facebook
        self.scheduler.add_job(
            self.scrape_facebook,
            trigger=IntervalTrigger(minutes=settings.facebook_interval_minutes),
            id='facebook_scraper',
            name='Facebook Scraper',
            replace_existing=True
        )

        # Schedule neighborhood stats update (every 6 hours)
        self.scheduler.add_job(
            self.update_stats,
            trigger=IntervalTrigger(hours=6),
            id='stats_updater',
            name='Neighborhood Stats Updater',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("Scheduler started successfully")
        logger.info(f"Yad2: Every {settings.yad2_interval_minutes} minutes")
        logger.info(f"Madlan: Every {settings.madlan_interval_minutes} minutes")
        logger.info(f"Facebook: Every {settings.facebook_interval_minutes} minutes")

        # Run initial scrape immediately
        # asyncio.create_task(self.run_initial_scrape())

    async def run_initial_scrape(self):
        """Run initial scrape on startup"""
        logger.info("Running initial scrape...")
        await asyncio.sleep(5)  # Wait a bit for system to initialize

        await self.scrape_yad2()
        await asyncio.sleep(30)  # Delay between sources

        await self.scrape_madlan()
        await asyncio.sleep(30)

        await self.scrape_facebook()

        # Update stats after initial scrape
        await self.update_stats()

        logger.info("Initial scrape completed")

    async def scrape_yad2(self):
        """Scrape Yad2"""
        logger.info("🔍 Starting Yad2 scrape...")
        db = self.SessionLocal()

        try:
            scraper = Yad2Scraper(db)
            scraper_with_retry = ScraperWithRetry(scraper)

            listings = await scraper_with_retry.scrape_with_retry()

            if listings:
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'yad2')

                logger.info(f"Yad2 scrape complete: {stats}")

                # Send notifications for new listings
                await self._notify_new_listings(db, stats)

        except Exception as e:
            logger.error(f"Error in Yad2 scrape: {e}")
        finally:
            db.close()

    async def scrape_madlan(self):
        """Scrape Madlan"""
        logger.info("🔍 Starting Madlan scrape...")
        db = self.SessionLocal()

        try:
            scraper = MadlanScraper(db)
            scraper_with_retry = ScraperWithRetry(scraper)

            listings = await scraper_with_retry.scrape_with_retry()

            if listings:
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'madlan')

                logger.info(f"Madlan scrape complete: {stats}")

                # Send notifications
                await self._notify_new_listings(db, stats)

        except Exception as e:
            logger.error(f"Error in Madlan scrape: {e}")
        finally:
            db.close()

    async def scrape_facebook(self):
        """Scrape Facebook"""
        logger.info("🔍 Starting Facebook scrape...")
        db = self.SessionLocal()

        try:
            cookies_file = settings.facebook_cookies_file
            scraper = FacebookScraper(db, cookies_file=cookies_file)
            scraper_with_retry = ScraperWithRetry(scraper)

            listings = await scraper_with_retry.scrape_with_retry()

            if listings:
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'facebook')

                logger.info(f"Facebook scrape complete: {stats}")

                # Send notifications
                await self._notify_new_listings(db, stats)

        except Exception as e:
            logger.error(f"Error in Facebook scrape: {e}")
        finally:
            db.close()

    async def update_stats(self):
        """Update neighborhood statistics"""
        logger.info("📊 Updating neighborhood statistics...")
        db = self.SessionLocal()

        try:
            update_neighborhood_stats(db)
            logger.info("Neighborhood stats updated")
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
        finally:
            db.close()

    async def _notify_new_listings(self, db, stats: dict):
        """Send notifications for new/updated listings"""
        if stats['new'] == 0 and stats['price_drops'] == 0:
            return

        try:
            from database import Listing
            from datetime import datetime, timedelta

            notifier = TelegramNotifier(db)

            # Get recent new listings (last 5 minutes)
            recent_listings = db.query(Listing).filter(
                Listing.first_seen > datetime.utcnow() - timedelta(minutes=5),
                Listing.status == 'unseen'
            ).all()

            for listing in recent_listings:
                # Try to notify
                if listing.deal_score >= settings.min_deal_score_notify:
                    await notifier.notify_high_score(listing)
                else:
                    await notifier.notify_new_listing(listing)

                # Small delay between notifications
                await asyncio.sleep(1)

            # Check for price drops
            price_drop_listings = db.query(Listing).filter(
                Listing.last_seen > datetime.utcnow() - timedelta(minutes=5)
            ).all()

            for listing in price_drop_listings:
                await notifier.notify_price_drop(listing)
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

    def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return

        logger.info("Stopping scraping scheduler...")
        try:
            # Use wait=False to avoid blocking on job completion
            self.scheduler.shutdown(wait=False)
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
        finally:
            self.is_running = False
            logger.info("Scheduler stopped")

    def get_status(self) -> dict:
        """Get scheduler status"""
        jobs = self.scheduler.get_jobs()

        return {
            'running': self.is_running,
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in jobs
            ]
        }
