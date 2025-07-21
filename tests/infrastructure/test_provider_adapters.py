"""Tests for external provider service adapters."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

from src.infrastructure.external_services.byteme_adapter import ByteMeAdapter
from src.infrastructure.external_services.verbyndich_adapter import VerbynDichAdapter
from src.infrastructure.external_services.webwunder_adapter import WebWunderAdapter
from src.infrastructure.external_services.ping_perfect_adapter import PingPerfectAdapter
from src.infrastructure.external_services.provider_registry import ProviderRegistry
from src.infrastructure.external_services.provider_aggregator import ProviderAggregator
from src.domain.value_objects.address import Address
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType
from src.application.interfaces.providers import ProviderStatus, ProviderType


class TestByteMeAdapter:
    """Test cases for ByteMe adapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create ByteMe adapter instance."""
        return ByteMeAdapter()
    
    @pytest.fixture
    def test_address(self):
        """Create test address."""
        return Address(
            street="Teststraße",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
    
    def test_provider_properties(self, adapter):
        """Test provider properties."""
        assert adapter.provider_name == "ByteMe"
        assert adapter.provider_type == ProviderType.CSV_BASED
        assert "DE" in adapter.supported_regions
    
    @pytest.mark.asyncio
    async def test_validate_address_valid(self, adapter, test_address):
        """Test address validation with valid address."""
        result = await adapter.validate_address(test_address)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_address_invalid_country(self, adapter):
        """Test address validation with invalid country."""
        invalid_address = Address(
            street="Test Street",
            house_number="123",
            city="New York",
            postal_code="10001",
            country="US"
        )
        result = await adapter.validate_address(invalid_address)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_parse_csv_data_empty(self, adapter):
        """Test CSV parsing with empty data."""
        result = await adapter.parse_csv_data("")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_parse_csv_data_valid(self, adapter):
        """Test CSV parsing with valid data."""
        csv_data = """productId,providerName,speed,monthlyCostInCent,afterTwoYearsMonthlyCost,durationInMonths,connectionType,installationService,tv,voucherType,voucherValue
