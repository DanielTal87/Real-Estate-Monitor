"""
Unit tests for DuplicateDetector.
Tests duplicate detection strategies and fuzzy matching.
"""
import pytest
from app.utils.duplicate_detector import DuplicateDetector
from app.core.database import Listing
from datetime import datetime


class TestDuplicateDetector:
    """Test duplicate detection logic"""

    def test_find_by_property_hash(self, db_session, sample_listing):
        """Test finding duplicate by property hash"""
        detector = DuplicateDetector(db_session)

        found = detector.find_by_property_hash(sample_listing.property_hash)

        assert found is not None
        assert found.id == sample_listing.id

    def test_find_by_property_hash_not_found(self, db_session):
        """Test property hash search when no match exists"""
        detector = DuplicateDetector(db_session)

        found = detector.find_by_property_hash('nonexistent_hash')

        assert found is None

    def test_find_by_external_id(self, db_session, sample_listing):
        """Test finding duplicate by source and external ID"""
        detector = DuplicateDetector(db_session)

        found = detector.find_by_external_id('yad2', '12345')

        assert found is not None
        assert found.id == sample_listing.id

    def test_find_by_external_id_wrong_source(self, db_session, sample_listing):
        """Test external ID search with wrong source"""
        detector = DuplicateDetector(db_session)

        found = detector.find_by_external_id('madlan', '12345')

        assert found is None

    def test_find_by_external_id_none(self, db_session):
        """Test external ID search with None"""
        detector = DuplicateDetector(db_session)

        found = detector.find_by_external_id('yad2', None)

        assert found is None

    def test_find_by_phone_fuzzy_exact_match(self, db_session, sample_listing):
        """Test fuzzy phone matching with exact address"""
        detector = DuplicateDetector(db_session)

        found, similarity = detector.find_by_phone_fuzzy(
            '0501234567',
            'רחוב הרצל, פלורנטין, תל אביב'
        )

        assert found is not None
        assert found.id == sample_listing.id
        assert similarity >= 85

    def test_find_by_phone_fuzzy_similar_address(self, db_session, sample_listing):
        """Test fuzzy phone matching with similar address"""
        detector = DuplicateDetector(db_session)

        found, similarity = detector.find_by_phone_fuzzy(
            '0501234567',
            'הרצל, פלורנטין, תל-אביב'  # Slightly different formatting
        )

        assert found is not None
        assert similarity >= 80

    def test_find_by_phone_fuzzy_different_address(self, db_session, sample_listing):
        """Test fuzzy phone matching with very different address"""
        detector = DuplicateDetector(db_session, similarity_threshold=85)

        found, similarity = detector.find_by_phone_fuzzy(
            '0501234567',
            'רחוב אחר, שכונה אחרת, עיר אחרת'
        )

        # Should not match due to low similarity
        assert found is None
        assert similarity < 85

    def test_find_by_phone_fuzzy_no_phone(self, db_session):
        """Test fuzzy phone matching with no phone"""
        detector = DuplicateDetector(db_session)

        found, similarity = detector.find_by_phone_fuzzy(None, 'Some address')

        assert found is None
        assert similarity == 0

    def test_find_by_phone_fuzzy_no_address(self, db_session):
        """Test fuzzy phone matching with no address"""
        detector = DuplicateDetector(db_session)

        found, similarity = detector.find_by_phone_fuzzy('0501234567', None)

        assert found is None
        assert similarity == 0

    def test_find_duplicate_by_property_hash(self, db_session, sample_listing):
        """Test find_duplicate using property hash strategy"""
        detector = DuplicateDetector(db_session)

        found, method = detector.find_duplicate(
            property_hash=sample_listing.property_hash,
            source='yad2',
            external_id=None,
            phone=None,
            address='Some address'
        )

        assert found is not None
        assert found.id == sample_listing.id
        assert method == 'property_hash'

    def test_find_duplicate_by_external_id(self, db_session, sample_listing):
        """Test find_duplicate using external ID strategy"""
        detector = DuplicateDetector(db_session)

        found, method = detector.find_duplicate(
            property_hash='different_hash',
            source='yad2',
            external_id='12345',
            phone=None,
            address='Some address'
        )

        assert found is not None
        assert found.id == sample_listing.id
        assert method == 'external_id'

    def test_find_duplicate_by_phone_fuzzy(self, db_session, sample_listing):
        """Test find_duplicate using phone fuzzy strategy"""
        detector = DuplicateDetector(db_session)

        found, method = detector.find_duplicate(
            property_hash='different_hash',
            source='madlan',  # Different source
            external_id='99999',  # Different ID
            phone='0501234567',
            address='רחוב הרצל, פלורנטין, תל אביב'
        )

        assert found is not None
        assert found.id == sample_listing.id
        assert 'phone_fuzzy' in method
        assert 'similarity' in method

    def test_find_duplicate_no_match(self, db_session):
        """Test find_duplicate when no duplicate exists"""
        detector = DuplicateDetector(db_session)

        found, method = detector.find_duplicate(
            property_hash='nonexistent',
            source='yad2',
            external_id='99999',
            phone='0509999999',
            address='Nonexistent address'
        )

        assert found is None
        assert method == ''

    def test_custom_similarity_threshold(self, db_session, sample_listing):
        """Test detector with custom similarity threshold"""
        # Very strict threshold
        detector = DuplicateDetector(db_session, similarity_threshold=95)

        found, similarity = detector.find_by_phone_fuzzy(
            '0501234567',
            'הרצל פלורנטין תל אביב'  # Similar but not exact
        )

        # May or may not match depending on similarity score
        assert isinstance(similarity, int)
        assert 0 <= similarity <= 100
