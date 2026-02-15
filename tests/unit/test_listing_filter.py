"""
Unit tests for ListingFilter.
Tests filtering logic based on user preferences and deal breakers.
"""
import pytest
from app.utils.listing_filter import ListingFilter
from app.core.config import Settings


class TestListingFilter:
    """Test listing filtering logic"""

    def test_passes_all_filters_valid_listing(self, test_settings):
        """Test that valid listing passes all filters"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'floor': 2,
            'has_elevator': True,
            'has_parking': True,
            'has_mamad': False
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is True
        assert reason is None

    def test_price_filter_exceeds_max(self, test_settings):
        """Test price filter when price exceeds maximum"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 5000000,  # Exceeds max_price of 3000000
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv'
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'Price' in reason
        assert '5000000' in reason

    def test_price_filter_no_price(self, test_settings):
        """Test price filter when price is not specified"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': None,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv'
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is True

    def test_rooms_filter_below_minimum(self, test_settings):
        """Test rooms filter when below minimum"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': 2.0,  # Below min_rooms of 3.0
            'size_sqm': 85,
            'city': 'Tel Aviv'
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'Rooms' in reason

    def test_rooms_filter_no_rooms(self, test_settings):
        """Test rooms filter when rooms not specified"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': None,
            'size_sqm': 85,
            'city': 'Tel Aviv'
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is True

    def test_size_filter_below_minimum(self, test_settings):
        """Test size filter when below minimum"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 50,  # Below min_size_sqm of 70
            'city': 'Tel Aviv'
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'Size' in reason
        assert '50' in reason

    def test_size_filter_no_size(self, test_settings):
        """Test size filter when size not specified"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': None,
            'city': 'Tel Aviv'
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is True

    def test_city_filter_not_in_list(self, test_settings):
        """Test city filter when city not in allowed list"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Jerusalem'  # Not in allowed cities
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'City' in reason
        assert 'Jerusalem' in reason

    def test_city_filter_no_city(self, test_settings):
        """Test city filter when city not specified"""
        filter_obj = ListingFilter(test_settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': None
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is True

    def test_ground_floor_exclusion(self):
        """Test ground floor exclusion deal breaker"""
        settings = Settings(
            cities="Tel Aviv",
            max_price=3000000,
            min_rooms=3.0,
            min_size_sqm=70,
            exclude_ground_floor=True
        )
        filter_obj = ListingFilter(settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'floor': 0  # Ground floor
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'Ground floor' in reason

    def test_elevator_requirement(self):
        """Test elevator requirement for high floors"""
        settings = Settings(
            cities="Tel Aviv",
            max_price=3000000,
            min_rooms=3.0,
            min_size_sqm=70,
            require_elevator_above_floor=2
        )
        filter_obj = ListingFilter(settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'floor': 4,
            'has_elevator': False
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'elevator' in reason.lower()

    def test_elevator_requirement_with_elevator(self):
        """Test elevator requirement passes when elevator exists"""
        settings = Settings(
            cities="Tel Aviv",
            max_price=3000000,
            min_rooms=3.0,
            min_size_sqm=70,
            require_elevator_above_floor=2
        )
        filter_obj = ListingFilter(settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'floor': 4,
            'has_elevator': True
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is True

    def test_parking_requirement(self):
        """Test parking requirement deal breaker"""
        settings = Settings(
            cities="Tel Aviv",
            max_price=3000000,
            min_rooms=3.0,
            min_size_sqm=70,
            require_parking=True
        )
        filter_obj = ListingFilter(settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'has_parking': False
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'Parking' in reason

    def test_mamad_requirement(self):
        """Test mamad (safe room) requirement deal breaker"""
        settings = Settings(
            cities="Tel Aviv",
            max_price=3000000,
            min_rooms=3.0,
            min_size_sqm=70,
            require_mamad=True
        )
        filter_obj = ListingFilter(settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'has_mamad': False
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        assert passes is False
        assert 'Mamad' in reason or 'safe room' in reason.lower()

    def test_get_filter_summary(self, test_settings):
        """Test getting filter summary"""
        filter_obj = ListingFilter(test_settings)

        summary = filter_obj.get_filter_summary()

        assert 'price' in summary
        assert 'rooms' in summary
        assert 'size' in summary
        assert 'deal_breakers' in summary
        assert 'cities' in summary

        assert summary['price']['max'] == test_settings.max_price
        assert summary['rooms']['min'] == test_settings.min_rooms
        assert summary['size']['min_sqm'] == test_settings.min_size_sqm

    def test_multiple_deal_breakers(self):
        """Test listing failing multiple deal breakers"""
        settings = Settings(
            cities="Tel Aviv",
            max_price=3000000,
            min_rooms=3.0,
            min_size_sqm=70,
            exclude_ground_floor=True,
            require_parking=True,
            require_mamad=True
        )
        filter_obj = ListingFilter(settings)

        listing_data = {
            'price': 2500000,
            'rooms': 3.5,
            'size_sqm': 85,
            'city': 'Tel Aviv',
            'floor': 0,  # Ground floor
            'has_parking': False,  # No parking
            'has_mamad': False  # No mamad
        }

        passes, reason = filter_obj.passes_all_filters(listing_data)

        # Should fail on first deal breaker (ground floor)
        assert passes is False
        assert reason is not None
