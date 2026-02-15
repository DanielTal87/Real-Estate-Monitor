from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.scrapers.yad2_scraper import Yad2Scraper
from app.scrapers.madlan_scraper import MadlanScraper
from app.scrapers.facebook_scraper import FacebookScraper
from app.scrapers.base_scraper import ScraperWithRetry
from app.core.listing_processor import ListingProcessor
from app.services.telegram_notifier import TelegramNotifier
from app.core.deal_score import update_neighborhood_stats
from app.core.database import init_db
from app.core.config import settings
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
        logger.info("[Scheduler] Starting scraping scheduler...")

        # Schedule Yad2
        logger.info(f"[Scheduler] Scheduling Yad2 scraper, interval: {settings.yad2_interval_minutes} minutes")
        self.scheduler.add_job(
            self.scrape_yad2,
            trigger=IntervalTrigger(minutes=settings.yad2_interval_minutes),
            id='yad2_scraper',
            name='Yad2 Scraper',
            replace_existing=True
        )

        # Schedule Madlan
        logger.info(f"[Scheduler] Scheduling Madlan scraper, interval: {settings.madlan_interval_minutes} minutes")
        self.scheduler.add_job(
            self.scrape_madlan,
            trigger=IntervalTrigger(minutes=settings.madlan_interval_minutes),
            id='madlan_scraper',
            name='Madlan Scraper',
            replace_existing=True
        )

        # Schedule Facebook
        logger.info(f"[Scheduler] Scheduling Facebook scraper, interval: {settings.facebook_interval_minutes} minutes")
        self.scheduler.add_job(
            self.scrape_facebook,
            trigger=IntervalTrigger(minutes=settings.facebook_interval_minutes),
            id='facebook_scraper',
            name='Facebook Scraper',
            replace_existing=True
        )

        # Schedule neighborhood stats update (every 6 hours)
        logger.info("[Scheduler] Scheduling neighborhood stats updater, interval: 6 hours")
        self.scheduler.add_job(
            self.update_stats,
            trigger=IntervalTrigger(hours=6),
            id='stats_updater',
            name='Neighborhood Stats Updater',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("[Scheduler] ✅ Scheduler started successfully")
        logger.info(f"[Scheduler] Job schedule - Yad2: Every {settings.yad2_interval_minutes} min | Madlan: Every {settings.madlan_interval_minutes} min | Facebook: Every {settings.facebook_interval_minutes} min")
        logger.info("[Scheduler] ⏰ Initial scrape will begin in 5 seconds...")

        # Run initial scrape immediately
        asyncio.create_task(self.run_initial_scrape())

    async def run_initial_scrape(self):
        """Run initial scrape on startup"""
        logger.info("[Scheduler] 🚀 Running initial scrape sequence...")
        logger.info("[Scheduler] Waiting 5 seconds for system initialization...")
        await asyncio.sleep(5)

        logger.info("[Scheduler] Starting Yad2 initial scrape")
        await self.scrape_yad2()
        logger.info("[Scheduler] Waiting 30 seconds before next source...")
        await asyncio.sleep(30)

        logger.info("[Scheduler] Starting Madlan initial scrape")
        await self.scrape_madlan()
        logger.info("[Scheduler] Waiting 30 seconds before next source...")
        await asyncio.sleep(30)

        logger.info("[Scheduler] Starting Facebook initial scrape")
        await self.scrape_facebook()

        # Update stats after initial scrape
        logger.info("[Scheduler] Updating neighborhood statistics after initial scrape")
        await self.update_stats()

        logger.info("[Scheduler] ✅ Initial scrape sequence completed successfully")

    async def scrape_yad2(self):
        """Scrape Yad2"""
        logger.info("=" * 60)
        logger.info("[Scheduler] 🔍 Starting Yad2 scrape job")
        logger.info("=" * 60)
        db = self.SessionLocal()

        try:
            logger.info("[Scheduler] Initializing Yad2 scraper")
            scraper = Yad2Scraper(db)
            scraper_with_retry = ScraperWithRetry(scraper)

            logger.info("[Scheduler] Executing Yad2 scraper with retry logic")
            listings = await scraper_with_retry.scrape_with_retry()

            if listings:
                logger.info(f"[Scheduler] Yad2 scraper returned listings, count: {len(listings)}")
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'yad2')

                logger.info(f"[Scheduler] Yad2 scrape completed successfully, stats: {stats}")

                # Send notifications for new listings
                if stats['new'] > 0 or stats['price_drops'] > 0:
                    logger.info(f"[Scheduler] Sending notifications, new: {stats['new']}, price_drops: {stats['price_drops']}")
                    await self._notify_new_listings(db, stats)
            else:
                logger.warning("[Scheduler] Yad2 scraper returned no listings")

        except Exception as e:
            logger.error(f"[Scheduler] Error in Yad2 scrape job, error: {e}")
        finally:
            db.close()
            logger.info("[Scheduler] Yad2 scrape job finished")

    async def scrape_madlan(self):
        """Scrape Madlan"""
        logger.info("=" * 60)
        logger.info("[Scheduler] 🔍 Starting Madlan scrape job")
        logger.info("=" * 60)
        db = self.SessionLocal()

        try:
            logger.info("[Scheduler] Initializing Madlan scraper")
            scraper = MadlanScraper(db)
            scraper_with_retry = ScraperWithRetry(scraper)

            logger.info("[Scheduler] Executing Madlan scraper with retry logic")
            listings = await scraper_with_retry.scrape_with_retry()

            if listings:
                logger.info(f"[Scheduler] Madlan scraper returned listings, count: {len(listings)}")
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'madlan')

                logger.info(f"[Scheduler] Madlan scrape completed successfully, stats: {stats}")

                # Send notifications
                if stats['new'] > 0 or stats['price_drops'] > 0:
                    logger.info(f"[Scheduler] Sending notifications, new: {stats['new']}, price_drops: {stats['price_drops']}")
                    await self._notify_new_listings(db, stats)
            else:
                logger.warning("[Scheduler] Madlan scraper returned no listings")

        except Exception as e:
            logger.error(f"[Scheduler] Error in Madlan scrape job, error: {e}")
        finally:
            db.close()
            logger.info("[Scheduler] Madlan scrape job finished")

    async def scrape_facebook(self):
        """Scrape Facebook"""
        logger.info("=" * 60)
        logger.info("[Scheduler] 🔍 Starting Facebook scrape job")
        logger.info("=" * 60)
        db = self.SessionLocal()

        try:
            cookies_file = settings.facebook_cookies_file
            logger.info(f"[Scheduler] Initializing Facebook scraper, cookies_file: {cookies_file}")
            scraper = FacebookScraper(db, cookies_file=cookies_file)
            scraper_with_retry = ScraperWithRetry(scraper)

            logger.info("[Scheduler] Executing Facebook scraper with retry logic")
            listings = await scraper_with_retry.scrape_with_retry()

            if listings:
                logger.info(f"[Scheduler] Facebook scraper returned listings, count: {len(listings)}")
                processor = ListingProcessor(db)
                stats = processor.process_listings(listings, 'facebook')

                logger.info(f"[Scheduler] Facebook scrape completed successfully, stats: {stats}")

                # Send notifications
                if stats['new'] > 0 or stats['price_drops'] > 0:
                    logger.info(f"[Scheduler] Sending notifications, new: {stats['new']}, price_drops: {stats['price_drops']}")
                    await self._notify_new_listings(db, stats)
            else:
                logger.warning("[Scheduler] Facebook scraper returned no listings")

        except Exception as e:
            logger.error(f"[Scheduler] Error in Facebook scrape job, error: {e}")
        finally:
            db.close()
            logger.info("[Scheduler] Facebook scrape job finished")

    async def update_stats(self):
        """Update neighborhood statistics"""
        logger.info("[Scheduler] 📊 Starting neighborhood statistics update")
        db = self.SessionLocal()

        try:
            update_neighborhood_stats(db)
            logger.info("[Scheduler] Neighborhood statistics updated successfully")
        except Exception as e:
            logger.error(f"[Scheduler] Error updating neighborhood stats, error: {e}")
        finally:
            db.close()

    async def _notify_new_listings(self, db, stats: dict):
        """Send notifications for new/updated listings"""
        if stats['new'] == 0 and stats['price_drops'] == 0:
            return

        try:
            from app.core.database import Listing
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
            # Shutdown with a short wait to allow jobs to finish gracefully
            self.scheduler.shutdown(wait=True)
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
