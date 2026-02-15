"""
Unit tests for ListingProcessor and DealScoreCalculator.
Tests deal scoring logic, listing processing, and deduplication.
"""
import pytest
from datetime import datetime, timedelta
from app.core.listing_processor import ListingProcessor
from app.core.deal_score import DealScoreCalculator
from app.core.database import Listing, NeighborhoodStats, PriceHistory


class TestDealScoreCalculator:
    """Test deal score calculation logic"""

    @pytest.mark.parametrize("listing_data,expected_score_range,description", [
        # Perfect Deal: Low price, high sqm, all features
        ({
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'price': 2000000,
            'size_sqm': 100.0,
            'price_per_sqm': 20000,  # 37.5% below average (32000)
            'has_parking': True,
            'has_balcony': True,
            'has_elevator': True,
            'has_mamad': True,
            'floor': 4,
            'total_floors': 5,
            'first_seen': datetime.utcnow(),
        }, (80, 100), "Perfect Deal - Low price, all features"),

        # Bad Deal: High price, low sqm, no features
        ({
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'price': 4000000,
            'size_sqm': 80.0,
            'price_per_sqm': 50000,  # 56% above average (32000)
            'has_parking': False,
            'has_balcony': False,
            'has_elevator': False,
            'has_mamad': False,
            'floor': 1,
            'total_floors': 5,
            'first_seen': datetime.utcnow() - timedelta(days=30),
        }, (0, 20), "Bad Deal - High price, no features"),

        # Average Deal: Market price, some features
        ({
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'price': 2720000,
            'size_sqm': 85.0,
            'price_per_sqm': 32000,  # Exactly average
            'has_parking': True,
            'has_balcony': True,
            'has_elevator': False,
            'has_mamad': False,
            'floor': 2,
            'total_floors': 5,
            'first_seen': datetime.utcnow() - timedelta(days=5),
        }, (35, 55), "Average Deal - Market price, some features"),

        # Good Deal: Below market, good features
        ({
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'price': 2400000,
            'size_sqm': 90.0,
            'price_per_sqm': 26666,  # ~17% below average
            'has_parking': True,
            'has_balcony': True,
            'has_elevator': True,
            'has_mamad': True,
            'floor': 3,
            'total_floors': 5,
            'first_seen': datetime.utcnow() - timedelta(days=1),
        }, (60, 80), "Good Deal - Below market, good features"),

        # No neighborhood data - should get neutral score
        ({
            'city': 'Unknown City',
            'neighborhood': 'Unknown',
            'price': 2500000,
            'size_sqm': 85.0,
            'price_per_sqm': 29411,
            'has_parking': True,
            'has_balcony': False,
            'has_elevator': True,
            'has_mamad': False,
            'floor': 2,
            'total_floors': 4,
            'first_seen': datetime.utcnow(),
        }, (30, 50), "No neighborhood data - neutral score"),
    ])
    def test_deal_score_scenarios(self, db_session, sample_neighborhood_stats,
                                   listing_data, expected_score_range, description):
        """Test deal score calculation with various scenarios"""
        # Create listing
        listing = Listing(
            property_hash=Listing.generate_property_hash(
                f"{listing_data.get('city', 'Test')}, Test St",
                3.5,
                listing_data['size_sqm']
            ),
            source='test',
            external_id='test123',
            city=listing_data['city'],
            neighborhood=listing_data['neighborhood'],
            price=listing_data['price'],
            size_sqm=listing_data['size_sqm'],
            price_per_sqm=listing_data['price_per_sqm'],
            has_parking=listing_data.get('has_parking', False),
            has_balcony=listing_data.get('has_balcony', False),
            has_elevator=listing_data.get('has_elevator', False),
            has_mamad=listing_data.get('has_mamad', False),
            floor=listing_data.get('floor'),
            total_floors=listing_data.get('total_floors'),
            first_seen=listing_data['first_seen'],
            rooms=3.5,
            address='Test Address',
            status='unseen'
        )

        # Calculate score
        calculator = DealScoreCalculator(db_session)
        score = calculator.calculate_score(listing)

        # Verify score is in expected range
        min_score, max_score = expected_score_range
        assert min_score <= score <= max_score, (
            f"{description}: Expected score between {min_score}-{max_score}, got {score:.1f}"
        )

    def test_price_competitiveness_scoring(self, db_session, sample_neighborhood_stats):
        """Test price competitiveness component of scoring"""
        calculator = DealScoreCalculator(db_session)

        # Test listing 30% below average (should get max 40 points)
        listing = Listing(
            property_hash='test_hash',
            city='תל אביב',
            neighborhood='פלורנטין',
            price=1900000,
            size_sqm=85.0,
            price_per_sqm=22353,  # ~30% below 32000
            rooms=3.5,
            address='Test',
            status='unseen'
        )

        score = calculator._score_price_competitiveness(listing)
        assert 35 <= score <= 40, f"Expected ~40 points for 30% below market, got {score}"

    def test_features_scoring(self, db_session, test_settings):
        """Test feature matching component of scoring"""
        calculator = DealScoreCalculator(db_session)

        # Listing with all preferred features
        listing_all_features = Listing(
            property_hash='test_hash',
            has_parking=True,
            has_balcony=True,
            has_elevator=True,
            has_mamad=True,
            floor=4,
            total_floors=5,
            rooms=3.5,
            address='Test',
            status='unseen'
        )

        score_all = calculator._score_features(listing_all_features)
        assert score_all == 30.0, f"Expected max 30 points for all features, got {score_all}"

        # Listing with no features
        listing_no_features = Listing(
            property_hash='test_hash2',
            has_parking=False,
            has_balcony=False,
            has_elevator=False,
            has_mamad=False,
            floor=1,
            total_floors=5,
            rooms=3.5,
            address='Test',
            status='unseen'
        )

        score_none = calculator._score_features(listing_no_features)
        assert score_none == 0.0, f"Expected 0 points for no features, got {score_none}"

    def test_recency_scoring(self, db_session):
        """Test recency component of scoring"""
        calculator = DealScoreCalculator(db_session)

        # Brand new listing (today)
        listing_new = Listing(
            property_hash='test_hash',
            first_seen=datetime.utcnow(),
            rooms=3.5,
            address='Test',
            status='unseen'
        )
        score_new = calculator._score_recency(listing_new)
        assert score_new == 15.0, f"Expected 15 points for new listing, got {score_new}"

        # Old listing (30 days)
        listing_old = Listing(
            property_hash='test_hash2',
            first_seen=datetime.utcnow() - timedelta(days=30),
            rooms=3.5,
            address='Test',
            status='unseen'
        )
        score_old = calculator._score_recency(listing_old)
        assert score_old <= 3.0, f"Expected <=3 points for old listing, got {score_old}"

    def test_price_trend_scoring(self, db_session):
        """Test price trend component of scoring"""
        calculator = DealScoreCalculator(db_session)

        # Create listing with price history
        listing = Listing(
            property_hash='test_hash',
            price=2000000,
            rooms=3.5,
            address='Test',
            status='unseen',
            first_seen=datetime.utcnow() - timedelta(days=10)
        )
        db_session.add(listing)
        db_session.commit()

        # Add price history showing 10% drop
        old_price = PriceHistory(
            listing_id=listing.id,
            price=2222222,
            timestamp=datetime.utcnow() - timedelta(days=5)
        )
        new_price = PriceHistory(
            listing_id=listing.id,
            price=2000000,
            timestamp=datetime.utcnow()
        )
        db_session.add(old_price)
        db_session.add(new_price)
        db_session.commit()
        db_session.refresh(listing)

        score = calculator._score_price_trend(listing)
        assert score >= 12.0, f"Expected >=12 points for 10% price drop, got {score}"


