"""Unit tests for domain entities."""

import pytest
from datetime import datetime
from src.domain.entities.provider_offer import ProviderOffer
from src.domain.entities.connection_session import ConnectionSession
from src.domain.entities.search_result import SearchResult
from src.domain.value_objects.address import Address


class TestProviderOffer:
    """Test ProviderOffer entity."""

    def test_provider_offer_creation(self):
        """Test creating a provider offer."""
        offer = ProviderOffer(
            provider_name="TestProvider",
            offer_id="test-123",
            speed_mbps=100,
            price_monthly=29.99,
            technology="fiber",
            availability=True,
            installation_fee=0.0
        )
        
        assert offer.provider_name == "TestProvider"
        assert offer.offer_id == "test-123"
        assert offer.speed_mbps == 100
        assert offer.price_monthly == 29.99
        assert offer.technology == "fiber"
        assert offer.availability is True
        assert offer.installation_fee == 0.0

    def test_provider_offer_validation(self):
        """Test provider offer validation."""
        # Test invalid speed
        with pytest.raises(ValueError):
            ProviderOffer(
                provider_name="TestProvider",
                offer_id="test-123",
                speed_mbps=-10,  # Invalid negative speed
                price_monthly=29.99,
                technology="fiber",
                availability=True,
                installation_fee=0.0
            )

    def test_provider_offer_equality(self):
        """Test provider offer equality."""
        offer1 = ProviderOffer(
            provider_name="TestProvider",
            offer_id="test-123",
            speed_mbps=100,
            price_monthly=29.99,
            technology="fiber",
            availability=True,
            installation_fee=0.0
        )
        
        offer2 = ProviderOffer(
            provider_name="TestProvider",
            offer_id="test-123",
            speed_mbps=100,
            price_monthly=29.99,
            technology="fiber",
            availability=True,
            installation_fee=0.0
        )
        
        assert offer1 == offer2


class TestConnectionSession:
    """Test ConnectionSession entity."""

    def test_connection_session_creation(self):
        """Test creating a connection session."""
        session = ConnectionSession(
            connection_id="conn-123",
            user_id="user-456",
            connected_at="2024-01-01T12:00:00Z",
            last_activity="2024-01-01T12:05:00Z",
            status="active"
        )
        
        assert session.connection_id == "conn-123"
        assert session.user_id == "user-456"
        assert session.connected_at == "2024-01-01T12:00:00Z"
        assert session.last_activity == "2024-01-01T12:05:00Z"
        assert session.status == "active"

    def test_connection_session_is_active(self):
        """Test connection session active status."""
        active_session = ConnectionSession(
            connection_id="conn-123",
            user_id="user-456",
            connected_at="2024-01-01T12:00:00Z",
            last_activity="2024-01-01T12:05:00Z",
            status="active"
        )
        
        inactive_session = ConnectionSession(
            connection_id="conn-124",
            user_id="user-457",
            connected_at="2024-01-01T12:00:00Z",
            last_activity="2024-01-01T12:05:00Z",
            status="disconnected"
        )
        
        assert active_session.is_active() is True
        assert inactive_session.is_active() is False


class TestSearchResult:
    """Test SearchResult entity."""

    def test_search_result_creation(self):
        """Test creating a search result."""
        offers = [
            ProviderOffer(
                provider_name="Provider1",
                offer_id="offer-1",
                speed_mbps=100,
                price_monthly=29.99,
                technology="fiber",
                availability=True,
                installation_fee=0.0
            )
        ]
        
        result = SearchResult(
            request_id="req-123",
            address=Address(
                street="Test Street 1",
                city="Berlin",
                postal_code="10115",
                country="Germany"
            ),
            offers=offers,
            search_timestamp="2024-01-01T12:00:00Z"
        )
        
        assert result.request_id == "req-123"
        assert len(result.offers) == 1
        assert result.offers[0].provider_name == "Provider1"
        assert result.search_timestamp == "2024-01-01T12:00:00Z"

    def test_search_result_add_offer(self):
        """Test adding offers to search result."""
        result = SearchResult(
            request_id="req-123",
            address=Address(
                street="Test Street 1",
                city="Berlin",
                postal_code="10115",
                country="Germany"
            ),
            offers=[],
            search_timestamp="2024-01-01T12:00:00Z"
        )
        
        offer = ProviderOffer(
            provider_name="Provider1",
            offer_id="offer-1",
            speed_mbps=100,
            price_monthly=29.99,
            technology="fiber",
            availability=True,
            installation_fee=0.0
        )
        
        result.add_offer(offer)
        assert len(result.offers) == 1
        assert result.offers[0] == offer

    def test_search_result_get_best_offer(self):
        """Test getting best offer from search result."""
        offers = [
            ProviderOffer(
                provider_name="Provider1",
                offer_id="offer-1",
                speed_mbps=50,
                price_monthly=39.99,
                technology="dsl",
                availability=True,
                installation_fee=50.0
            ),
            ProviderOffer(
                provider_name="Provider2",
                offer_id="offer-2",
                speed_mbps=100,
                price_monthly=29.99,
                technology="fiber",
                availability=True,
                installation_fee=0.0
            )
        ]
        
        result = SearchResult(
            request_id="req-123",
            address=Address(
                street="Test Street 1",
                city="Berlin",
                postal_code="10115",
                country="Germany"
            ),
            offers=offers,
            search_timestamp="2024-01-01T12:00:00Z"
        )
        
        best_offer = result.get_best_offer()
        assert best_offer.provider_name == "Provider2"  # Better speed and price


class TestAddress:
    """Test Address value object."""

    def test_address_creation(self):
        """Test creating an address."""
        address = Address(
            street="Musterstraße 1",
            city="Berlin",
            postal_code="10115",
            country="Germany"
        )
        
        assert address.street == "Musterstraße 1"
        assert address.city == "Berlin"
        assert address.postal_code == "10115"
        assert address.country == "Germany"

    def test_address_validation(self):
        """Test address validation."""
        # Test empty street
        with pytest.raises(ValueError):
            Address(
                street="",
                city="Berlin",
                postal_code="10115",
                country="Germany"
            )

    def test_address_equality(self):
        """Test address equality."""
        address1 = Address(
            street="Musterstraße 1",
            city="Berlin",
            postal_code="10115",
            country="Germany"
        )
        
        address2 = Address(
            street="Musterstraße 1",
            city="Berlin",
            postal_code="10115",
            country="Germany"
        )
        
        assert address1 == address2

    def test_address_string_representation(self):
        """Test address string representation."""
        address = Address(
            street="Musterstraße 1",
            city="Berlin",
            postal_code="10115",
            country="Germany"
        )
        
        address_str = str(address)
        assert "Musterstraße 1" in address_str
        assert "Berlin" in address_str
        assert "10115" in address_str
        assert "Germany" in address_str

    def test_address_normalization(self):
        """Test address normalization."""
        address = Address(
            street="  musterstraße 1  ",
            city="  BERLIN  ",
            postal_code="10115",
            country="germany"
        )
        
        normalized = address.normalize()
        assert normalized.street == "Musterstraße 1"
        assert normalized.city == "Berlin"
        assert normalized.country == "Germany"