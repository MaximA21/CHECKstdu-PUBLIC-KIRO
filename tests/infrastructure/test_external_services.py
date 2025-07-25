"""Tests for infrastructure external services."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.application.interfaces.providers import ProviderStatus
from src.infrastructure.external_services.byteme_adapter import ByteMeAdapter
from src.infrastructure.external_services.mock_providers import MockProviderService
from src.infrastructure.external_services.ping_perfect_adapter import PingPerfectAdapter
from src.infrastructure.external_services.provider_aggregator import ProviderAggregator
from src.infrastructure.external_services.provider_registry import ProviderRegistry
from src.infrastructure.external_services.verbyndich_adapter import VerbynDichAdapter
from src.infrastructure.external_services.webwunder_adapter import WebWunderAdapter


class TestByteMeAdapter:
    @pytest.fixture
    def byteme_adapter(self):
        """Create ByteMeAdapter instance."""
        return ByteMeAdapter()

    def test_byteme_adapter_initialization(self, byteme_adapter):
        """Test ByteMeAdapter initialization."""
        assert byteme_adapter._supported_regions == ["DE", "AT", "CH"]
        assert byteme_adapter._status.value == "available"
        assert byteme_adapter._rate_limit_remaining == 1000
        assert byteme_adapter._call_count == 0

    @pytest.mark.asyncio
    async def test_get_offers_success(self, byteme_adapter):
        """Test successful get offers."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        with (
            patch.object(byteme_adapter, "validate_address", return_value=True),
            patch.object(byteme_adapter, "get_csv_data_for_address", return_value="test,csv,data"),
            patch.object(byteme_adapter, "parse_csv_data", return_value=[]),
        ):

            result = await byteme_adapter.get_offers(address)

            assert result == []
            assert byteme_adapter._call_count == 1
            assert byteme_adapter._rate_limit_remaining == 999

    @pytest.mark.asyncio
    async def test_get_offers_invalid_address(self, byteme_adapter):
        """Test get offers with invalid address."""
        from src.domain.value_objects.address import Address
        from src.shared.exceptions.domain import InvalidAddressException

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        with patch.object(byteme_adapter, "validate_address", return_value=False):
            with pytest.raises(InvalidAddressException):
                await byteme_adapter.get_offers(address)

    @pytest.mark.asyncio
    async def test_get_offers_provider_unavailable(self, byteme_adapter):
        """Test get offers when provider is unavailable."""
        from src.domain.value_objects.address import Address
        from src.shared.exceptions.domain import ProviderUnavailableException

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        # Mock the status to be unavailable
        with patch.object(byteme_adapter, "_status", Mock(value="unavailable")):
            with pytest.raises(ProviderUnavailableException):
                await byteme_adapter.get_offers(address)

    @pytest.mark.asyncio
    async def test_parse_csv_data_empty(self, byteme_adapter):
        """Test parsing empty CSV data."""
        result = await byteme_adapter.parse_csv_data("")
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_csv_data_with_polars(self, byteme_adapter):
        """Test parsing CSV data with Polars."""
        csv_data = "productId,speed,monthlyCostInCent,afterTwoYearsMonthlyCost,durationInMonths,voucherValue,installationService,connectionType,providerName\n1,100,2000,2500,24,100,true,FTTH,TestProvider"

        # Mock the actual parsing to return a valid offer
        mock_offer = Mock()
        with (
            patch("src.infrastructure.external_services.byteme_adapter.HAS_POLARS", True),
            patch.object(byteme_adapter, "_parse_csv_with_polars", return_value=[mock_offer]),
        ):
            result = await byteme_adapter.parse_csv_data(csv_data)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_parse_csv_data_pure_python(self, byteme_adapter):
        """Test parsing CSV data with pure Python."""
        csv_data = "productId,speed,monthlyCostInCent,afterTwoYearsMonthlyCost,durationInMonths,voucherValue,installationService,connectionType,providerName\n1,100,2000,2500,24,100,true,FTTH,TestProvider"

        # Mock the actual parsing to return a valid offer
        mock_offer = Mock()
        with (
            patch("src.infrastructure.external_services.byteme_adapter.HAS_POLARS", False),
            patch.object(byteme_adapter, "_parse_csv_pure_python", return_value=[mock_offer]),
        ):
            result = await byteme_adapter.parse_csv_data(csv_data)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_validate_address_supported_region(self, byteme_adapter):
        """Test address validation for supported region."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        result = await byteme_adapter.validate_address(address)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_address_unsupported_region(self, byteme_adapter):
        """Test address validation for unsupported region."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Paris", postal_code="75001", country="FR")

        result = await byteme_adapter.validate_address(address)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_provider_status(self, byteme_adapter):
        """Test getting provider status."""
        result = await byteme_adapter.get_provider_status()
        assert result.value == "available"

    def test_provider_name(self, byteme_adapter):
        """Test getting provider name."""
        assert byteme_adapter.provider_name == "ByteMe"

    def test_provider_type(self, byteme_adapter):
        """Test getting provider type."""
        assert byteme_adapter.provider_type.value == "csv_based"

    def test_supported_regions(self, byteme_adapter):
        """Test getting supported regions."""
        regions = byteme_adapter.supported_regions
        assert "DE" in regions
        assert "AT" in regions
        assert "CH" in regions

    @pytest.mark.asyncio
    async def test_get_rate_limit_info(self, byteme_adapter):
        """Test getting rate limit info."""
        result = await byteme_adapter.get_rate_limit_info()
        assert "remaining_requests" in result
        assert "total_calls" in result
        assert result["remaining_requests"] == 1000
        assert result["total_calls"] == 0

    def test_safe_int(self, byteme_adapter):
        """Test safe integer conversion."""
        assert byteme_adapter._safe_int("123") == 123
        assert byteme_adapter._safe_int("invalid", 0) == 0
        assert byteme_adapter._safe_int(None, 42) == 42

    def test_safe_bool(self, byteme_adapter):
        """Test safe boolean conversion."""
        assert byteme_adapter._safe_bool("true") is True
        assert byteme_adapter._safe_bool("false") is False
        assert byteme_adapter._safe_bool("1") is True
        assert byteme_adapter._safe_bool("0") is False
        assert byteme_adapter._safe_bool("yes") is True
        assert byteme_adapter._safe_bool("no") is False

    def test_normalize_connection_type(self, byteme_adapter):
        """Test connection type normalization."""
        from src.domain.entities.provider_offer import ConnectionType

        assert byteme_adapter._normalize_connection_type("FTTH") == ConnectionType.FIBER
        assert byteme_adapter._normalize_connection_type("DSL") == ConnectionType.DSL
        assert byteme_adapter._normalize_connection_type("CABLE") == ConnectionType.CABLE
        assert byteme_adapter._normalize_connection_type("UNKNOWN") == ConnectionType.UNKNOWN


