"""Phone number normalization utilities for Israeli phone numbers"""

from typing import Optional


def normalize_israeli_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize Israeli phone number to standard format.

    Converts various phone number formats to a standardized Israeli format:
    - Removes all non-digit characters
    - Converts international format (+972, 972) to local format (0)
    - Returns 10-digit Israeli phone number

    Args:
        phone: Raw phone number string (can be None)

    Returns:
        Normalized phone number (e.g., "0501234567") or None if invalid

    Examples:
        >>> normalize_israeli_phone("+972-50-123-4567")
        "0501234567"
        >>> normalize_israeli_phone("972501234567")
        "0501234567"
        >>> normalize_israeli_phone("050-123-4567")
        "0501234567"
        >>> normalize_israeli_phone(None)
        None
    """
    if not phone:
        return None

    # Remove all non-digit characters
    digits = ''.join(c for c in phone if c.isdigit())

    if not digits:
        return None

    # Handle Israeli phone numbers with country code
    if digits.startswith('972'):
        # Remove country code and add leading 0
        digits = '0' + digits[3:]

    # Ensure we have exactly 10 digits for Israeli numbers
    if len(digits) > 10 and digits.startswith('0'):
        digits = digits[:10]

    # Validate length (Israeli mobile numbers are 10 digits, landlines can be 9)
    if len(digits) not in [9, 10]:
        return None

    return digits
