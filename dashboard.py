from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from database import Listing, NeighborhoodStats, init_db
from config import settings
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Real Estate Monitor")

# Setup templates
templates = Jinja2Templates(directory="templates")

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
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
