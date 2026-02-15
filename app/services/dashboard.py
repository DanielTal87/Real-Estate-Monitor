from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.core.database import Listing, NeighborhoodStats, init_db
from app.core.config import settings
from datetime import datetime, timedelta
from typing import Optional
import logging
import urllib.parse

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Real Estate Monitor")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Add template helper functions
def format_price(price):
    """Format price with thousands separator"""
    if not price:
        return "N/A"
    return f"₪{price:,.0f}"

def days_ago(date):
    """Return human-readable time since date"""
    if not date:
        return "Unknown"

    delta = datetime.utcnow() - date

    if delta.days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            minutes = delta.seconds // 60
            return f"{minutes} minutes ago" if minutes > 1 else "Just now"
        return f"{hours} hours ago" if hours > 1 else "1 hour ago"
    elif delta.days == 1:
        return "Yesterday"
    elif delta.days < 7:
        return f"{delta.days} days ago"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks} weeks ago" if weeks > 1 else "1 week ago"
    else:
        months = delta.days // 30
        return f"{months} months ago" if months > 1 else "1 month ago"

def get_whatsapp_url(phone, address, source):
    """Generate WhatsApp URL with pre-filled message"""
    if not phone:
        return None

    # Clean phone number
    phone = phone.strip().replace('-', '').replace(' ', '')

    # Add country code if not present
    if not phone.startswith('+'):
        if phone.startswith('0'):
            phone = '+972' + phone[1:]
        else:
            phone = '+972' + phone

    # Create message
    message = f"Hi, I saw your listing on {source} for {address}. Is it still available?"
    encoded_message = urllib.parse.quote(message)

    return f"https://wa.me/{phone}?text={encoded_message}"

# Register template filters
templates.env.globals['format_price'] = format_price
templates.env.globals['days_ago'] = days_ago
templates.env.globals['get_whatsapp_url'] = get_whatsapp_url
templates.env.globals['datetime'] = datetime

# Database
engine, SessionLocal = init_db(settings.database_url)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    max_price: Optional[float] = None,
    city: Optional[str] = None,
    neighborhood: Optional[str] = None,
    sort_by: str = "deal_score"
):
    """Main dashboard page"""

    # Build query
    query = db.query(Listing)

    # Apply filters
    if status and status != 'all':
        query = query.filter(Listing.status == status)
    else:
        # Default: show unseen and interested
        query = query.filter(Listing.status.in_(['unseen', 'interested']))

    if min_score:
        query = query.filter(Listing.deal_score >= min_score)

    if max_price:
        query = query.filter(Listing.price <= max_price)

    if city:
        query = query.filter(Listing.city == city)

    if neighborhood:
        query = query.filter(Listing.neighborhood == neighborhood)

    # Apply sorting
    if sort_by == "deal_score":
        query = query.order_by(desc(Listing.deal_score))
    elif sort_by == "price_asc":
        query = query.order_by(Listing.price)
    elif sort_by == "price_desc":
        query = query.order_by(desc(Listing.price))
    elif sort_by == "newest":
        query = query.order_by(desc(Listing.first_seen))
    elif sort_by == "recently_updated":
        query = query.order_by(desc(Listing.last_seen))

    listings = query.all()

    # Get statistics
    total_listings = db.query(Listing).count()
    new_today = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=1)
    ).count()
    high_score = db.query(Listing).filter(Listing.deal_score >= 80).count()

    # Get unique cities and neighborhoods for filters
    cities = db.query(Listing.city).distinct().all()
    cities = [c[0] for c in cities if c[0]]

    neighborhoods = db.query(Listing.neighborhood).distinct().all()
    neighborhoods = [n[0] for n in neighborhoods if n[0]]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "listings": listings,
        "total_listings": total_listings,
        "new_today": new_today,
        "high_score": high_score,
        "cities": cities,
        "neighborhoods": neighborhoods,
        "current_status": status or 'active',
        "current_city": city or '',
        "current_neighborhood": neighborhood or '',
        "current_min_score": min_score or 0,
        "current_max_price": max_price or settings.max_price,
        "current_sort": sort_by
    })


@app.get("/listing/{listing_id}", response_class=HTMLResponse)
async def listing_detail(request: Request, listing_id: int, db: Session = Depends(get_db)):
    """Listing detail page"""

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Get neighborhood stats
    neighborhood_stats = db.query(NeighborhoodStats).filter(
        NeighborhoodStats.city == listing.city,
        NeighborhoodStats.neighborhood == listing.neighborhood
    ).first()

    # Get price history for chart
    price_history = sorted(listing.price_history, key=lambda x: x.timestamp)

    return templates.TemplateResponse("listing_detail.html", {
        "request": request,
        "listing": listing,
        "neighborhood_stats": neighborhood_stats,
        "price_history": price_history
    })


