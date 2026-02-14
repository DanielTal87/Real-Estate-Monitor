"""Listing filtering utilities based on user preferences"""

from typing import Dict, Tuple, Optional, Any
from config import Settings


class ListingFilter:
    """
    Filter listings based on user-defined criteria.

    Applies multiple filter types:
    - Must-have filters (price, rooms, size)
    - Deal-breaker filters (ground floor, elevator, parking)
    - Location filters (city whitelist)
    """

    def __init__(self, settings: Settings):
        """
        Initialize listing filter.

        Args:
            settings: Application settings with filter criteria
        """
        self.settings = settings

    def passes_all_filters(self, listing_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if listing passes all configured filters.

        Args:
            listing_data: Dictionary containing listing information

        Returns:
            Tuple of (passes, reason) where:
            - passes: True if listing passes all filters
            - reason: None if passes, otherwise description of why it failed

        Example:
            >>> filter = ListingFilter(settings)
            >>> passes, reason = filter.passes_all_filters(listing_data)
            >>> if not passes:
            ...     print(f"Filtered out: {reason}")
        """
        # Price filter
        if not self._passes_price_filter(listing_data):
            return False, f"Price {listing_data.get('price')} exceeds maximum {self.settings.max_price}"

        # Rooms filter
        if not self._passes_rooms_filter(listing_data):
            return False, f"Rooms {listing_data.get('rooms')} below minimum {self.settings.min_rooms}"

        # Size filter
        if not self._passes_size_filter(listing_data):
            return False, f"Size {listing_data.get('size_sqm')}m² below minimum {self.settings.min_size_sqm}m²"

        # Deal breakers
        passes, reason = self._passes_deal_breakers(listing_data)
        if not passes:
            return False, reason

        # City filter
        if not self._passes_city_filter(listing_data):
            city = listing_data.get('city', 'Unknown')
            allowed = ', '.join(self.settings.get_cities_list())
            return False, f"City '{city}' not in allowed list: {allowed}"

        return True, None

    def _passes_price_filter(self, listing_data: Dict) -> bool:
        """
        Check if listing price is within acceptable range.

        Args:
            listing_data: Listing information

        Returns:
            True if price is acceptable or not specified
        """
        price = listing_data.get('price')
        if not price:
            return True  # No price specified, allow it

        return price <= self.settings.max_price

    def _passes_rooms_filter(self, listing_data: Dict) -> bool:
        """
        Check if listing has minimum required rooms.

        Args:
            listing_data: Listing information

        Returns:
            True if rooms meet minimum or not specified
        """
        rooms = listing_data.get('rooms')
        if not rooms:
            return True  # No rooms specified, allow it

        return rooms >= self.settings.min_rooms

    def _passes_size_filter(self, listing_data: Dict) -> bool:
        """
        Check if listing meets minimum size requirement.

        Args:
            listing_data: Listing information

        Returns:
            True if size meets minimum or not specified
        """
        size = listing_data.get('size_sqm')
        if not size:
            return True  # No size specified, allow it

        return size >= self.settings.min_size_sqm

    def _passes_deal_breakers(self, listing_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if listing passes all deal-breaker criteria.

        Deal breakers are hard requirements that immediately disqualify a listing.

        Args:
            listing_data: Listing information

        Returns:
            Tuple of (passes, reason)
        """
        # Ground floor exclusion
        if self.settings.exclude_ground_floor:
            floor = listing_data.get('floor')
            if floor is not None and floor == 0:
                return False, "Ground floor excluded by user preference"

        # Elevator requirement for high floors
        if self.settings.require_elevator_above_floor:
            floor = listing_data.get('floor')
            has_elevator = listing_data.get('has_elevator', False)

            if floor is not None and floor > self.settings.require_elevator_above_floor:
                if not has_elevator:
                    return False, f"Floor {floor} requires elevator (threshold: {self.settings.require_elevator_above_floor})"

        # Parking requirement
        if self.settings.require_parking:
            has_parking = listing_data.get('has_parking', False)
            if not has_parking:
                return False, "Parking required but not available"

        # Mamad (safe room) requirement
        if self.settings.require_mamad:
            has_mamad = listing_data.get('has_mamad', False)
            if not has_mamad:
                return False, "Mamad (safe room) required but not available"

        return True, None

    def _passes_city_filter(self, listing_data: Dict) -> bool:
        """
        Check if listing is in an allowed city.

        Args:
            listing_data: Listing information

        Returns:
            True if city is allowed or no city filter configured
        """
        city = listing_data.get('city')
        if not city:
            return True  # No city specified, allow it

        allowed_cities = self.settings.get_cities_list()
        if not allowed_cities:
            return True  # No city filter configured, allow all

        return city in allowed_cities

    def get_filter_summary(self) -> Dict[str, Any]:
        """
        Get a summary of active filters.

        Returns:
            Dictionary describing all active filters
        """
        return {
            "price": {
                "max": self.settings.max_price,
                "active": True
            },
            "rooms": {
                "min": self.settings.min_rooms,
                "active": True
            },
            "size": {
                "min_sqm": self.settings.min_size_sqm,
                "active": True
            },
            "deal_breakers": {
                "exclude_ground_floor": self.settings.exclude_ground_floor,
                "require_elevator_above_floor": self.settings.require_elevator_above_floor,
                "require_parking": self.settings.require_parking,
                "require_mamad": self.settings.require_mamad
            },
            "cities": {
                "allowed": self.settings.get_cities_list(),
                "active": bool(self.settings.get_cities_list())
            }
        }
