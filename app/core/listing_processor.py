from sqlalchemy.orm import Session
from app.core.database import Listing, PriceHistory, DescriptionHistory
from app.core.deal_score import DealScoreCalculator
from app.core.config import settings
from datetime import datetime
import logging
from typing import Dict, Optional, List

from app.utils.phone_normalizer import normalize_israeli_phone
from app.utils.duplicate_detector import DuplicateDetector
from app.utils.listing_filter import ListingFilter

logger = logging.getLogger(__name__)


class ListingProcessor:
    """Process and store scraped listings"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.deal_calculator = DealScoreCalculator(db_session)
        self.duplicate_detector = DuplicateDetector(db_session)
        self.listing_filter = ListingFilter(settings)
        self.settings = settings

    def process_listings(self, listings: List[Dict], source: str) -> Dict[str, int]:
        """
        Process a batch of listings from a source
        Returns stats: {new: X, updated: X, duplicates: X, filtered: X}
        """
        logger.info(f"[Listing Processor] Starting batch processing, source: {source}, count: {len(listings)}")

        stats = {
            'new': 0,
            'updated': 0,
            'duplicates': 0,
            'filtered': 0,
            'price_drops': 0
        }

        for idx, listing_data in enumerate(listings, 1):
            try:
                logger.debug(f"[Listing Processor] Processing listing, index: {idx}/{len(listings)}, source: {source}")
                result = self.process_single_listing(listing_data, source)
                stats[result] += 1
                logger.debug(f"[Listing Processor] Listing processed, result: {result}, index: {idx}")
            except Exception as e:
                logger.error(f"[Listing Processor] Error processing listing, index: {idx}, error: {e}")
                continue

        self.db.commit()
        logger.info(f"[Listing Processor] Batch processing completed, source: {source}, stats: {stats}")
        return stats

    def process_single_listing(self, listing_data: Dict, source: str) -> str:
        """
        Process a single listing
        Returns: 'new', 'updated', 'duplicates', or 'filtered'
        """
        title = listing_data.get('title', 'N/A')[:50]
        price = listing_data.get('price', 0)

        logger.debug(f"[Listing Processor] Applying filters, title: {title}, price: {price}")

        # Apply filters first using the filter utility
        passes, reason = self.listing_filter.passes_all_filters(listing_data)
        if not passes:
            logger.info(f"[Listing Processor] Listing filtered out, reason: {reason}, title: {title}")
            return 'filtered'

        logger.debug(f"[Listing Processor] Listing passed all filters, title: {title}")

        # Generate property hash
        address = listing_data.get('address', '')
        rooms = listing_data.get('rooms', 0)
        size_sqm = listing_data.get('size_sqm', 0)

        property_hash = Listing.generate_property_hash(address, rooms, size_sqm)

        # Normalize phone for duplicate detection
        phone = listing_data.get('contact_phone')
        normalized_phone = normalize_israeli_phone(phone) if phone else None

        # Use duplicate detector to find existing listing
        existing_listing, detection_method = self.duplicate_detector.find_duplicate(
            property_hash=property_hash,
            source=source,
            external_id=listing_data.get('external_id'),
            phone=normalized_phone,
            address=address
        )

        if existing_listing:
            logger.debug(f"Found duplicate via {detection_method}: {property_hash}")
            return self._update_existing_listing(existing_listing, listing_data)

        # Create new listing
        return self._create_new_listing(listing_data, property_hash)

    def _create_new_listing(self, listing_data: Dict, property_hash: str) -> str:
        """Create a new listing"""
        title = listing_data.get('title', 'N/A')[:50]
        logger.info(f"[Listing Processor] Creating new listing, title: {title}, hash: {property_hash[:16]}")

        listing = Listing(
            property_hash=property_hash,
            source=listing_data.get('source'),
            external_id=listing_data.get('external_id'),
            url=listing_data.get('url'),
            title=listing_data.get('title'),
            description=listing_data.get('description'),
            address=listing_data.get('address'),
            city=listing_data.get('city'),
            neighborhood=listing_data.get('neighborhood'),
            street=listing_data.get('street'),
            rooms=listing_data.get('rooms'),
            size_sqm=listing_data.get('size_sqm'),
            floor=listing_data.get('floor'),
            total_floors=listing_data.get('total_floors'),
            has_elevator=listing_data.get('has_elevator', False),
            has_parking=listing_data.get('has_parking', False),
            has_balcony=listing_data.get('has_balcony', False),
            price=listing_data.get('price'),
            price_per_sqm=listing_data.get('price_per_sqm'),
            contact_name=listing_data.get('contact_name'),
            contact_phone=normalize_israeli_phone(listing_data.get('contact_phone')),
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            last_checked=datetime.utcnow(),
            status='unseen'
        )

        # Set images
        if listing_data.get('images'):
            listing.set_images(listing_data['images'])

        # Calculate deal score
        listing.deal_score = self.deal_calculator.calculate_score(listing)

        self.db.add(listing)
        self.db.flush()

        # Add initial price history
        if listing.price:
            price_history = PriceHistory(
                listing_id=listing.id,
                price=listing.price,
                price_per_sqm=listing.price_per_sqm,
                timestamp=datetime.utcnow()
            )
            self.db.add(price_history)

        # Add initial description history
        if listing.description:
            desc_history = DescriptionHistory(
                listing_id=listing.id,
                description=listing.description,
                timestamp=datetime.utcnow()
            )
            self.db.add(desc_history)

        logger.info(f"[Listing Processor] New listing created successfully, title: {listing.title[:50]}, score: {listing.deal_score:.1f}, price: {listing.price}")
        return 'new'

    def _update_existing_listing(self, listing: Listing, listing_data: Dict) -> str:
        """Update an existing listing"""
        logger.debug(f"[Listing Processor] Updating existing listing, id: {listing.id}, title: {listing.title[:50]}")

        # Update last seen
        listing.last_seen = datetime.utcnow()
        listing.last_checked = datetime.utcnow()

        price_changed = False
        description_changed = False

        # Check for price change
        new_price = listing_data.get('price')
        if new_price and new_price != listing.price:
            old_price = listing.price
            logger.info(f"[Listing Processor] Price change detected, id: {listing.id}, old_price: {old_price}, new_price: {new_price}")
            listing.price = new_price

            # Recalculate price per sqm
            if listing.size_sqm and listing.size_sqm > 0:
                listing.price_per_sqm = new_price / listing.size_sqm

            # Add to price history
            price_history = PriceHistory(
                listing_id=listing.id,
                price=new_price,
                price_per_sqm=listing.price_per_sqm,
                timestamp=datetime.utcnow()
            )
            self.db.add(price_history)

            price_changed = True

            # Check for price drop
            if old_price and new_price < old_price:
                drop_pct = ((old_price - new_price) / old_price) * 100
                logger.info(f"[Listing Processor] 🔥 Price drop detected, id: {listing.id}, title: {listing.title[:50]}, drop_percent: {drop_pct:.1f}%, old_price: {old_price}, new_price: {new_price}")

                # Reset status if significant drop
                if drop_pct >= self.settings.min_price_drop_percent_notify:
                    if listing.status == 'not_interested':
                        listing.status = 'unseen'
                        logger.info(f"Resetting 'not_interested' status due to price drop")

        # Check for description change
        new_description = listing_data.get('description')
        if new_description and new_description != listing.description:
            listing.description = new_description

            # Add to description history
            desc_history = DescriptionHistory(
                listing_id=listing.id,
                description=new_description,
                timestamp=datetime.utcnow()
            )
            self.db.add(desc_history)

            description_changed = True

        # Update other fields
        if listing_data.get('url'):
            listing.url = listing_data['url']
        if listing_data.get('title'):
            listing.title = listing_data['title']

        # Recalculate deal score
        old_score = listing.deal_score
        listing.deal_score = self.deal_calculator.calculate_score(listing)

        if price_changed:
            logger.info(f"[Listing Processor] Listing updated with price change, id: {listing.id}, title: {listing.title[:50]}, score_change: {old_score:.1f} → {listing.deal_score:.1f}")
            # Check if price actually dropped (compare new_price with old_price from line 179)
            return 'price_drops' if new_price < old_price else 'updated'
        elif description_changed:
            logger.info(f"[Listing Processor] Listing updated with description change, id: {listing.id}, title: {listing.title[:50]}")
            return 'updated'
        else:
            logger.debug(f"[Listing Processor] Duplicate listing (no changes), id: {listing.id}")
            return 'duplicates'

