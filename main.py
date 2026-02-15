#!/usr/bin/env python3
"""
Real Estate Monitor - Main Application
Autonomous real estate listing monitor for Central Israel
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

import uvicorn
from app.core.config import settings
from app.core.database import init_db
from app.services.scheduler import ScrapingScheduler
from app.core.deal_score import update_neighborhood_stats


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def setup_database():
    """Initialize database and create tables"""
    logger.info("Initializing database...")
    engine, SessionLocal = init_db(settings.database_url)
    logger.info("Database initialized successfully")
    return engine, SessionLocal


async def run_scheduler():
    """Run the scraping scheduler"""
    scheduler = ScrapingScheduler()
    scheduler.start()

    try:
        # Keep running
        while True:
            await asyncio.sleep(1)  # Check more frequently for faster shutdown
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Scheduler received shutdown signal")
        raise  # Re-raise to ensure proper cancellation
    finally:
        # Ensure cleanup happens
        logger.info("Cleaning up scheduler...")
        try:
            if scheduler.is_running:
                scheduler.stop()
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
        logger.info("Scheduler cleanup complete")


async def run_dashboard():
    """Run the web dashboard"""
    config = uvicorn.Config(
        "app.services.dashboard:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level=settings.log_level.lower(),
        reload=False
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Dashboard received shutdown signal")
        # Explicitly shutdown the server
        server.should_exit = True
        raise  # Re-raise to ensure proper cancellation
    finally:
        logger.info("Dashboard cleanup complete")


async def main():
    """Main application entry point"""
    logger.info("=" * 60)
    logger.info("Real Estate Monitor Starting...")
    logger.info("=" * 60)

    # Setup database
    setup_database()

    # Create tasks for scheduler and dashboard
    scheduler_task = asyncio.create_task(run_scheduler())
    dashboard_task = asyncio.create_task(run_dashboard())

    logger.info(f"Dashboard available at: http://{settings.dashboard_host}:{settings.dashboard_port}")
    logger.info("Scheduler is running. Scraping will begin shortly.")
    logger.info("Press Ctrl+C to stop.")

    # Wait for both tasks
    try:
        await asyncio.gather(scheduler_task, dashboard_task)
    except KeyboardInterrupt:
        logger.info("=" * 60)
        logger.info("Shutting down gracefully...")
        logger.info("=" * 60)

        # Cancel both tasks
        scheduler_task.cancel()
        dashboard_task.cancel()

        # Wait for tasks to complete cancellation with shorter timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(scheduler_task, dashboard_task, return_exceptions=True),
                timeout=3.0
            )
        except asyncio.TimeoutError:
            logger.warning("Shutdown timeout - forcing exit")
            # Force kill any remaining tasks
            for task in [scheduler_task, dashboard_task]:
                if not task.done():
                    task.cancel()
        except Exception as e:
            logger.debug(f"Exception during shutdown: {e}")

        logger.info("=" * 60)
        logger.info("Application stopped successfully")
        logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)