test_product,ByteMe,50,3999,4499,12,DSL,true,Premium TV,percentage,500"""
        
        offers = await adapter.parse_csv_data(csv_data)
        
        assert len(offers) == 1
        offer = offers[0]
        assert offer.provider_name == "ByteMe"
        assert offer.product_id == "test_product"
        assert offer.speed_download_mbps == 50
        assert offer.monthly_cost_euros == Decimal('39.99')
        assert offer.connection_type == ConnectionType.DSL
    
    @pytest.mark.asyncio
    async def test_get_provider_status(self, adapter):
        """Test getting provider status."""
        status = await adapter.get_provider_status()
        assert status == ProviderStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_info(self, adapter):
        """Test getting rate limit information."""
        info = await adapter.get_rate_limit_info()
        assert "remaining_requests" in info
        assert "total_calls" in info
        assert info["provider_type"] == "CSV_BASED"


class TestVerbynDichAdapter:
    """Test cases for VerbynDich adapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create VerbynDich adapter instance."""
        return VerbynDichAdapter()
    
    @pytest.fixture
    def test_address(self):
        """Create test address."""
        return Address(
            street="Teststraße",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
    
    def test_provider_properties(self, adapter):
        """Test provider properties."""
        assert adapter.provider_name == "VerbynDich"
        assert adapter.provider_type == ProviderType.API_BASED
        assert "DE" in adapter.supported_regions
    
    @pytest.mark.asyncio
    async def test_parse_description(self, adapter):
        """Test description parsing."""
        description = "Für nur 24€ im Monat erhalten Sie eine DSL-Verbindung mit einer Geschwindigkeit von 25 Mbit/s. Mindestvertragslaufzeit 12 Monate."
        
        parsed = adapter._parse_description(description)
        
        assert parsed['monthly_cost_euros'] == 24.0
        assert parsed['speed_mbps'] == 25
        assert parsed['connection_type'] == 'DSL'
        assert parsed['contract_duration_months'] == 12
    
    @pytest.mark.asyncio
    async def test_flatten_nested_array(self, adapter):
        """Test nested array flattening."""
        nested_data = {
            "results": [
                [
                    [
                        {"valid": True, "product": "test1"},
                        {"valid": False, "product": "test2"}
                    ]
                ],
                {"valid": True, "product": "test3"}
            ]
        }
        
        flattened = adapter._flatten_nested_array(nested_data)
        
        # Should contain all valid items
        valid_items = [item for item in flattened if isinstance(item, dict) and item.get('valid')]
        assert len(valid_items) >= 2


class TestWebWunderAdapter:
    """Test cases for WebWunder adapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create WebWunder adapter instance."""
        return WebWunderAdapter()
    
    def test_provider_properties(self, adapter):
        """Test provider properties."""
        assert adapter.provider_name == "WebWunder"
        assert adapter.provider_type == ProviderType.HYBRID
        assert "DE" in adapter.supported_regions
    
    def test_normalize_connection_type(self, adapter):
        """Test connection type normalization."""
        assert adapter._normalize_connection_type("FIBER") == ConnectionType.FIBER
        assert adapter._normalize_connection_type("DSL") == ConnectionType.DSL
        assert adapter._normalize_connection_type("CABLE") == ConnectionType.CABLE
        assert adapter._normalize_connection_type("Unknown") == ConnectionType.UNKNOWN
    
    def test_get_xml_text(self, adapter):
        """Test XML text extraction."""
        import xml.etree.ElementTree as ET
        
        xml_data = "<root><ns2:test xmlns:ns2='http://test'>value</ns2:test><fallback>fallback_value</fallback></root>"
        root = ET.fromstring(xml_data)
        namespaces = {'ns2': 'http://test'}
        
        # Should find namespaced element
        result = adapter._get_xml_text(root, 'test', namespaces)
        assert result == "value"
        
        # Should fallback to non-namespaced element
        result = adapter._get_xml_text(root, 'fallback', namespaces)
        assert result == "fallback_value"


class TestPingPerfectAdapter:
    """Test cases for PingPerfect adapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create PingPerfect adapter instance."""
        return PingPerfectAdapter(api_key="test_key", secret_key="test_secret")
    
    def test_provider_properties(self, adapter):
        """Test provider properties."""
        assert adapter.provider_name == "PingPerfect"
        assert adapter.provider_type == ProviderType.API_BASED
        assert "DE" in adapter.supported_regions
    
    @pytest.mark.asyncio
    async def test_sign_request(self, adapter):
        """Test request signing."""
        request_data = {"test": "value", "timestamp": "2023-01-01T00:00:00"}
        
        signature = await adapter.sign_request(request_data)
        
        assert signature is not None
        assert len(signature) > 0
        assert signature != "invalid_signature"
    
    def test_create_canonical_string(self, adapter):
        """Test canonical string creation."""
        request_data = {"b": "2", "a": "1", "c": "3"}
        
        canonical = adapter._create_canonical_string(request_data)
        
        # Should be sorted by key
        assert canonical == "a=1&b=2&c=3"


class TestProviderRegistry:
    """Test cases for provider registry."""
    
    @pytest.fixture
    def registry(self):
        """Create provider registry instance."""
        return ProviderRegistry()
    
    @pytest.fixture
    def mock_provider(self):
        """Create mock provider."""
        provider = Mock()
        provider.provider_name = "TestProvider"
        provider.provider_type = ProviderType.API_BASED
        provider.supported_regions = ["DE", "AT"]
        provider.validate_address = AsyncMock(return_value=True)
        provider.get_provider_status = AsyncMock(return_value=ProviderStatus.AVAILABLE)
        provider.get_rate_limit_info = AsyncMock(return_value={"remaining": 100})
        return provider
    
    @pytest.mark.asyncio
    async def test_register_provider(self, registry, mock_provider):
        """Test provider registration."""
        result = await registry.register_provider(mock_provider)
        
        assert result is True
        assert registry.is_provider_registered("TestProvider")
    
    @pytest.mark.asyncio
    async def test_unregister_provider(self, registry, mock_provider):
        """Test provider unregistration."""
        await registry.register_provider(mock_provider)
        
        result = await registry.unregister_provider("TestProvider")
        
        assert result is True
        assert not registry.is_provider_registered("TestProvider")
    
    @pytest.mark.asyncio
    async def test_get_provider(self, registry, mock_provider):
        """Test getting provider by name."""
        await registry.register_provider(mock_provider)
        
        retrieved = await registry.get_provider("TestProvider")
        
        assert retrieved == mock_provider
    
    @pytest.mark.asyncio
    async def test_get_all_providers(self, registry, mock_provider):
        """Test getting all providers."""
        await registry.register_provider(mock_provider)
        
        providers = await registry.get_all_providers()
        
        assert len(providers) == 1
        assert providers[0] == mock_provider


class TestProviderAggregator:
    """Test cases for provider aggregator."""
    
    @pytest.fixture
    def registry(self):
        """Create mock registry."""
        return Mock()
    
    @pytest.fixture
    def aggregator(self, registry):
        """Create provider aggregator instance."""
        return ProviderAggregator(registry)
    
    @pytest.fixture
    def test_address(self):
        """Create test address."""
        return Address(
            street="Teststraße",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
    
    @pytest.fixture
    def mock_provider_with_offers(self):
        """Create mock provider that returns offers."""
        provider = Mock()
        provider.provider_name = "TestProvider"
        
        # Create mock offers
        offer1 = ProviderOffer(
            provider_name="TestProvider",
            product_id="test1",
            speed_download_mbps=100,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal('39.99'),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        provider.get_offers = AsyncMock(return_value=[offer1])
        return provider
    
    @pytest.mark.asyncio
    async def test_get_aggregated_offers_empty_providers(self, aggregator, registry, test_address):
        """Test aggregation with no providers."""
        registry.get_available_providers = AsyncMock(return_value=[])
        
        offers = await aggregator.get_aggregated_offers(test_address)
        
        assert offers == []
    
    @pytest.mark.asyncio
    async def test_get_aggregated_offers_with_providers(self, aggregator, registry, test_address, mock_provider_with_offers):
        """Test aggregation with providers."""
        registry.get_available_providers = AsyncMock(return_value=[mock_provider_with_offers])
        
        offers = await aggregator.get_aggregated_offers(test_address)
        
        assert len(offers) == 1
        assert offers[0].provider_name == "TestProvider"
    
    def test_deduplicate_offers(self, aggregator):
        """Test offer deduplication."""
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="product1",
            speed_download_mbps=100,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal('39.99'),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        )
        
        offer2 = ProviderOffer(
            provider_name="Provider1",
            product_id="product1",  # Same provider and product ID
            speed_download_mbps=200,  # Different speed
            speed_upload_mbps=20,
            monthly_cost_euros=Decimal('49.99'),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        offer3 = ProviderOffer(
            provider_name="Provider1",
            product_id="product2",  # Different product ID
            speed_download_mbps=150,
            speed_upload_mbps=15,
            monthly_cost_euros=Decimal('44.99'),
            connection_type=ConnectionType.CABLE,
            contract_duration_months=12
        )
        
        offers = [offer1, offer2, offer3]
        unique_offers = aggregator._deduplicate_offers(offers)
        
        # Should have 2 unique offers (offer2 is duplicate of offer1)
        assert len(unique_offers) == 2
        assert unique_offers[0] == offer1  # First occurrence kept
        assert unique_offers[1] == offer3