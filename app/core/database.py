from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import hashlib
import json

Base = declarative_base()


class Listing(Base):
    __tablename__ = 'listings'

    id = Column(Integer, primary_key=True)

    # Identifiers
    property_hash = Column(String(64), unique=True, index=True)  # Unique identifier
    external_id = Column(String(255))  # Site's listing ID
    source = Column(String(50), index=True)  # yad2, madlan, facebook
    url = Column(Text)

    # Basic Info
    title = Column(String(500))
    description = Column(Text)
    address = Column(String(500))
    city = Column(String(100), index=True)
    neighborhood = Column(String(100), index=True)
    street = Column(String(200))

    # Property Details
    rooms = Column(Float)
    size_sqm = Column(Float)
    floor = Column(Integer)
    total_floors = Column(Integer)

    # Features
    has_elevator = Column(Boolean, default=False)
    has_parking = Column(Boolean, default=False)
    has_balcony = Column(Boolean, default=False)
    has_mamad = Column(Boolean, default=False)

    # Price
    price = Column(Float, index=True)
    price_per_sqm = Column(Float)

    # Contact
    contact_name = Column(String(200))
    contact_phone = Column(String(50), index=True)

    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, default=datetime.utcnow)

    # Status
    status = Column(String(50), default='unseen')  # unseen, interested, not_interested, contacted
    user_note = Column(Text)

    # Deal Score
    deal_score = Column(Float, default=0.0, index=True)

    # Images
    images_json = Column(Text)  # JSON array of image URLs

    # Relationships
    price_history = relationship("PriceHistory", back_populates="listing", cascade="all, delete-orphan")
    description_history = relationship("DescriptionHistory", back_populates="listing", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="listing", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('source', 'external_id', name='uix_source_external_id'),
    )

    @staticmethod
    def generate_property_hash(address, rooms, size_sqm):
        """Generate unique hash for property to detect duplicates across sources"""
        # Normalize address
        normalized_address = address.lower().strip().replace(' ', '')
        hash_string = f"{normalized_address}_{rooms}_{size_sqm}"
        return hashlib.sha256(hash_string.encode()).hexdigest()

    def get_images(self):
        """Get images as list"""
        if self.images_json:
            return json.loads(self.images_json)
        return []

    def set_images(self, images_list):
        """Set images from list"""
        self.images_json = json.dumps(images_list)

    def to_dict(self):
        """Convert to dictionary for API/template use"""
        return {
            'id': self.id,
            'property_hash': self.property_hash,
            'source': self.source,
            'url': self.url,
            'title': self.title,
            'description': self.description,
            'address': self.address,
            'city': self.city,
            'neighborhood': self.neighborhood,
            'street': self.street,
            'rooms': self.rooms,
            'size_sqm': self.size_sqm,
            'floor': self.floor,
            'total_floors': self.total_floors,
            'has_elevator': self.has_elevator,
            'has_parking': self.has_parking,
            'has_balcony': self.has_balcony,
            'price': self.price,
            'price_per_sqm': self.price_per_sqm,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'status': self.status,
            'user_note': self.user_note,
            'deal_score': self.deal_score,
            'images': self.get_images(),
        }


class PriceHistory(Base):
    __tablename__ = 'price_history'

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), index=True)
    price = Column(Float)
    price_per_sqm = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="price_history")


class DescriptionHistory(Base):
    __tablename__ = 'description_history'

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), index=True)
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="description_history")


class Notification(Base):
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), index=True)
    notification_type = Column(String(50))  # new_listing, price_drop, high_score
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="notifications")


class ScrapingState(Base):
    __tablename__ = 'scraping_state'

    id = Column(Integer, primary_key=True)
    source = Column(String(50), unique=True, index=True)
    last_scrape_time = Column(DateTime)
    last_listing_id = Column(String(255))
    last_listing_timestamp = Column(DateTime)
    cookies_json = Column(Text)
    status = Column(String(50), default='active')  # active, error, disabled
    error_message = Column(Text)
    error_count = Column(Integer, default=0)

    def get_cookies(self):
        """Get cookies as dict"""
        if self.cookies_json:
            return json.loads(self.cookies_json)
        return {}

    def set_cookies(self, cookies_dict):
        """Set cookies from dict"""
        self.cookies_json = json.dumps(cookies_dict)


class NeighborhoodStats(Base):
    __tablename__ = 'neighborhood_stats'

    id = Column(Integer, primary_key=True)
    city = Column(String(100))
    neighborhood = Column(String(100))
    avg_price = Column(Float)
    avg_price_per_sqm = Column(Float)
    median_price = Column(Float)
    median_price_per_sqm = Column(Float)
    sample_size = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('city', 'neighborhood', name='uix_city_neighborhood'),
    )


def init_db(database_url):
    """Initialize database and create all tables"""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal
