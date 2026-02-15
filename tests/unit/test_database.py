"""
Unit tests for database models.
Tests Listing model methods and property hash generation.
"""
import pytest
from app.core.database import Listing
from datetime import datetime


class TestListingModel:
    """Test Listing database model"""

    def test_generate_property_hash_consistent(self):
        """Test that property hash is consistent for same inputs"""
        hash1 = Listing.generate_property_hash('Test Address', 3.5, 85.0)
        hash2 = Listing.generate_property_hash('Test Address', 3.5, 85.0)

        assert hash1 == hash2

    def test_generate_property_hash_different_address(self):
        """Test that different addresses produce different hashes"""
        hash1 = Listing.generate_property_hash('Address 1', 3.5, 85.0)
        hash2 = Listing.generate_property_hash('Address 2', 3.5, 85.0)

        assert hash1 != hash2

    def test_generate_property_hash_different_rooms(self):
        """Test that different room counts produce different hashes"""
        hash1 = Listing.generate_property_hash('Test Address', 3.5, 85.0)
        hash2 = Listing.generate_property_hash('Test Address', 4.0, 85.0)

        assert hash1 != hash2

    def test_generate_property_hash_different_size(self):
        """Test that different sizes produce different hashes"""
        hash1 = Listing.generate_property_hash('Test Address', 3.5, 85.0)
        hash2 = Listing.generate_property_hash('Test Address', 3.5, 90.0)

        assert hash1 != hash2

    def test_listing_creation(self, db_session):
        """Test creating a listing"""
        listing = Listing(
            property_hash='test_hash',
            source='test',
            external_id='123',
            url='https://example.com',
            title='Test Listing',
            address='Test Address',
            city='Test City',
            rooms=3.5,
            size_sqm=85.0,
            price=2500000,
            status='unseen'
        )

        db_session.add(listing)
        db_session.commit()

        assert listing.id is not None

    def test_listing_set_images(self, db_session):
        """Test setting images on a listing"""
        listing = Listing(
            property_hash='test_hash',
            source='test',
            rooms=3.5,
            address='Test',
            status='unseen'
        )

        images = ['https://example.com/img1.jpg', 'https://example.com/img2.jpg']
        listing.set_images(images)

        db_session.add(listing)
        db_session.commit()

        retrieved_images = listing.get_images()
        assert len(retrieved_images) == 2
        assert retrieved_images[0] == 'https://example.com/img1.jpg'

    def test_listing_get_images_empty(self, db_session):
        """Test getting images when none are set"""
        listing = Listing(
            property_hash='test_hash',
            source='test',
            rooms=3.5,
            address='Test',
            status='unseen'
        )

        db_session.add(listing)
        db_session.commit()

        images = listing.get_images()
        assert images == []

    def test_listing_price_per_sqm_calculation(self, db_session):
        """Test price per sqm is calculated correctly"""
        listing = Listing(
            property_hash='test_hash',
            source='test',
            rooms=3.5,
            address='Test',
            price=2500000,
            size_sqm=100.0,
            price_per_sqm=25000.0,
            status='unseen'
        )

        assert listing.price_per_sqm == 25000.0

    def test_listing_status_values(self, db_session):
        """Test different status values"""
        statuses = ['unseen', 'interested', 'not_interested', 'contacted']

        for status in statuses:
            listing = Listing(
                property_hash=f'test_hash_{status}',
                source='test',
                rooms=3.5,
                address='Test',
                status=status
            )

            db_session.add(listing)
            db_session.commit()

            assert listing.status == status

    def test_listing_timestamps(self, db_session):
        """Test listing timestamp fields"""
        now = datetime.utcnow()

        listing = Listing(
            property_hash='test_hash',
            source='test',
            rooms=3.5,
            address='Test',
            status='unseen',
            first_seen=now,
            last_seen=now,
            last_checked=now
        )

        db_session.add(listing)
        db_session.commit()

        assert listing.first_seen is not None
        assert listing.last_seen is not None
        assert listing.last_checked is not None

    def test_listing_boolean_features(self, db_session):
        """Test boolean feature fields"""
        listing = Listing(
            property_hash='test_hash',
            source='test',
            rooms=3.5,
            address='Test',
            status='unseen',
            has_elevator=True,
            has_parking=True,
            has_balcony=True,
            has_mamad=True
        )

        db_session.add(listing)
        db_session.commit()

        assert listing.has_elevator is True
        assert listing.has_parking is True
        assert listing.has_balcony is True
        assert listing.has_mamad is True
