"""
Unit tests for dashboard service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.dashboard import (
    app,
    format_price,
    days_ago,
    get_whatsapp_url,
    get_db
)
from app.core.database import Listing, NeighborhoodStats


@pytest.fixture
def test_client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Create mock database session"""
    return Mock(spec=Session)


class TestHelperFunctions:
    """Test template helper functions"""

    def test_format_price_with_value(self):
        """Test price formatting with valid value"""
        assert format_price(5000) == "₪5,000"
        assert format_price(10000.5) == "₪10,000"
        assert format_price(1234567) == "₪1,234,567"

    def test_format_price_none(self):
        """Test price formatting with None"""
        assert format_price(None) == "N/A"

    def test_days_ago_just_now(self):
        """Test days_ago for recent times"""
        now = datetime.utcnow()
        assert days_ago(now) == "Just now"

    def test_days_ago_minutes(self):
        """Test days_ago for minutes"""
        time = datetime.utcnow() - timedelta(minutes=30)
        result = days_ago(time)
        assert "minutes ago" in result

    def test_days_ago_hours(self):
        """Test days_ago for hours"""
        time = datetime.utcnow() - timedelta(hours=3)
        result = days_ago(time)
        assert "hours ago" in result

    def test_days_ago_yesterday(self):
        """Test days_ago for yesterday"""
        time = datetime.utcnow() - timedelta(days=1)
        assert days_ago(time) == "Yesterday"

    def test_days_ago_days(self):
        """Test days_ago for days"""
        time = datetime.utcnow() - timedelta(days=3)
        result = days_ago(time)
        assert "days ago" in result

    def test_days_ago_weeks(self):
        """Test days_ago for weeks"""
        time = datetime.utcnow() - timedelta(days=14)
        result = days_ago(time)
        assert "weeks ago" in result

    def test_days_ago_months(self):
        """Test days_ago for months"""
        time = datetime.utcnow() - timedelta(days=60)
        result = days_ago(time)
        assert "months ago" in result

    def test_days_ago_none(self):
        """Test days_ago with None"""
        assert days_ago(None) == "Unknown"

    def test_get_whatsapp_url_valid(self):
        """Test WhatsApp URL generation"""
        url = get_whatsapp_url("0501234567", "Test St, Tel Aviv", "yad2")
        assert url is not None
        assert "wa.me" in url
        assert "+972501234567" in url
        assert "Test%20St" in url

    def test_get_whatsapp_url_with_country_code(self):
        """Test WhatsApp URL with existing country code"""
        url = get_whatsapp_url("+972501234567", "Test St", "yad2")
        assert "+972501234567" in url

    def test_get_whatsapp_url_none(self):
        """Test WhatsApp URL with no phone"""
        assert get_whatsapp_url(None, "Test St", "yad2") is None
        assert get_whatsapp_url("", "Test St", "yad2") is None


