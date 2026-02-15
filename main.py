#!/usr/bin/env python3
"""
Real Estate Monitor - Main Application
Autonomous real estate listing monitor for Central Israel
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
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

# Global shutdown event
shutdown_event = asyncio.Event()

# Global scheduler instance
scheduler_instance = None


def setup_database():
    """Initialize database and create tables"""
    logger.info("Initializing database...")
    engine, SessionLocal = init_db(settings.database_url)
    logger.info("Database initialized successfully")
    return engine, SessionLocal


async def run_scheduler():
    """Run the scraping scheduler with shutdown support"""
    global scheduler_instance

    scheduler_instance = ScrapingScheduler(shutdown_event)
    scheduler_instance.start()

    try:
        # Keep running until shutdown signal
        while not shutdown_event.is_set():
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Scheduler task cancelled")
    finally:
        # Ensure cleanup happens
        logger.info("Cleaning up scheduler...")
        try:
            if scheduler_instance and scheduler_instance.is_running:
                scheduler_instance.stop()
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
        logger.info("Scheduler cleanup complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.
    This ensures graceful shutdown of all background tasks.
    """
    logger.info("=" * 60)
    logger.info("Real Estate Monitor Starting...")
    logger.info("=" * 60)

    # Setup database
    setup_database()

    # Create scheduler task
    scheduler_task = asyncio.create_task(run_scheduler())

    logger.info(f"Dashboard available at: http://{settings.dashboard_host}:{settings.dashboard_port}")
    logger.info("Scheduler is running. Scraping will begin shortly.")
    logger.info("Press Ctrl+C to stop.")

    # Yield control to FastAPI
    yield

    # Shutdown sequence
    logger.info("=" * 60)
    logger.info("Shutting down gracefully...")
    logger.info("=" * 60)

    # Signal shutdown to all tasks
    shutdown_event.set()

    # Cancel scheduler task
    scheduler_task.cancel()

    # Wait for scheduler to complete with timeout
    try:
        await asyncio.wait_for(scheduler_task, timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Scheduler shutdown timeout - forcing exit")
    except asyncio.CancelledError:
        logger.debug("Scheduler task cancelled successfully")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {e}")

    logger.info("=" * 60)
    logger.info("Application stopped successfully")
    logger.info("=" * 60)


# Import the dashboard app and add lifespan
from app.services.dashboard import app as dashboard_app

# Create a new app with lifespan
app = FastAPI(title="Real Estate Monitor", lifespan=lifespan)

# Mount all routes from dashboard app
app.mount("/", dashboard_app)


if __name__ == "__main__":
    try:
        uvicorn.run(
            app,
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)
