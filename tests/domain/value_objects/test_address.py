"""Tests for Address value object."""

import pytest
from src.domain.value_objects.address import Address


class TestAddress:
    """Test cases for Address value object."""
    
    def test_valid_address_creation(self):
        """Test creating a valid address."""
        address = Address(
            street="Musterstraße",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
        
        assert address.street == "Musterstraße"
        assert address.house_number == "123"
        assert address.city == "Berlin"
        assert address.postal_code == "10115"
        assert address.country == "DE"
    
    def test_address_with_default_country(self):
        """Test address creation with default country."""
        address = Address(
            street="Hauptstraße",
            house_number="1",
            city="München",
            postal_code="80331"
        )
        
        assert address.country == "DE"
    
    def test_address_with_complex_house_number(self):
        """Test address with complex house numbers."""
        # Test alphanumeric house number
        address1 = Address(
            street="Teststraße",
            house_number="12a",
            city="Hamburg",
            postal_code="20095"
        )
        assert address1.house_number == "12a"
        
        # Test range house number
        address2 = Address(
            street="Teststraße",
            house_number="12-14",
            city="Hamburg",
            postal_code="20095"
        )
        assert address2.house_number == "12-14"
    
    def test_full_address_property(self):
        """Test full address formatting."""
        address = Address(
            street="Alexanderplatz",
            house_number="1",
            city="Berlin",
            postal_code="10178"
        )
        
        expected = "Alexanderplatz 1, 10178 Berlin"
        assert address.full_address == expected
    
    def test_normalized_postal_code(self):
        """Test postal code normalization."""
        # Use a non-German address to test postal code with spaces
        address = Address(
            street="Test Street",
            house_number="1",
            city="London",
            postal_code="SW1A 1AA",
            country="GB"
        )
        
        assert address.normalized_postal_code == "SW1A1AA"
    
    def test_is_same_location(self):
        """Test location comparison."""
        address1 = Address(
            street="Musterstraße",
            house_number="123",
            city="Berlin",
            postal_code="10115"
        )
        
        address2 = Address(
            street="Andere Straße",  # Different street
            house_number="123",
            city="Berlin",
            postal_code="10115"
        )
        
        address3 = Address(
            street="Musterstraße",
            house_number="123",
            city="berlin",  # Different case
            postal_code="10115"
        )
        
        # Same location (ignores street name, case insensitive)
        assert address1.is_same_location(address3)
        assert address2.is_same_location(address3)
        
        # Different location
        address4 = Address(
            street="Musterstraße",
            house_number="124",  # Different house number
            city="Berlin",
            postal_code="10115"
        )
        assert not address1.is_same_location(address4)
    
    def test_empty_street_validation(self):
        """Test validation of empty street."""
        with pytest.raises(ValueError, match="Street cannot be empty"):
            Address(
                street="",
                house_number="1",
                city="Berlin",
                postal_code="10115"
            )
        
        with pytest.raises(ValueError, match="Street cannot be empty"):
            Address(
                street="   ",  # Only whitespace
                house_number="1",
                city="Berlin",
                postal_code="10115"
            )
    
    def test_short_street_validation(self):
        """Test validation of too short street."""
        with pytest.raises(ValueError, match="Street must be at least 2 characters long"):
            Address(
                street="A",
                house_number="1",
                city="Berlin",
                postal_code="10115"
            )
    
    def test_long_street_validation(self):
        """Test validation of too long street."""
        long_street = "A" * 101
        with pytest.raises(ValueError, match="Street cannot exceed 100 characters"):
            Address(
                street=long_street,
                house_number="1",
                city="Berlin",
                postal_code="10115"
            )
    
    def test_empty_house_number_validation(self):
        """Test validation of empty house number."""
        with pytest.raises(ValueError, match="House number cannot be empty"):
            Address(
                street="Teststraße",
                house_number="",
                city="Berlin",
                postal_code="10115"
            )
    
    def test_invalid_house_number_format(self):
        """Test validation of invalid house number format."""
        invalid_house_numbers = ["abc", "12b3", "12--14", "-12", "12-"]
        
        for house_number in invalid_house_numbers:
            with pytest.raises(ValueError, match="House number must be in valid format"):
                Address(
                    street="Teststraße",
                    house_number=house_number,
                    city="Berlin",
                    postal_code="10115"
                )
    
    def test_empty_city_validation(self):
        """Test validation of empty city."""
        with pytest.raises(ValueError, match="City cannot be empty"):
            Address(
                street="Teststraße",
                house_number="1",
                city="",
                postal_code="10115"
            )
    
    def test_short_city_validation(self):
        """Test validation of too short city."""
        with pytest.raises(ValueError, match="City must be at least 2 characters long"):
            Address(
                street="Teststraße",
                house_number="1",
                city="A",
                postal_code="10115"
            )
    
    def test_long_city_validation(self):
        """Test validation of too long city."""
        long_city = "A" * 51
        with pytest.raises(ValueError, match="City cannot exceed 50 characters"):
            Address(
                street="Teststraße",
                house_number="1",
                city=long_city,
                postal_code="10115"
            )
    
    def test_invalid_city_characters(self):
        """Test validation of invalid city characters."""
        with pytest.raises(ValueError, match="City contains invalid characters"):
            Address(
                street="Teststraße",
                house_number="1",
                city="Berlin123",  # Numbers not allowed
                postal_code="10115"
            )
    
    def test_valid_city_with_special_characters(self):
        """Test valid city names with special characters."""
        valid_cities = [
            "München",
            "Düsseldorf", 
            "Frankfurt am Main",
            "Baden-Baden",
            "O'Brien"
        ]
        
        for city in valid_cities:
            address = Address(
                street="Teststraße",
                house_number="1",
                city=city,
                postal_code="10115"
            )
            assert address.city == city
    
    def test_empty_postal_code_validation(self):
        """Test validation of empty postal code."""
        with pytest.raises(ValueError, match="Postal code cannot be empty"):
            Address(
                street="Teststraße",
                house_number="1",
                city="Berlin",
                postal_code=""
            )
    
    def test_german_postal_code_validation(self):
        """Test German postal code validation."""
        # Valid German postal codes
        valid_codes = ["10115", "80331", "20095", "01067"]
        for code in valid_codes:
            address = Address(
                street="Teststraße",
                house_number="1",
                city="Berlin",
                postal_code=code,
                country="DE"
            )
            assert address.postal_code == code
        
        # Invalid German postal codes
        invalid_codes = ["1011", "101156", "abcde", "10-115"]
        for code in invalid_codes:
            with pytest.raises(ValueError, match="German postal code must be exactly 5 digits"):
                Address(
                    street="Teststraße",
                    house_number="1",
                    city="Berlin",
                    postal_code=code,
                    country="DE"
                )
    
    def test_non_german_postal_code_validation(self):
        """Test non-German postal code validation."""
        # Valid non-German postal codes
        address1 = Address(
            street="Test Street",
            house_number="1",
            city="London",
            postal_code="SW1A 1AA",
            country="GB"
        )
        assert address1.postal_code == "SW1A 1AA"
        
        # Too short postal code
        with pytest.raises(ValueError, match="Postal code must be between 3 and 10 characters"):
            Address(
                street="Test Street",
                house_number="1",
                city="London",
                postal_code="AB",
                country="GB"
            )
        
        # Too long postal code
        with pytest.raises(ValueError, match="Postal code must be between 3 and 10 characters"):
            Address(
                street="Test Street",
                house_number="1",
                city="London",
                postal_code="ABCDEFGHIJK",
                country="GB"
            )
    
    def test_invalid_country_code_length(self):
        """Test validation of invalid country code length."""
        with pytest.raises(ValueError, match="Country code must be exactly 2 characters"):
            Address(
                street="Teststraße",
                house_number="1",
                city="Berlin",
                postal_code="10115",
                country="DEU"  # Too long
            )
        
        with pytest.raises(ValueError, match="Country code must be exactly 2 characters"):
            Address(
                street="Teststraße",
                house_number="1",
                city="Berlin",
                postal_code="10115",
                country="D"  # Too short
            )
    
    def test_country_code_case_validation(self):
        """Test validation of country code case."""
        with pytest.raises(ValueError, match="Country code must be uppercase"):
            Address(
                street="Teststraße",
                house_number="1",
                city="Berlin",
                postal_code="10115",
                country="de"  # Lowercase
            )
    
    def test_address_immutability(self):
        """Test that address is immutable (frozen dataclass)."""
        address = Address(
            street="Teststraße",
            house_number="1",
            city="Berlin",
            postal_code="10115"
        )
        
        # Should not be able to modify fields
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.7+
            address.street = "New Street"
    
    def test_address_equality(self):
        """Test address equality comparison."""
        address1 = Address(
            street="Teststraße",
            house_number="1",
            city="Berlin",
            postal_code="10115"
        )
        
        address2 = Address(
            street="Teststraße",
            house_number="1",
            city="Berlin",
            postal_code="10115"
        )
        
        address3 = Address(
            street="Andere Straße",
            house_number="1",
            city="Berlin",
            postal_code="10115"
        )
        
        assert address1 == address2
        assert address1 != address3
    
    def test_address_hash(self):
        """Test that address can be used as dictionary key."""
        address1 = Address(
            street="Teststraße",
            house_number="1",
            city="Berlin",
            postal_code="10115"
        )
        
        address2 = Address(
            street="Teststraße",
            house_number="1",
            city="Berlin",
            postal_code="10115"
        )
        
        # Should be able to use as dictionary keys
        address_dict = {address1: "value1"}
        assert address_dict[address2] == "value1"  # Same address should work as key