class TestPingPerfectAdapter:
    @pytest.fixture
    def ping_perfect_adapter(self):
        """Create PingPerfectAdapter instance."""
        return PingPerfectAdapter()

    def test_ping_perfect_adapter_initialization(self, ping_perfect_adapter):
        """Test PingPerfectAdapter initialization."""
        assert ping_perfect_adapter._supported_regions == ["DE", "AT", "CH"]
        assert ping_perfect_adapter._status.value == "available"

    @pytest.mark.asyncio
    async def test_get_offers_success(self, ping_perfect_adapter):
        """Test successful get offers."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        with (
            patch.object(ping_perfect_adapter, "validate_address", return_value=True),
            patch.object(ping_perfect_adapter, "get_signed_offers", return_value=[]),
        ):

            result = await ping_perfect_adapter.get_offers(address)
            assert result == []

    def test_provider_name(self, ping_perfect_adapter):
        """Test getting provider name."""
        assert ping_perfect_adapter.provider_name == "PingPerfect"

    def test_provider_type(self, ping_perfect_adapter):
        """Test getting provider type."""
        assert ping_perfect_adapter.provider_type.value == "api_based"


class TestVerbynDichAdapter:
    @pytest.fixture
    def verbyndich_adapter(self):
        """Create VerbynDichAdapter instance."""
        return VerbynDichAdapter()

    def test_verbyndich_adapter_initialization(self, verbyndich_adapter):
        """Test VerbynDichAdapter initialization."""
        assert verbyndich_adapter._supported_regions == ["DE", "AT", "CH"]
        assert verbyndich_adapter._status.value == "available"

    @pytest.mark.asyncio
    async def test_get_offers_success(self, verbyndich_adapter):
        """Test successful get offers."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        with (
            patch.object(verbyndich_adapter, "validate_address", return_value=True),
            patch.object(verbyndich_adapter, "get_api_data_for_address", return_value={"offers": []}),
            patch.object(verbyndich_adapter, "parse_nested_array_data", return_value=[]),
        ):

            result = await verbyndich_adapter.get_offers(address)
            assert result == []

    def test_provider_name(self, verbyndich_adapter):
        """Test getting provider name."""
        assert verbyndich_adapter.provider_name == "VerbynDich"

    def test_provider_type(self, verbyndich_adapter):
        """Test getting provider type."""
        assert verbyndich_adapter.provider_type.value == "api_based"