class TestDashboardEndpoints:
    """Test dashboard API endpoints"""

    @patch('app.services.dashboard.get_db')
    def test_index_page(self, mock_get_db, test_client):
        """Test main dashboard page"""
        # Setup mock
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        mock_query.distinct.return_value = mock_query
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=False)

        # Make request
        response = test_client.get("/")
        assert response.status_code == 200

    @patch('app.services.dashboard.get_db')
    def test_index_with_filters(self, mock_get_db, test_client):
        """Test dashboard with filters"""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        mock_query.distinct.return_value = mock_query
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=False)

        response = test_client.get("/?status=interested&min_score=80&max_price=5000")
        assert response.status_code == 200

    def test_listing_detail_found(self, test_client):
        """Test listing detail page"""
        from app.services.dashboard import app, get_db

        def override_get_db():
            mock_db = Mock()
            mock_listing = Mock(spec=Listing)
            mock_listing.id = 1
            mock_listing.city = "Tel Aviv"
            mock_listing.neighborhood = "Center"
            mock_listing.price_history = []

            # Mock the query for NeighborhoodStats
            def query_side_effect(model):
                mock_query = Mock()
                mock_query.filter.return_value = mock_query
                if model == Listing:
                    mock_query.first.return_value = mock_listing
                else:  # NeighborhoodStats
                    mock_query.first.return_value = None
                return mock_query

            mock_db.query.side_effect = query_side_effect

            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        response = test_client.get("/listing/1")
        app.dependency_overrides.clear()

        assert response.status_code == 200

    def test_listing_detail_not_found(self, test_client):
        """Test listing detail page with non-existent listing"""
        from app.services.dashboard import app, get_db

        def override_get_db():
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = None
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        response = test_client.get("/listing/999")
        app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_update_listing_status(self, test_client):
        """Test updating listing status"""
        from app.services.dashboard import app, get_db

        def override_get_db():
            mock_db = Mock()
            mock_listing = Mock(spec=Listing)
            mock_listing.id = 1

            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_listing
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        response = test_client.post("/api/listing/1/status?status=interested&note=Test note")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "interested"

    def test_update_listing_status_invalid(self, test_client):
        """Test updating listing with invalid status"""
        response = test_client.post("/api/listing/1/status?status=invalid_status")
        assert response.status_code == 400

    @patch('app.services.dashboard.get_db')
    def test_get_stats(self, mock_get_db, test_client):
        """Test stats endpoint"""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.scalar.return_value = 5000.0
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [("unseen", 5), ("interested", 3)]
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=False)

        response = test_client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_listings" in data
        assert "new_today" in data

    @patch('app.services.dashboard.get_db')
    def test_get_neighborhood_stats(self, mock_get_db, test_client):
        """Test neighborhood stats endpoint"""
        mock_db = Mock()
        mock_stats = Mock(spec=NeighborhoodStats)
        mock_stats.city = "Tel Aviv"
        mock_stats.neighborhood = "Center"
        mock_stats.avg_price = 5000
        mock_stats.avg_price_per_sqm = 100
        mock_stats.median_price = 4800
        mock_stats.median_price_per_sqm = 95
        mock_stats.sample_size = 50

        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_stats]
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=False)

        response = test_client.get("/api/neighborhood-stats?city=Tel Aviv")
        assert response.status_code == 200
        data = response.json()
        assert "neighborhoods" in data

    def test_get_price_history(self, test_client):
        """Test price history endpoint"""
        from app.services.dashboard import app, get_db

        def override_get_db():
            mock_db = Mock()
            mock_listing = Mock(spec=Listing)
            mock_listing.id = 1

            mock_history = Mock()
            mock_history.timestamp = datetime.utcnow()
            mock_history.price = 5000
            mock_history.price_per_sqm = 100
            mock_listing.price_history = [mock_history]

            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_listing
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        response = test_client.get("/api/price-history/1")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "listing_id" in data
        assert "history" in data

    @patch('app.services.dashboard.get_db')
    def test_health_check(self, mock_get_db, test_client):
        """Test health check endpoint"""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.all.return_value = []
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=False)

        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @patch('app.scrapers.base_scraper.captcha_state')
    def test_api_health_check(self, mock_captcha_state, test_client):
        """Test API health check endpoint"""
        from app.services.dashboard import app, get_db

        def override_get_db():
            mock_db = Mock()
            mock_query = Mock()
            mock_db.query.return_value = mock_query
            mock_query.all.return_value = []
            yield mock_db

        mock_captcha_state.is_waiting.return_value = False
        mock_captcha_state.get_status.return_value = {"status": "NORMAL"}

        app.dependency_overrides[get_db] = override_get_db
        response = test_client.get("/api/health")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "is_blocked" in data
        assert "captcha_state" in data

    @patch('app.scrapers.base_scraper.captcha_state')
    def test_get_scraper_status(self, mock_captcha_state, test_client):
        """Test scraper status endpoint"""
        mock_captcha_state.get_status.return_value = {"status": "NORMAL"}
        mock_captcha_state.is_waiting.return_value = False

        response = test_client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "captcha" in data
        assert "is_paused" in data

    @patch('app.services.dashboard.get_db')
    def test_database_stats(self, mock_get_db, test_client):
        """Test database stats endpoint"""
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = Mock(return_value=False)

        response = test_client.get("/api/db-stats")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert "scrapers" in data
        assert "timestamp" in data
