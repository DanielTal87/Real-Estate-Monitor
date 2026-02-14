"""Duplicate detection utilities for real estate listings"""

from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fuzzywuzzy import fuzz

from app.core.database import Listing


class DuplicateDetector:
    """
    Detect duplicate listings across different sources.

    Uses multiple strategies:
    1. Exact property hash matching (address + rooms + size)
    2. Source + external ID matching
    3. Fuzzy phone number + address matching
    """

    def __init__(self, db_session: Session, similarity_threshold: int = 85):
        """
        Initialize duplicate detector.

        Args:
            db_session: SQLAlchemy database session
            similarity_threshold: Minimum similarity score (0-100) for fuzzy matching
        """
        self.db = db_session
        self.similarity_threshold = similarity_threshold

    def find_by_property_hash(self, property_hash: str) -> Optional[Listing]:
        """
        Find listing by property hash (exact match).

        Property hash is generated from address, rooms, and size.
        This catches exact duplicates across different sources.

        Args:
            property_hash: SHA256 hash of property characteristics

        Returns:
            Matching Listing or None
        """
        return self.db.query(Listing).filter(
            Listing.property_hash == property_hash
        ).first()

    def find_by_external_id(self, source: str, external_id: str) -> Optional[Listing]:
        """
        Find listing by source and external ID.

        Each source (yad2, madlan, facebook) has its own listing IDs.
        This catches re-scraping of the same listing from the same source.

        Args:
            source: Source name (e.g., 'yad2', 'madlan')
            external_id: Listing ID from the source site

        Returns:
            Matching Listing or None
        """
        if not external_id:
            return None

        return self.db.query(Listing).filter(
            Listing.source == source,
            Listing.external_id == external_id
        ).first()

    def find_by_phone_fuzzy(
        self,
        phone: str,
        address: str
    ) -> Tuple[Optional[Listing], int]:
        """
        Find similar listing by phone number with fuzzy address matching.

        This catches cases where:
        - Same property listed by same agent on different sites
        - Address formatting differs slightly between sources

        Args:
            phone: Normalized phone number
            address: Property address

        Returns:
            Tuple of (listing, similarity_score) or (None, 0)
            similarity_score is 0-100, where 100 is exact match
        """
        if not phone or not address:
            return None, 0

        # Find listing with same phone number
        listing = self.db.query(Listing).filter(
            Listing.contact_phone == phone
        ).first()

        if not listing:
            return None, 0

        # Calculate address similarity
        similarity = fuzz.ratio(
            listing.address.lower(),
            address.lower()
        )

        # Return listing only if similarity exceeds threshold
        if similarity > self.similarity_threshold:
            return listing, similarity

        return None, similarity

    def find_duplicate(
        self,
        property_hash: str,
        source: str,
        external_id: Optional[str],
        phone: Optional[str],
        address: str
    ) -> Tuple[Optional[Listing], str]:
        """
        Find duplicate using all available strategies.

        Tries strategies in order of reliability:
        1. Property hash (most reliable)
        2. Source + external ID
        3. Phone + fuzzy address match

        Args:
            property_hash: Property hash
            source: Source name
            external_id: External listing ID
            phone: Normalized phone number
            address: Property address

        Returns:
            Tuple of (listing, detection_method) or (None, '')
            detection_method is one of: 'property_hash', 'external_id', 'phone_fuzzy'
        """
        # Strategy 1: Property hash (exact match)
        listing = self.find_by_property_hash(property_hash)
        if listing:
            return listing, 'property_hash'

        # Strategy 2: Source + external ID
        if external_id:
            listing = self.find_by_external_id(source, external_id)
            if listing:
                return listing, 'external_id'

        # Strategy 3: Phone + fuzzy address
        if phone:
            listing, similarity = self.find_by_phone_fuzzy(phone, address)
            if listing:
                return listing, f'phone_fuzzy (similarity: {similarity}%)'

        return None, ''