class TestWebWunderAdapter:
    @pytest.fixture
    def webwunder_adapter(self):
        """Create WebwunderAdapter instance."""
        return WebWunderAdapter()

    def test_webwunder_adapter_initialization(self, webwunder_adapter):
        """Test WebwunderAdapter initialization."""
        assert webwunder_adapter._supported_regions == ["DE", "AT", "CH"]
        assert webwunder_adapter._status.value == "available"

    @pytest.mark.asyncio
    async def test_get_offers_success(self, webwunder_adapter):
        """Test successful get offers."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        with (
            patch.object(webwunder_adapter, "validate_address", return_value=True),
            patch.object(webwunder_adapter, "get_offers_with_metadata", return_value={"offers": []}),
        ):

            result = await webwunder_adapter.get_offers(address)
            assert result == []

    def test_provider_name(self, webwunder_adapter):
        """Test getting provider name."""
        assert webwunder_adapter.provider_name == "WebWunder"

    def test_provider_type(self, webwunder_adapter):
        """Test getting provider type."""
        assert webwunder_adapter.provider_type.value == "hybrid"


class TestProviderAggregator:
    @pytest.fixture
    def provider_registry(self):
        """Create ProviderRegistry instance."""
        return ProviderRegistry()

    @pytest.fixture
    def provider_aggregator(self, provider_registry):
        """Create ProviderAggregator instance."""
        return ProviderAggregator(provider_registry)

    def test_provider_aggregator_initialization(self, provider_aggregator, provider_registry):
        """Test ProviderAggregator initialization."""
        assert provider_aggregator._registry == provider_registry
        assert provider_aggregator._default_timeout == 30
        assert provider_aggregator._max_concurrent_requests == 10

    @pytest.mark.asyncio
    async def test_get_aggregated_offers_success(self, provider_aggregator, provider_registry):
        """Test getting aggregated offers successfully."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        # Create mock offers with proper structure
        mock_offer1 = Mock()
        mock_offer1.provider_name = "provider1"
        mock_offer1.product_id = "offer1"

        mock_offer2 = Mock()
        mock_offer2.provider_name = "provider2"
        mock_offer2.product_id = "offer2"

        mock_provider1 = AsyncMock()
        mock_provider1.provider_name = "provider1"
        mock_provider1.validate_address.return_value = True
        mock_provider1.get_provider_status.return_value = ProviderStatus.AVAILABLE
        mock_provider1.get_offers.return_value = [mock_offer1]

        mock_provider2 = AsyncMock()
        mock_provider2.provider_name = "provider2"
        mock_provider2.validate_address.return_value = True
        mock_provider2.get_provider_status.return_value = ProviderStatus.AVAILABLE
        mock_provider2.get_offers.return_value = [mock_offer2]

        # Register providers in the registry
        await provider_registry.register_provider(mock_provider1)
        await provider_registry.register_provider(mock_provider2)

        result = await provider_aggregator.get_aggregated_offers(address)

        assert len(result) == 2
        assert any(offer.provider_name == "provider1" for offer in result)
        assert any(offer.provider_name == "provider2" for offer in result)

    @pytest.mark.asyncio
    async def test_get_aggregated_offers_with_specific_providers(self, provider_aggregator, provider_registry):
        """Test getting aggregated offers from specific providers."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        # Create mock offers with proper structure
        mock_offer1 = Mock()
        mock_offer1.provider_name = "provider1"
        mock_offer1.product_id = "offer1"

        mock_offer2 = Mock()
        mock_offer2.provider_name = "provider2"
        mock_offer2.product_id = "offer2"

        mock_provider1 = AsyncMock()
        mock_provider1.provider_name = "provider1"
        mock_provider1.get_offers.return_value = [mock_offer1]

        mock_provider2 = AsyncMock()
        mock_provider2.provider_name = "provider2"
        mock_provider2.get_offers.return_value = [mock_offer2]

        # Register providers in the registry
        await provider_registry.register_provider(mock_provider1)
        await provider_registry.register_provider(mock_provider2)

        result = await provider_aggregator.get_aggregated_offers(address, ["provider1"])

        assert len(result) == 1
        assert result[0].provider_name == "provider1"

    @pytest.mark.asyncio
    async def test_get_aggregated_offers_with_failures(self, provider_aggregator, provider_registry):
        """Test getting aggregated offers with some provider failures."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        # Create mock offers with proper structure
        mock_offer1 = Mock()
        mock_offer1.provider_name = "provider1"
        mock_offer1.product_id = "offer1"

        mock_provider1 = AsyncMock()
        mock_provider1.provider_name = "provider1"
        mock_provider1.validate_address.return_value = True
        mock_provider1.get_provider_status.return_value = ProviderStatus.AVAILABLE
        mock_provider1.get_offers.return_value = [mock_offer1]

        mock_provider2 = AsyncMock()
        mock_provider2.provider_name = "provider2"
        mock_provider2.validate_address.return_value = True
        mock_provider2.get_provider_status.return_value = ProviderStatus.AVAILABLE
        mock_provider2.get_offers.side_effect = Exception("API Error")

        # Register providers in the registry
        await provider_registry.register_provider(mock_provider1)
        await provider_registry.register_provider(mock_provider2)

        result = await provider_aggregator.get_aggregated_offers(address)

        assert len(result) == 1
        assert result[0].provider_name == "provider1"

    @pytest.mark.asyncio
    async def test_get_aggregated_offers_no_providers(self, provider_aggregator):
        """Test getting aggregated offers when no providers are available."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        result = await provider_aggregator.get_aggregated_offers(address)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_offers_with_fallback(self, provider_aggregator, provider_registry):
        """Test getting offers with fallback strategy."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        # Create mock offers with proper structure
        mock_primary_offer = Mock()
        mock_primary_offer.provider_name = "primary"
        mock_primary_offer.product_id = "primary_offer"

        mock_fallback_offer = Mock()
        mock_fallback_offer.provider_name = "fallback"
        mock_fallback_offer.product_id = "fallback_offer"

        mock_primary = AsyncMock()
        mock_primary.provider_name = "primary"
        mock_primary.validate_address.return_value = True
        mock_primary.get_provider_status.return_value = ProviderStatus.AVAILABLE
        mock_primary.get_offers.return_value = [mock_primary_offer]

        mock_fallback = AsyncMock()
        mock_fallback.provider_name = "fallback"
        mock_fallback.validate_address.return_value = True
        mock_fallback.get_provider_status.return_value = ProviderStatus.AVAILABLE
        mock_fallback.get_offers.return_value = [mock_fallback_offer]

        # Register providers in the registry
        await provider_registry.register_provider(mock_primary)
        await provider_registry.register_provider(mock_fallback)

        result = await provider_aggregator.get_offers_with_fallback(address, ["primary"], ["fallback"])

        # The fallback strategy returns primary offers if available, otherwise fallback offers
        assert len(result) == 1
        assert result[0].provider_name == "primary"