@app.post("/api/listing/{listing_id}/status")
async def update_listing_status(
    listing_id: int,
    status: str,
    note: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update listing status (like/hide/contacted)"""

    valid_statuses = ['unseen', 'interested', 'not_interested', 'contacted']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.status = status
    if note:
        listing.user_note = note

    db.commit()

    logger.info(f"Updated listing {listing_id} status to {status}")

    return {"success": True, "status": status}


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics"""

    total = db.query(Listing).count()

    new_today = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=1)
    ).count()

    new_week = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=7)
    ).count()

    high_score = db.query(Listing).filter(
        Listing.deal_score >= 80
    ).count()

    avg_price = db.query(func.avg(Listing.price)).filter(
        Listing.price > 0
    ).scalar()

    avg_price_per_sqm = db.query(func.avg(Listing.price_per_sqm)).filter(
        Listing.price_per_sqm > 0
    ).scalar()

    by_status = db.query(
        Listing.status,
        func.count(Listing.id)
    ).group_by(Listing.status).all()

    by_source = db.query(
        Listing.source,
        func.count(Listing.id)
    ).group_by(Listing.source).all()

    return {
        "total_listings": total,
        "new_today": new_today,
        "new_this_week": new_week,
        "high_score_count": high_score,
        "avg_price": round(avg_price, 2) if avg_price else 0,
        "avg_price_per_sqm": round(avg_price_per_sqm, 2) if avg_price_per_sqm else 0,
        "by_status": {status: count for status, count in by_status},
        "by_source": {source: count for source, count in by_source}
    }


@app.get("/api/neighborhood-stats")
async def get_neighborhood_stats(
    city: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get neighborhood statistics"""

    query = db.query(NeighborhoodStats)

    if city:
        query = query.filter(NeighborhoodStats.city == city)

    stats = query.all()

    return {
        "neighborhoods": [
            {
                "city": s.city,
                "neighborhood": s.neighborhood,
                "avg_price": s.avg_price,
                "avg_price_per_sqm": s.avg_price_per_sqm,
                "median_price": s.median_price,
                "median_price_per_sqm": s.median_price_per_sqm,
                "sample_size": s.sample_size
            }
            for s in stats
        ]
    }


@app.get("/api/price-history/{listing_id}")
async def get_price_history(listing_id: int, db: Session = Depends(get_db)):
    """Get price history for a listing"""

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    history = sorted(listing.price_history, key=lambda x: x.timestamp)

    return {
        "listing_id": listing_id,
        "history": [
            {
                "timestamp": h.timestamp.isoformat(),
                "price": h.price,
                "price_per_sqm": h.price_per_sqm
            }
            for h in history
        ]
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with scraper status"""
    from app.core.database import ScrapingState

    # Get scraping states
    states = db.query(ScrapingState).all()

    scraper_status = {}
    for state in states:
        time_since_scrape = None
        if state.last_scrape_time:
            time_since_scrape = (datetime.utcnow() - state.last_scrape_time).total_seconds()

        scraper_status[state.source] = {
            "status": state.status,
            "last_scrape": state.last_scrape_time.isoformat() if state.last_scrape_time else None,
            "seconds_since_scrape": time_since_scrape,
            "error_count": state.error_count,
            "error_message": state.error_message
        }

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "scrapers": scraper_status
    }


@app.get("/api/db-stats")
async def database_stats(db: Session = Depends(get_db)):
    """Get detailed database statistics for monitoring"""
    from app.core.database import ScrapingState, PriceHistory

    # Listing stats
    total_listings = db.query(Listing).count()

    # By status
    by_status = db.query(
        Listing.status,
        func.count(Listing.id)
    ).group_by(Listing.status).all()

    # By source
    by_source = db.query(
        Listing.source,
        func.count(Listing.id)
    ).group_by(Listing.source).all()

    # By city
    by_city = db.query(
        Listing.city,
        func.count(Listing.id)
    ).group_by(Listing.city).all()

    # Recent activity
    new_today = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=1)
    ).count()

    new_week = db.query(Listing).filter(
        Listing.first_seen >= datetime.utcnow() - timedelta(days=7)
    ).count()

    # Scraper status
    scraper_states = db.query(ScrapingState).all()

    return {
        "database": {
            "total_listings": total_listings,
            "new_today": new_today,
            "new_this_week": new_week,
            "by_status": {status: count for status, count in by_status},
            "by_source": {source: count for source, count in by_source},
            "by_city": {city: count for city, count in by_city}
        },
        "scrapers": [
            {
                "source": s.source,
                "status": s.status,
                "last_scrape": s.last_scrape_time.isoformat() if s.last_scrape_time else None,
                "error_count": s.error_count,
                "error_message": s.error_message
            }
            for s in scraper_states
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