class TestListingProcessor:
    """Test listing processing and deduplication logic"""

    def test_process_new_listing(self, db_session, sample_listing_data):
        """Test processing a completely new listing"""
        processor = ListingProcessor(db_session)

        result = processor.process_single_listing(sample_listing_data, 'yad2')

        assert result == 'new', "Should create new listing"

        # Verify listing was created
        listing = db_session.query(Listing).filter_by(external_id='12345').first()
        assert listing is not None
        assert listing.title == sample_listing_data['title']
        assert listing.price == sample_listing_data['price']
        assert listing.deal_score > 0  # Should have calculated score

    def test_process_duplicate_listing(self, db_session, sample_listing, sample_listing_data):
        """Test processing a duplicate listing (no changes)"""
        processor = ListingProcessor(db_session)

        result = processor.process_single_listing(sample_listing_data, 'yad2')

        assert result == 'duplicates', "Should detect duplicate"

        # Verify only one listing exists
        count = db_session.query(Listing).filter_by(external_id='12345').count()
        assert count == 1

    def test_process_price_change(self, db_session, sample_listing, sample_listing_data):
        """Test processing a listing with price change"""
        processor = ListingProcessor(db_session)

        # Modify price
        new_data = sample_listing_data.copy()
        new_data['price'] = 2300000  # Price drop from 2,500,000

        result = processor.process_single_listing(new_data, 'yad2')

        assert result == 'price_drops', "Should detect price drop"

        # Verify price was updated
        db_session.refresh(sample_listing)
        assert sample_listing.price == 2300000

        # Verify price history was created
        assert len(sample_listing.price_history) > 0

    def test_process_filtered_listing(self, db_session, sample_listing_data):
        """Test that listings outside criteria are filtered"""
        processor = ListingProcessor(db_session)

        # Create listing that exceeds max price
        expensive_data = sample_listing_data.copy()
        expensive_data['price'] = 10000000  # Way over max_price

        result = processor.process_single_listing(expensive_data, 'yad2')

        assert result == 'filtered', "Should filter expensive listing"

        # Verify listing was NOT created
        listing = db_session.query(Listing).filter_by(price=10000000).first()
        assert listing is None

    def test_batch_processing(self, db_session, sample_listing_data):
        """Test batch processing of multiple listings"""
        processor = ListingProcessor(db_session)

        # Create batch of listings
        listings = [
            sample_listing_data.copy(),
            {**sample_listing_data, 'external_id': '12346', 'price': 2600000},
            {**sample_listing_data, 'external_id': '12347', 'price': 2700000},
        ]

        stats = processor.process_listings(listings, 'yad2')

        assert stats['new'] == 3, "Should create 3 new listings"
        assert stats['duplicates'] == 0
        assert stats['filtered'] == 0

    def test_phone_normalization(self, db_session, sample_listing_data):
        """Test that phone numbers are normalized"""
        processor = ListingProcessor(db_session)

        # Test with various phone formats
        test_data = sample_listing_data.copy()
        test_data['contact_phone'] = '050-123-4567'

        processor.process_single_listing(test_data, 'yad2')

        listing = db_session.query(Listing).filter_by(external_id='12345').first()
        assert listing.contact_phone == '0501234567', "Phone should be normalized"

    def test_deal_score_calculation_on_create(self, db_session, sample_listing_data,
                                              sample_neighborhood_stats):
        """Test that deal score is calculated when creating listing"""
        processor = ListingProcessor(db_session)

        processor.process_single_listing(sample_listing_data, 'yad2')

        listing = db_session.query(Listing).filter_by(external_id='12345').first()
        assert listing.deal_score > 0, "Deal score should be calculated"
        assert listing.deal_score <= 100, "Deal score should not exceed 100"

    def test_deal_score_recalculation_on_update(self, db_session, sample_listing,
                                                sample_listing_data, sample_neighborhood_stats):
        """Test that deal score is recalculated when listing is updated"""
        processor = ListingProcessor(db_session)

        original_score = sample_listing.deal_score

        # Update with lower price (should increase score)
        updated_data = sample_listing_data.copy()
        updated_data['price'] = 2000000  # Significant price drop

        processor.process_single_listing(updated_data, 'yad2')

        db_session.refresh(sample_listing)
        assert sample_listing.deal_score != original_score, "Score should be recalculated"
