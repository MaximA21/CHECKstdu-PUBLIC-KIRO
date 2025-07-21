"""Tests for SearchResult entity."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from src.domain.entities.search_result import SearchResult
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from src.domain.value_objects.address import Address


class TestSearchResult:
    """Test cases for SearchResult entity."""
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="Teststraße",
            house_number="123",
            city="Berlin",
            postal_code="10115"
        )
    
    @pytest.fixture
    def sample_offer(self):
        """Create a sample provider offer for testing."""
        return ProviderOffer(
            provider_name="TestProvider",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
    
    def test_search_result_creation(self, sample_address):
        """Test creating a search result."""
        search_result = SearchResult(
            request_id="test-request-123",
            address=sample_address
        )
        
        assert search_result.request_id == "test-request-123"
        assert search_result.address == sample_address
        assert search_result.offers == []
        assert search_result.share_token is not None
        assert len(search_result.share_token) >= 8
        assert search_result.timestamp is not None
        assert search_result.expires_at is not None
        assert search_result.expires_at > search_result.timestamp
        assert search_result.search_metadata == {}
    
    def test_create_new_class_method(self, sample_address):
        """Test creating a new search result using class method."""
        search_result = SearchResult.create_new(sample_address)
        
        assert search_result.request_id is not None
        assert search_result.address == sample_address
        assert search_result.offers == []
        assert search_result.share_token is not None
    
    def test_create_new_with_request_id(self, sample_address):
        """Test creating a new search result with specific request ID."""
        request_id = "custom-request-id"
        search_result = SearchResult.create_new(sample_address, request_id)
        
        assert search_result.request_id == request_id
        assert search_result.address == sample_address
    
    def test_add_offer(self, sample_address, sample_offer):
        """Test adding an offer to search results."""
        search_result = SearchResult.create_new(sample_address)
        search_result.add_offer(sample_offer)
        
        assert len(search_result.offers) == 1
        assert search_result.offers[0] == sample_offer
    
    def test_add_duplicate_offer(self, sample_address, sample_offer):
        """Test adding duplicate offer raises error."""
        search_result = SearchResult.create_new(sample_address)
        search_result.add_offer(sample_offer)
        
        # Try to add the same offer again
        with pytest.raises(ValueError, match="Offer from TestProvider with product TEST-001 already exists"):
            search_result.add_offer(sample_offer)
    
    def test_add_invalid_offer(self, sample_address):
        """Test adding invalid offer raises error."""
        search_result = SearchResult.create_new(sample_address)
        
        with pytest.raises(ValueError, match="Offer must be a ProviderOffer instance"):
            search_result.add_offer("not an offer")
    
    def test_remove_offer(self, sample_address, sample_offer):
        """Test removing an offer."""
        search_result = SearchResult.create_new(sample_address)
        search_result.add_offer(sample_offer)
        
        # Remove the offer
        result = search_result.remove_offer("TestProvider", "TEST-001")
        assert result is True
        assert len(search_result.offers) == 0
        
        # Try to remove non-existent offer
        result = search_result.remove_offer("NonExistent", "NONE")
        assert result is False
    
    def test_get_offer_by_provider_and_product(self, sample_address, sample_offer):
        """Test getting offer by provider and product ID."""
        search_result = SearchResult.create_new(sample_address)
        search_result.add_offer(sample_offer)
        
        found_offer = search_result.get_offer_by_provider_and_product("TestProvider", "TEST-001")
        assert found_offer == sample_offer
        
        not_found = search_result.get_offer_by_provider_and_product("NonExistent", "NONE")
        assert not_found is None
    
    def test_get_offers_by_provider(self, sample_address):
        """Test getting offers by provider."""
        search_result = SearchResult.create_new(sample_address)
        
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="PROD-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer2 = ProviderOffer(
            provider_name="Provider1",
            product_id="PROD-002",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("49.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer3 = ProviderOffer(
            provider_name="Provider2",
            product_id="PROD-003",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        search_result.add_offer(offer1)
        search_result.add_offer(offer2)
        search_result.add_offer(offer3)
        
        provider1_offers = search_result.get_offers_by_provider("Provider1")
        assert len(provider1_offers) == 2
        assert offer1 in provider1_offers
        assert offer2 in provider1_offers
        
        provider2_offers = search_result.get_offers_by_provider("Provider2")
        assert len(provider2_offers) == 1
        assert offer3 in provider2_offers
    
    def test_get_offers_by_connection_type(self, sample_address):
        """Test getting offers by connection type."""
        search_result = SearchResult.create_new(sample_address)
        
        fiber_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="FIBER-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        dsl_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="DSL-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        search_result.add_offer(fiber_offer)
        search_result.add_offer(dsl_offer)
        
        fiber_offers = search_result.get_offers_by_connection_type(ConnectionType.FIBER)
        assert len(fiber_offers) == 1
        assert fiber_offer in fiber_offers
        
        dsl_offers = search_result.get_offers_by_connection_type(ConnectionType.DSL)
        assert len(dsl_offers) == 1
        assert dsl_offer in dsl_offers
    
    def test_get_available_offers(self, sample_address):
        """Test getting only available offers."""
        search_result = SearchResult.create_new(sample_address)
        
        available_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="AVAIL-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.AVAILABLE
        )
        
        unavailable_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="UNAVAIL-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
            status=OfferStatus.UNAVAILABLE
        )
        
        search_result.add_offer(available_offer)
        search_result.add_offer(unavailable_offer)
        
        available_offers = search_result.get_available_offers()
        assert len(available_offers) == 1
        assert available_offer in available_offers
        assert unavailable_offer not in available_offers
    
    def test_get_cheapest_offer(self, sample_address):
        """Test getting the cheapest offer."""
        search_result = SearchResult.create_new(sample_address)
        
        expensive_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="EXP-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("49.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        cheap_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="CHEAP-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        search_result.add_offer(expensive_offer)
        search_result.add_offer(cheap_offer)
        
        cheapest = search_result.get_cheapest_offer()
        assert cheapest == cheap_offer
    
    def test_get_cheapest_offer_no_available(self, sample_address):
        """Test getting cheapest offer when none are available."""
        search_result = SearchResult.create_new(sample_address)
        
        unavailable_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="UNAVAIL-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
            status=OfferStatus.UNAVAILABLE
        )
        
        search_result.add_offer(unavailable_offer)
        
        cheapest = search_result.get_cheapest_offer()
        assert cheapest is None
    
    def test_get_fastest_offer(self, sample_address):
        """Test getting the fastest offer."""
        search_result = SearchResult.create_new(sample_address)
        
        slow_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="SLOW-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        fast_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="FAST-001",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("49.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        search_result.add_offer(slow_offer)
        search_result.add_offer(fast_offer)
        
        fastest = search_result.get_fastest_offer()
        assert fastest == fast_offer
    
    def test_get_best_value_offer(self, sample_address):
        """Test getting the best value offer (lowest cost per Mbps)."""
        search_result = SearchResult.create_new(sample_address)
        
        # 30 EUR / 100 Mbps = 0.30 EUR per Mbps
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="OFFER-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        # 40 EUR / 200 Mbps = 0.20 EUR per Mbps (better value)
        offer2 = ProviderOffer(
            provider_name="Provider2",
            product_id="OFFER-002",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("40.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        search_result.add_offer(offer1)
        search_result.add_offer(offer2)
        
        best_value = search_result.get_best_value_offer()
        assert best_value == offer2
    
    def test_get_fiber_offers(self, sample_address):
        """Test getting fiber offers."""
        search_result = SearchResult.create_new(sample_address)
        
        fiber_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="FIBER-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        dsl_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="DSL-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        search_result.add_offer(fiber_offer)
        search_result.add_offer(dsl_offer)
        
        fiber_offers = search_result.get_fiber_offers()
        assert len(fiber_offers) == 1
        assert fiber_offer in fiber_offers
        assert dsl_offer not in fiber_offers
    
    def test_properties(self, sample_address, sample_offer):
        """Test various properties of search result."""
        search_result = SearchResult.create_new(sample_address)
        
        # Empty search result
        assert search_result.offer_count == 0
        assert search_result.available_offer_count == 0
        assert search_result.provider_count == 0
        
        # Add offers
        search_result.add_offer(sample_offer)
        
        offer2 = ProviderOffer(
            provider_name="Provider2",
            product_id="PROD-002",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12,
            status=OfferStatus.UNAVAILABLE
        )
        search_result.add_offer(offer2)
        
        assert search_result.offer_count == 2
        assert search_result.available_offer_count == 1  # Only sample_offer is available
        assert search_result.provider_count == 2  # TestProvider and Provider2
    
    def test_expiration(self, sample_address):
        """Test expiration functionality."""
        # Create search result with custom expiration
        past_time = datetime.utcnow() - timedelta(days=1)
        search_result = SearchResult(
            request_id="test-request",
            address=sample_address,
            timestamp=past_time - timedelta(days=1),
            expires_at=past_time
        )
        
        assert search_result.is_expired is True
        assert search_result.days_until_expiration == 0
        
        # Create non-expired search result
        future_time = datetime.utcnow() + timedelta(days=5)
        search_result2 = SearchResult(
            request_id="test-request-2",
            address=sample_address,
            expires_at=future_time
        )
        
        assert search_result2.is_expired is False
        assert search_result2.days_until_expiration >= 4  # Should be around 5 days
    
    def test_extend_expiration(self, sample_address):
        """Test extending expiration date."""
        search_result = SearchResult.create_new(sample_address)
        original_expiration = search_result.expires_at
        
        search_result.extend_expiration(7)  # Extend by 7 days
        
        expected_expiration = original_expiration + timedelta(days=7)
        assert search_result.expires_at == expected_expiration
    
    def test_extend_expiration_invalid(self, sample_address):
        """Test extending expiration with invalid days."""
        search_result = SearchResult.create_new(sample_address)
        
        with pytest.raises(ValueError, match="Extension days must be positive"):
            search_result.extend_expiration(0)
        
        with pytest.raises(ValueError, match="Extension days must be positive"):
            search_result.extend_expiration(-1)
    
    def test_metadata(self, sample_address):
        """Test metadata functionality."""
        search_result = SearchResult.create_new(sample_address)
        
        search_result.add_metadata("search_source", "web")
        search_result.add_metadata("user_agent", "Mozilla/5.0")
        
        assert search_result.get_metadata("search_source") == "web"
        assert search_result.get_metadata("user_agent") == "Mozilla/5.0"
        assert search_result.get_metadata("nonexistent") is None
        assert search_result.get_metadata("nonexistent", "default") == "default"
    
    def test_add_metadata_empty_key(self, sample_address):
        """Test adding metadata with empty key."""
        search_result = SearchResult.create_new(sample_address)
        
        with pytest.raises(ValueError, match="Metadata key cannot be empty"):
            search_result.add_metadata("", "value")
    
    def test_get_summary_stats(self, sample_address):
        """Test getting summary statistics."""
        search_result = SearchResult.create_new(sample_address)
        
        # Empty search result
        stats = search_result.get_summary_stats()
        assert stats["total_offers"] == 0
        assert stats["available_offers"] == 0
        assert stats["providers"] == 0
        assert stats["cheapest_monthly_cost"] is None
        assert stats["fastest_speed"] is None
        assert stats["fiber_available"] is False
        
        # Add offers
        fiber_offer = ProviderOffer(
            provider_name="Provider1",
            product_id="FIBER-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("30.00"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        dsl_offer = ProviderOffer(
            provider_name="Provider2",
            product_id="DSL-001",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("20.00"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        search_result.add_offer(fiber_offer)
        search_result.add_offer(dsl_offer)
        
        stats = search_result.get_summary_stats()
        assert stats["total_offers"] == 2
        assert stats["available_offers"] == 2
        assert stats["providers"] == 2
        assert stats["cheapest_monthly_cost"] == Decimal("20.00")
        assert stats["most_expensive_monthly_cost"] == Decimal("30.00")
        assert stats["fastest_speed"] == 100
        assert stats["slowest_speed"] == 50
        assert stats["fiber_available"] is True
        assert "Fiber" in stats["connection_types"]
        assert "DSL" in stats["connection_types"]
    
    # Validation tests
    def test_empty_request_id_validation(self, sample_address):
        """Test validation of empty request ID."""
        with pytest.raises(ValueError, match="Request ID cannot be empty"):
            SearchResult(
                request_id="",
                address=sample_address
            )
    
    def test_invalid_address_validation(self):
        """Test validation of invalid address."""
        with pytest.raises(ValueError, match="Address must be a valid Address value object"):
            SearchResult(
                request_id="test-request",
                address="not an address"
            )
    
    def test_invalid_offers_type_validation(self, sample_address):
        """Test validation of invalid offers type."""
        with pytest.raises(ValueError, match="Offers must be a list"):
            SearchResult(
                request_id="test-request",
                address=sample_address,
                offers="not a list"
            )
    
    def test_invalid_offer_in_list_validation(self, sample_address):
        """Test validation of invalid offer in offers list."""
        with pytest.raises(ValueError, match="All offers must be ProviderOffer instances"):
            SearchResult(
                request_id="test-request",
                address=sample_address,
                offers=["not an offer"]
            )
    
    def test_expiration_before_timestamp_validation(self, sample_address):
        """Test validation when expiration is before timestamp."""
        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="Expiration date must be after timestamp"):
            SearchResult(
                request_id="test-request",
                address=sample_address,
                timestamp=now,
                expires_at=past
            )
    
    def test_short_share_token_validation(self, sample_address):
        """Test validation of too short share token."""
        with pytest.raises(ValueError, match="Share token must be at least 8 characters long"):
            SearchResult(
                request_id="test-request",
                address=sample_address,
                share_token="short"
            )