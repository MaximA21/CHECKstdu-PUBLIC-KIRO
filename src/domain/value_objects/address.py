"""Address value object with validation logic."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Address:
    """Address value object representing a physical address with validation."""

    street: str
    house_number: str
    city: str
    postal_code: str
    country: Optional[str] = "DE"  # Default to Germany

    def __post_init__(self):
        """Validate address fields after initialization."""
        self._validate_street()
        self._validate_house_number()
        self._validate_city()
        self._validate_postal_code()
        self._validate_country()

    def _validate_street(self) -> None:
        """Validate street name."""
        if not self.street or not self.street.strip():
            raise ValueError("Street cannot be empty")
        if len(self.street.strip()) < 2:
            raise ValueError("Street must be at least 2 characters long")
        if len(self.street) > 100:
            raise ValueError("Street cannot exceed 100 characters")

    def _validate_house_number(self) -> None:
        """Validate house number."""
        if not self.house_number or not self.house_number.strip():
            raise ValueError("House number cannot be empty")
        # Allow alphanumeric house numbers (e.g., "12", "12a", "12-14")
        if not re.match(r"^[0-9]+[a-zA-Z]?(-[0-9]+[a-zA-Z]?)?$", self.house_number.strip()):
            raise ValueError("House number must be in valid format (e.g., '12', '12a', '12-14')")

    def _validate_city(self) -> None:
        """Validate city name."""
        if not self.city or not self.city.strip():
            raise ValueError("City cannot be empty")
        if len(self.city.strip()) < 2:
            raise ValueError("City must be at least 2 characters long")
        if len(self.city) > 50:
            raise ValueError("City cannot exceed 50 characters")
        # Allow letters, spaces, hyphens, and apostrophes
        if not re.match(r"^[a-zA-ZäöüÄÖÜß\s\-']+$", self.city.strip()):
            raise ValueError("City contains invalid characters")

    def _validate_postal_code(self) -> None:
        """Validate postal code based on country."""
        if not self.postal_code or not self.postal_code.strip():
            raise ValueError("Postal code cannot be empty")

        # German postal code validation (5 digits)
        if self.country == "DE":
            if not re.match(r"^\d{5}$", self.postal_code.strip()):
                raise ValueError("German postal code must be exactly 5 digits")
        else:
            # Generic validation for other countries
            if len(self.postal_code.strip()) < 3 or len(self.postal_code.strip()) > 10:
                raise ValueError("Postal code must be between 3 and 10 characters")

    def _validate_country(self) -> None:
        """Validate country code."""
        if self.country and len(self.country) != 2:
            raise ValueError("Country code must be exactly 2 characters")
        if self.country and not self.country.isupper():
            raise ValueError("Country code must be uppercase")

    @property
    def full_address(self) -> str:
        """Return formatted full address string."""
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"

    @property
    def normalized_postal_code(self) -> str:
        """Return normalized postal code without spaces."""
        return self.postal_code.replace(" ", "")

    def is_same_location(self, other: "Address") -> bool:
        """Check if two addresses represent the same location."""
        if not isinstance(other, Address):
            return False

        return (
            self.normalized_postal_code == other.normalized_postal_code
            and self.house_number.strip().lower() == other.house_number.strip().lower()
            and self.city.strip().lower() == other.city.strip().lower()
        )
