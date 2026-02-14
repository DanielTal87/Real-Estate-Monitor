#!/usr/bin/env python3
"""
Real Estate Monitor - Main Application
Autonomous real estate listing monitor for Central Israel
"""

import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from config import settings
from database import init_db
from scheduler import ScrapingScheduler
from deal_score import update_neighborhood_stats


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
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        scheduler.stop()


async def run_dashboard():
    """Run the web dashboard"""
    config = uvicorn.Config(
        "dashboard:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level=settings.log_level.lower(),
        reload=False
    )
    server = uvicorn.Server(config)
    await server.serve()


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
        logger.info("Shutting down gracefully...")
        scheduler_task.cancel()
        dashboard_task.cancel()
        logger.info("Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)
