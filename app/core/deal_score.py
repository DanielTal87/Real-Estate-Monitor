from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import Listing, NeighborhoodStats
from app.core.config import settings
import statistics


class DealScoreCalculator:
    """Calculate deal score for listings based on multiple factors"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.settings = settings

    def calculate_score(self, listing: Listing) -> float:
        """
        Calculate deal score (0-100) for a listing

        Scoring breakdown (configurable via settings):
        - Price competitiveness: 0-{price_weight} points
        - Features match: 0-{features_weight} points
        - Recency/freshness: 0-{recency_weight} points
        - Price trend: 0-{trend_weight} points
        """
        score = 0.0

        # 1. Price Competitiveness
        score += self._score_price_competitiveness(listing)

        # 2. Features Match
        score += self._score_features(listing)

        # 3. Recency
        score += self._score_recency(listing)

        # 4. Price Trend
        score += self._score_price_trend(listing)

        return min(100.0, max(0.0, score))

    def _score_price_competitiveness(self, listing: Listing) -> float:
        """Score based on price per sqm vs neighborhood average"""
        if not listing.price_per_sqm or listing.price_per_sqm <= 0:
            return 0.0

        max_score = self.settings.deal_score_weight_price

        # Get neighborhood stats
        stats = self.db.query(NeighborhoodStats).filter(
            NeighborhoodStats.city == listing.city,
            NeighborhoodStats.neighborhood == listing.neighborhood
        ).first()

        if not stats or not stats.avg_price_per_sqm:
            # No data, give neutral score (50% of max)
            return max_score * 0.5

        # Calculate percentage difference
        avg_price = stats.avg_price_per_sqm
        price_ratio = listing.price_per_sqm / avg_price

        # Score based on how much below average (percentage of max_score)
        if price_ratio <= 0.7:  # 30% below average
            return max_score * 1.0
        elif price_ratio <= 0.8:  # 20% below average
            return max_score * 0.875
        elif price_ratio <= 0.9:  # 10% below average
            return max_score * 0.75
        elif price_ratio <= 1.0:  # At or slightly below average
            return max_score * 0.625
        elif price_ratio <= 1.1:  # 10% above average
            return max_score * 0.375
        elif price_ratio <= 1.2:  # 20% above average
            return max_score * 0.25
        else:  # More than 20% above average
            return max_score * 0.125

    def _score_features(self, listing: Listing) -> float:
        """Score based on matching user preferences"""
        score = 0.0
        max_score = self.settings.deal_score_weight_features

        features = []

        # Parking
        if self.settings.prefer_parking:
            features.append(('parking', listing.has_parking, 10.0))

        # Balcony
        if self.settings.prefer_balcony:
            features.append(('balcony', listing.has_balcony, 8.0))

        # Elevator
        if self.settings.prefer_elevator:
            features.append(('elevator', listing.has_elevator, 7.0))

        # Mamad
        if self.settings.prefer_mamad:
            features.append(('mamad', listing.has_mamad, 8.0))

        # Top floors preference
        if self.settings.prefer_top_floors and listing.floor and listing.total_floors:
            is_top_half = listing.floor >= (listing.total_floors / 2)
            features.append(('top_floor', is_top_half, 5.0))

        # Calculate weighted score
        total_weight = sum(weight for _, _, weight in features)
        if total_weight > 0:
            for _, has_feature, weight in features:
                if has_feature:
                    score += (weight / total_weight) * max_score

        return score

    def _score_recency(self, listing: Listing) -> float:
        """Score based on how fresh the listing is"""
        max_score = self.settings.deal_score_weight_recency

        if not listing.first_seen:
            return max_score  # New listing, give max score

        days_old = (datetime.utcnow() - listing.first_seen).days

        if days_old == 0:  # Today
            return max_score * 1.0
        elif days_old <= 2:  # 1-2 days
            return max_score * 0.8
        elif days_old <= 5:  # 3-5 days
            return max_score * 0.6
        elif days_old <= 10:  # 6-10 days
            return max_score * 0.4
        elif days_old <= 20:  # 11-20 days
            return max_score * 0.2
        else:  # Over 20 days
            return max_score * 0.067

    def _score_price_trend(self, listing: Listing) -> float:
        """Score based on price changes"""
        max_score = self.settings.deal_score_weight_price_trend
        neutral_score = max_score * 0.333  # 1/3 of max for neutral

        if not listing.price_history or len(listing.price_history) < 2:
            return neutral_score  # Neutral score for no history

        # Get most recent price changes
        sorted_history = sorted(listing.price_history, key=lambda x: x.timestamp, reverse=True)

        if len(sorted_history) < 2:
            return neutral_score

        current_price = sorted_history[0].price
        previous_price = sorted_history[1].price

        if not current_price or not previous_price or previous_price <= 0:
            return neutral_score

        # Calculate price change percentage
        price_change_pct = ((current_price - previous_price) / previous_price) * 100

        # Score based on price drops
        if price_change_pct <= -10:  # 10%+ drop
            return max_score * 1.0
        elif price_change_pct <= -5:  # 5-10% drop
            return max_score * 0.8
        elif price_change_pct <= -2:  # 2-5% drop
            return max_score * 0.6
        elif price_change_pct < 0:  # Any drop
            return max_score * 0.467
        elif price_change_pct == 0:  # No change
            return neutral_score
        else:  # Price increase
            return max_score * 0.133

    def get_price_drop_percentage(self, listing: Listing) -> Optional[float]:
        """Get percentage of price drop if any"""
        if not listing.price_history or len(listing.price_history) < 2:
            return None

        sorted_history = sorted(listing.price_history, key=lambda x: x.timestamp, reverse=True)

        if len(sorted_history) < 2:
            return None

        current_price = sorted_history[0].price
        previous_price = sorted_history[1].price

        if not current_price or not previous_price or previous_price <= 0:
            return None

        return ((previous_price - current_price) / previous_price) * 100


def update_neighborhood_stats(db_session: Session):
    """Update neighborhood statistics from current listings"""

    # Get all active listings grouped by neighborhood
    listings = db_session.query(Listing).filter(
        Listing.price > 0,
        Listing.price_per_sqm > 0
    ).all()

    # Group by city and neighborhood
    neighborhoods = {}
    for listing in listings:
        key = (listing.city, listing.neighborhood)
        if key not in neighborhoods:
            neighborhoods[key] = []
        neighborhoods[key].append(listing)

    # Calculate stats for each neighborhood
    for (city, neighborhood), listing_group in neighborhoods.items():
        if len(listing_group) < 3:  # Need at least 3 samples
            continue

        prices = [l.price for l in listing_group if l.price]
        prices_per_sqm = [l.price_per_sqm for l in listing_group if l.price_per_sqm]

        if not prices_per_sqm:
            continue

        # Get or create stats record
        stats = db_session.query(NeighborhoodStats).filter(
            NeighborhoodStats.city == city,
            NeighborhoodStats.neighborhood == neighborhood
        ).first()

        if not stats:
            stats = NeighborhoodStats(city=city, neighborhood=neighborhood)
            db_session.add(stats)

        # Update stats
        stats.avg_price = statistics.mean(prices)
        stats.avg_price_per_sqm = statistics.mean(prices_per_sqm)
        stats.median_price = statistics.median(prices)
        stats.median_price_per_sqm = statistics.median(prices_per_sqm)
        stats.sample_size = len(listing_group)
        stats.last_updated = datetime.utcnow()

    db_session.commit()