class TestProviderRegistry:
    @pytest.fixture
    def provider_registry(self):
        """Create ProviderRegistry instance."""
        return ProviderRegistry()

    def test_provider_registry_initialization(self, provider_registry):
        """Test ProviderRegistry initialization."""
        assert provider_registry._providers == {}
        assert provider_registry._provider_configs == {}

    @pytest.mark.asyncio
    async def test_register_provider(self, provider_registry):
        """Test provider registration."""
        mock_provider = AsyncMock()
        mock_provider.provider_name = "test-provider"
        mock_provider.provider_type.value = "api_based"
        mock_provider.supported_regions = ["DE", "AT"]

        result = await provider_registry.register_provider(mock_provider)

        assert result is True
        assert "test-provider" in provider_registry._providers
        assert provider_registry._providers["test-provider"] == mock_provider
        assert "test-provider" in provider_registry._provider_configs

    @pytest.mark.asyncio
    async def test_get_provider(self, provider_registry):
        """Test getting provider."""
        mock_provider = AsyncMock()
        mock_provider.provider_name = "test-provider"
        mock_provider.provider_type.value = "api_based"
        mock_provider.supported_regions = ["DE", "AT"]

        await provider_registry.register_provider(mock_provider)
        result = await provider_registry.get_provider("test-provider")

        assert result == mock_provider

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, provider_registry):
        """Test getting non-existent provider."""
        result = await provider_registry.get_provider("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_unregister_provider(self, provider_registry):
        """Test provider unregistration."""
        mock_provider = AsyncMock()
        mock_provider.provider_name = "test-provider"
        mock_provider.provider_type.value = "api_based"
        mock_provider.supported_regions = ["DE", "AT"]

        await provider_registry.register_provider(mock_provider)
        result = await provider_registry.unregister_provider("test-provider")

        assert result is True
        assert "test-provider" not in provider_registry._providers

    @pytest.mark.asyncio
    async def test_get_all_providers(self, provider_registry):
        """Test getting all providers."""
        mock_provider1 = AsyncMock()
        mock_provider1.provider_name = "provider1"
        mock_provider1.provider_type.value = "api_based"
        mock_provider1.supported_regions = ["DE"]

        mock_provider2 = AsyncMock()
        mock_provider2.provider_name = "provider2"
        mock_provider2.provider_type.value = "csv_based"
        mock_provider2.supported_regions = ["AT"]

        await provider_registry.register_provider(mock_provider1)
        await provider_registry.register_provider(mock_provider2)

        providers = await provider_registry.get_all_providers()
        assert len(providers) == 2
        assert mock_provider1 in providers
        assert mock_provider2 in providers

    def test_is_provider_registered(self, provider_registry):
        """Test checking if provider is registered."""
        assert provider_registry.is_provider_registered("test-provider") is False

        # Manually add to internal dict for testing
        mock_provider = Mock()
        provider_registry._providers["test-provider"] = mock_provider

        assert provider_registry.is_provider_registered("test-provider") is True

    def test_get_registered_provider_names(self, provider_registry):
        """Test getting registered provider names."""
        assert provider_registry.get_registered_provider_names() == []

        # Manually add to internal dict for testing
        mock_provider1 = Mock()
        mock_provider2 = Mock()
        provider_registry._providers["provider1"] = mock_provider1
        provider_registry._providers["provider2"] = mock_provider2

        names = provider_registry.get_registered_provider_names()
        assert "provider1" in names
        assert "provider2" in names
        assert len(names) == 2

    def test_get_provider_config(self, provider_registry):
        """Test getting provider configuration."""
        # Manually add config for testing
        provider_registry._provider_configs["test-provider"] = {
            "provider_type": "api_based",
            "supported_regions": ["DE", "AT"],
        }

        config = provider_registry.get_provider_config("test-provider")
        assert config["provider_type"] == "api_based"
        assert config["supported_regions"] == ["DE", "AT"]

    def test_get_provider_config_not_found(self, provider_registry):
        """Test getting non-existent provider configuration."""
        config = provider_registry.get_provider_config("nonexistent")
        assert config is None

    def test_get_all_provider_configs(self, provider_registry):
        """Test getting all provider configurations."""
        # Manually add configs for testing
        provider_registry._provider_configs["provider1"] = {"type": "api"}
        provider_registry._provider_configs["provider2"] = {"type": "csv"}

        configs = provider_registry.get_all_provider_configs()
        assert len(configs) == 2
        assert "provider1" in configs
        assert "provider2" in configs


class TestMockProviderService:
    @pytest.fixture
    def mock_provider(self):
        """Create MockProvider instance."""
        return MockProviderService("mock")

    def test_mock_provider_initialization(self, mock_provider):
        """Test MockProviderService initialization."""
        assert mock_provider._provider_name == "mock"
        assert mock_provider._supported_regions == ["DE", "AT", "CH"]

    @pytest.mark.asyncio
    async def test_get_offers_success(self, mock_provider):
        """Test successful get offers."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        result = await mock_provider.get_offers(address)

        assert len(result) > 0
        assert all(offer.provider_name == "mock" for offer in result)

    @pytest.mark.asyncio
    async def test_get_offers_with_error_rate(self, mock_provider):
        """Test get offers with error rate."""
        from src.domain.value_objects.address import Address

        address = Address(street="Test Street", house_number="123", city="Berlin", postal_code="10115", country="DE")

        mock_provider.set_status(ProviderStatus.UNAVAILABLE)

        with pytest.raises(Exception):
            await mock_provider.get_offers(address)

    def test_provider_name(self, mock_provider):
        """Test getting provider name."""
        assert mock_provider.provider_name == "mock"

    def test_provider_type(self, mock_provider):
        """Test getting provider type."""
        assert mock_provider.provider_type.value == "api_based"

    def test_set_status(self, mock_provider):
        """Test setting provider status."""
        mock_provider.set_status(ProviderStatus.RATE_LIMITED)
        assert mock_provider._status == ProviderStatus.RATE_LIMITED

    def test_reset_rate_limit(self, mock_provider):
        """Test resetting rate limit."""
        mock_provider.reset_rate_limit()
        assert mock_provider._rate_limit_remaining == 1000
