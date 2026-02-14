from sqlalchemy.orm import Session
from database import Listing, PriceHistory, DescriptionHistory
from deal_score import DealScoreCalculator
from config import settings
from datetime import datetime
from fuzzywuzzy import fuzz
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class ListingProcessor:
    """Process and store scraped listings"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.deal_calculator = DealScoreCalculator(db_session)
        self.settings = settings
    
    def process_listings(self, listings: List[Dict], source: str) -> Dict[str, int]:
        """
        Process a batch of listings from a source
        Returns stats: {new: X, updated: X, duplicates: X, filtered: X}
        """
        stats = {
            'new': 0,
            'updated': 0,
            'duplicates': 0,
            'filtered': 0,
            'price_drops': 0
        }
        
        for listing_data in listings:
            try:
                result = self.process_single_listing(listing_data, source)
                stats[result] += 1
            except Exception as e:
                logger.error(f"Error processing listing: {e}")
                continue
        
        self.db.commit()
        return stats
    
    def process_single_listing(self, listing_data: Dict, source: str) -> str:
        """
        Process a single listing
        Returns: 'new', 'updated', 'duplicates', or 'filtered'
        """
        
        # Apply filters first
        if not self._passes_filters(listing_data):
            return 'filtered'
        
        # Generate property hash
        address = listing_data.get('address', '')
        rooms = listing_data.get('rooms', 0)
        size_sqm = listing_data.get('size_sqm', 0)
        
        property_hash = Listing.generate_property_hash(address, rooms, size_sqm)
        
        # Check for existing listing by property hash (cross-site duplicate)
        existing_listing = self.db.query(Listing).filter(
            Listing.property_hash == property_hash
        ).first()
        
        if existing_listing:
            # Update existing listing
            return self._update_existing_listing(existing_listing, listing_data)
        
        # Check for existing listing by source + external_id
        if listing_data.get('external_id'):
            existing_listing = self.db.query(Listing).filter(
                Listing.source == source,
                Listing.external_id == listing_data['external_id']
            ).first()
            
            if existing_listing:
                return self._update_existing_listing(existing_listing, listing_data)
        
        # Check for fuzzy duplicates by phone number
        phone = listing_data.get('contact_phone')
        if phone:
            normalized_phone = self._normalize_phone(phone)
            if normalized_phone:
                similar_listing = self.db.query(Listing).filter(
                    Listing.contact_phone == normalized_phone
                ).first()
                
                if similar_listing:
                    # Check if addresses are similar
                    similarity = fuzz.ratio(
                        similar_listing.address.lower(),
                        address.lower()
                    )
                    if similarity > 85:  # 85% similarity threshold
                        logger.info(f"Found fuzzy duplicate by phone: {property_hash}")
                        return self._update_existing_listing(similar_listing, listing_data)
        
        # Create new listing
        return self._create_new_listing(listing_data, property_hash)
    
    def _create_new_listing(self, listing_data: Dict, property_hash: str) -> str:
        """Create a new listing"""
        
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
            contact_phone=self._normalize_phone(listing_data.get('contact_phone')),
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
        
        logger.info(f"Created new listing: {listing.title} (Score: {listing.deal_score:.1f})")
        return 'new'
    
    def _update_existing_listing(self, listing: Listing, listing_data: Dict) -> str:
        """Update an existing listing"""
        
        # Update last seen
        listing.last_seen = datetime.utcnow()
        listing.last_checked = datetime.utcnow()
        
        price_changed = False
        description_changed = False
        
        # Check for price change
        new_price = listing_data.get('price')
        if new_price and new_price != listing.price:
            old_price = listing.price
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
                logger.info(f"🔥 Price drop detected: {listing.title} - {drop_pct:.1f}% drop")
                
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
            logger.info(f"Updated listing with price change: {listing.title} "
                       f"(Score: {old_score:.1f} → {listing.deal_score:.1f})")
            return 'price_drops' if new_price < (listing_data.get('price') or 0) else 'updated'
        elif description_changed:
            logger.info(f"Updated listing with description change: {listing.title}")
            return 'updated'
        else:
            return 'duplicates'
    
    def _passes_filters(self, listing_data: Dict) -> bool:
        """Check if listing passes configured filters"""
        
        # Must have filters
        if listing_data.get('price'):
            if listing_data['price'] > self.settings.max_price:
                return False
        
        if listing_data.get('rooms'):
            if listing_data['rooms'] < self.settings.min_rooms:
                return False
        
        if listing_data.get('size_sqm'):
            if listing_data['size_sqm'] < self.settings.min_size_sqm:
                return False
        
        # Deal breakers
        if self.settings.exclude_ground_floor:
            if listing_data.get('floor') == 0:
                return False
        
        if self.settings.require_elevator_above_floor:
            floor = listing_data.get('floor')
            has_elevator = listing_data.get('has_elevator', False)
            if floor and floor > self.settings.require_elevator_above_floor and not has_elevator:
                return False
        
        if self.settings.require_parking:
            if not listing_data.get('has_parking', False):
                return False
        
        # City filter
        if listing_data.get('city'):
            allowed_cities = self.settings.get_cities_list()
            if allowed_cities and listing_data['city'] not in allowed_cities:
                return False
        
        return True
    
    def _normalize_phone(self, phone: Optional[str]) -> Optional[str]:
        """Normalize phone number"""
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits = ''.join(c for c in phone if c.isdigit())
        
        # Handle Israeli phone numbers
        if digits.startswith('972'):
            digits = '0' + digits[3:]
        elif digits.startswith('+972'):
            digits = '0' + digits[4:]
        
        return digits if digits else None
