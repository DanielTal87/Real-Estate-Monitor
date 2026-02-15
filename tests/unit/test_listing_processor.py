"""
Unit tests for ListingProcessor with parameterized deal score calculations.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from app.core.listing_processor import ListingProcessor
from app.core.deal_score import DealScoreCalculator
from app.core.database import Listing, NeighborhoodStats, PriceHistory


class TestDealScoreCalculation:
    """Test deal score calculation with various apartment scenarios"""

    @pytest.mark.parametrize("scenario,listing_data,neighborhood_avg,expected_score_range", [
        # Scenario 1: Under-priced apartment with all features
        (
            "under_priced_with_features",
            {
                'price_per_sqm': 21000,  # 30% below average
                'has_parking': True,
                'has_balcony': True,
                'has_elevator': True,
                'has_mamad': True,
                'floor': 4,
                'total_floors': 5,
                'first_seen': datetime.utcnow(),  # Fresh listing
                'price_history': []
            },
            30000,  # Neighborhood average
            (85, 100)  # Expected high score
        ),
        # Scenario 2: Over-priced apartment with missing features
        (
            "over_priced_no_features",
            {
                'price_per_sqm': 42000,  # 40% above average
                'has_parking': False,
                'has_balcony': False,
                'has_elevator': False,
                'has_mamad': False,
                'floor': 0,  # Ground floor
                'total_floors': 5,
                'first_seen': datetime.utcnow() - timedelta(days=30),  # Old listing
                'price_history': []
            },
            30000,
            (0, 25)  # Expected low score
        ),
        # Scenario 3: Average price with some features
        (
            "average_price_some_features",
            {
                'price_per_sqm': 30000,  # At average
                'has_parking': True,
                'has_balcony': True,
                'has_elevator': False,
                'has_mamad': False,
                'floor': 2,
                'total_floors': 4,
                'first_seen': datetime.utcnow() - timedelta(days=5),
                'price_history': []
            },
            30000,
            (40, 65)  # Expected medium score
        ),
        # Scenario 4: Good price (price drop tested separately)
        (
            "good_price_recent",
            {
                'price_per_sqm': 27000,  # 10% below average
                'has_parking': True,
                'has_balcony': True,
                'has_elevator': True,
                'has_mamad': True,
                'floor': 3,
                'total_floors': 5,
                'first_seen': datetime.utcnow() - timedelta(days=2),
                'price_history': []
            },
            30000,
            (70, 90)  # Expected high score
        ),
        # Scenario 5: Missing neighborhood data (neutral scoring)
        (
            "no_neighborhood_data",
            {
                'price_per_sqm': 28000,
                'has_parking': True,
                'has_balcony': False,
                'has_elevator': True,
                'has_mamad': False,
                'floor': 2,
                'total_floors': 4,
                'first_seen': datetime.utcnow() - timedelta(days=2),
                'price_history': []
            },
            None,  # No neighborhood data
            (45, 70)  # Expected medium score with neutral price component
        ),
    ])
    def test_calculate_score_scenarios(
        self,
        db_session,
        test_settings,
        scenario,
        listing_data,
        neighborhood_avg,
        expected_score_range
    ):
        """Test deal score calculation with various apartment scenarios"""
        # Create neighborhood stats if provided
        if neighborhood_avg:
            stats = NeighborhoodStats(
                city='תל אביב',
                neighborhood='פלורנטין',
                avg_price=neighborhood_avg * 85,  # Assuming 85 sqm
                avg_price_per_sqm=neighborhood_avg,
                median_price=neighborhood_avg * 85,
                median_price_per_sqm=neighborhood_avg,
                sample_size=20,
                last_updated=datetime.utcnow()
            )
            db_session.add(stats)
            db_session.commit()

        # Create listing
        listing = Listing(
            property_hash='test_hash_' + scenario,
            source='yad2',
            external_id=scenario,
            url=f'https://example.com/{scenario}',
            title=f'Test Listing - {scenario}',
            description='Test description',
            address='רחוב הרצל, פלורנטין, תל אביב',
            city='תל אביב',
            neighborhood='פלורנטין',
            street='רחוב הרצל',
            rooms=3.5,
            size_sqm=85.0,
            floor=listing_data['floor'],
            total_floors=listing_data['total_floors'],
            price=listing_data['price_per_sqm'] * 85,
            price_per_sqm=listing_data['price_per_sqm'],
            has_elevator=listing_data['has_elevator'],
            has_parking=listing_data['has_parking'],
            has_balcony=listing_data['has_balcony'],
            has_mamad=listing_data.get('has_mamad', False),
            contact_name='Test Contact',
            contact_phone='0501234567',
            first_seen=listing_data['first_seen'],
            last_seen=datetime.utcnow(),
            last_checked=datetime.utcnow(),
            status='unseen',
            deal_score=0.0
        )

        # Add price history if provided
        if listing_data.get('price_history'):
            listing.price_history = listing_data['price_history']

        db_session.add(listing)
        db_session.commit()
        db_session.refresh(listing)

        # Calculate score
        calculator = DealScoreCalculator(db_session)
        score = calculator.calculate_score(listing)

        # Verify score is in expected range
        min_score, max_score = expected_score_range
        assert min_score <= score <= max_score, (
            f"Scenario '{scenario}': Score {score:.1f} not in expected range "
            f"[{min_score}, {max_score}]"
        )

        # Verify score is valid
        assert 0 <= score <= 100, f"Score {score} is out of valid range [0, 100]"


class TestDeduplication:
    """Test deduplication logic"""

    def test_deduplicate_by_property_hash(self, db_session, test_settings):
        """Test that duplicate listings are detected by property hash"""
        # Use test_settings to ensure filters pass
        processor = ListingProcessor(db_session)

        # Create first listing that passes filters
        # test_settings has cities="תל אביב,Tel Aviv,Ramat Gan"
        listing_data_1 = {
            'source': 'yad2',
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירת 3 חדרים',
            'description': 'דירה יפה',
            'address': 'רחוב הרצל 10, תל אביב',
            'city': 'Tel Aviv',  # Match test_settings cities
            'neighborhood': 'פלורנטין',
            'street': 'רחוב הרצל',
            'rooms': 3.5,  # Above min_rooms (3.0)
            'size_sqm': 80.0,  # Above min_size_sqm (70)
            'floor': 2,
            'total_floors': 4,
            'price': 2500000,  # Below max_price (3000000)
            'price_per_sqm': 31250,
            'has_elevator': True,
            'has_parking': True,
            'has_balcony': True,
            'contact_name': 'Test',
            'contact_phone': '0501234567'
        }

        stats = processor.process_listings([listing_data_1], 'yad2')
        assert stats['new'] == 1, f"Expected 1 new listing, got stats: {stats}"
        assert stats['duplicates'] == 0

        # Try to add same listing again (different external_id but same property)
        listing_data_2 = listing_data_1.copy()
        listing_data_2['external_id'] = '67890'
        listing_data_2['url'] = 'https://www.yad2.co.il/item/67890'

        stats = processor.process_listings([listing_data_2], 'yad2')
        assert stats['new'] == 0
        assert stats['duplicates'] == 1

    def test_deduplicate_by_phone(self, db_session, test_settings):
        """Test that duplicate listings are detected by phone number"""
        processor = ListingProcessor(db_session)

        # Create first listing that passes filters
        listing_data_1 = {
            'source': 'yad2',
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירת 3 חדרים',
            'description': 'דירה יפה',
            'address': 'רחוב הרצל 10, תל אביב',
            'city': 'Tel Aviv',  # Match test_settings cities
            'neighborhood': 'פלורנטין',
            'street': 'רחוב הרצל',
            'rooms': 3.5,  # Above min_rooms
            'size_sqm': 80.0,  # Above min_size_sqm
            'floor': 2,
            'total_floors': 4,
            'price': 2500000,  # Below max_price
            'price_per_sqm': 31250,
            'has_elevator': True,
            'has_parking': True,
            'has_balcony': True,
            'contact_name': 'Test',
            'contact_phone': '050-123-4567'  # With dashes
        }

        stats = processor.process_listings([listing_data_1], 'yad2')
        assert stats['new'] == 1, f"Expected 1 new listing, got stats: {stats}"

        # Try to add listing with same phone (different format) but different address
        listing_data_2 = listing_data_1.copy()
        listing_data_2['external_id'] = '67890'
        listing_data_2['url'] = 'https://www.yad2.co.il/item/67890'
        listing_data_2['address'] = 'רחוב אחר 20, תל אביב'
        listing_data_2['contact_phone'] = '0501234567'  # Without dashes

        stats = processor.process_listings([listing_data_2], 'yad2')
        # Should be detected as duplicate due to same phone
        assert stats['duplicates'] >= 1

    def test_price_drop_detection(self, db_session, test_settings):
        """Test that price drops are properly detected and tracked"""
        processor = ListingProcessor(db_session)

        # Create initial listing that passes filters
        listing_data = {
            'source': 'yad2',
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירת 3 חדרים',
            'description': 'דירה יפה',
            'address': 'רחוב הרצל 10, תל אביב',
            'city': 'Tel Aviv',  # Match test_settings cities
            'neighborhood': 'פלורנטין',
            'street': 'רחוב הרצל',
            'rooms': 3.5,  # Above min_rooms
            'size_sqm': 80.0,  # Above min_size_sqm
            'floor': 2,
            'total_floors': 4,
            'price': 2900000,  # Below max_price
            'price_per_sqm': 36250,
            'has_elevator': True,
            'has_parking': True,
            'has_balcony': True,
            'contact_name': 'Test',
            'contact_phone': '0501234567'
        }

        stats = processor.process_listings([listing_data], 'yad2')
        assert stats['new'] == 1, f"Expected 1 new listing, got stats: {stats}"

        # Update with price drop (about 7% drop)
        listing_data['price'] = 2700000
        listing_data['price_per_sqm'] = 33750

        stats = processor.process_listings([listing_data], 'yad2')
        assert stats['price_drops'] == 1

        # Verify price history was created
        listing = db_session.query(Listing).filter_by(external_id='12345').first()
        assert listing is not None
        assert len(listing.price_history) == 2
        assert listing.price == 2700000


class TestListingFiltering:
    """Test listing filtering logic"""

    def test_filter_by_price(self, db_session, test_settings):
        """Test that listings above max price are filtered"""
        processor = ListingProcessor(db_session)

        listing_data = {
            'source': 'yad2',
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירת 3 חדרים',
            'description': 'דירה יפה',
            'address': 'רחוב הרצל 10, תל אביב',
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'street': 'רחוב הרצל',
            'rooms': 3.0,
            'size_sqm': 80.0,
            'floor': 2,
            'total_floors': 4,
            'price': 5000000,  # Above max_price (3000000)
            'price_per_sqm': 62500,
            'has_elevator': True,
            'has_parking': True,
            'has_balcony': True,
            'contact_name': 'Test',
            'contact_phone': '0501234567'
        }

        stats = processor.process_listings([listing_data], 'yad2')
        assert stats['filtered'] == 1
        assert stats['new'] == 0

    def test_filter_by_rooms(self, db_session, test_settings):
        """Test that listings below min rooms are filtered"""
        processor = ListingProcessor(db_session)

        listing_data = {
            'source': 'yad2',
            'external_id': '12345',
            'url': 'https://www.yad2.co.il/item/12345',
            'title': 'דירת 2 חדרים',
            'description': 'דירה קטנה',
            'address': 'רחוב הרצל 10, תל אביב',
            'city': 'תל אביב',
            'neighborhood': 'פלורנטין',
            'street': 'רחוב הרצל',
            'rooms': 2.0,  # Below min_rooms (3.0 in test_settings)
            'size_sqm': 60.0,
            'floor': 2,
            'total_floors': 4,
            'price': 2000000,
            'price_per_sqm': 33333,
            'has_elevator': True,
            'has_parking': True,
            'has_balcony': True,
            'contact_name': 'Test',
            'contact_phone': '0501234567'
        }

        stats = processor.process_listings([listing_data], 'yad2')
        assert stats['filtered'] == 1
        assert stats['new'] == 0
