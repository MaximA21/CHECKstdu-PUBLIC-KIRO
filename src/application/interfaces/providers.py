"""Provider service interfaces for external internet service providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum

from ...domain.entities.provider_offer import ProviderOffer
from ...domain.value_objects.address import Address


class ProviderStatus(Enum):
    """Status of provider service availability."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class ProviderType(Enum):
    """Types of providers supported."""

    CSV_BASED = "csv_based"
    API_BASED = "api_based"
    SCRAPING_BASED = "scraping_based"
    HYBRID = "hybrid"


class IProviderService(ABC):
    """Base interface for external provider services."""

    @abstractmethod
    async def get_offers(self, address: Address) -> List[ProviderOffer]:
        """
        Get internet offers for a specific address.

        Args:
            address: Address to get offers for

        Returns:
            List[ProviderOffer]: List of available offers

        Raises:
            ProviderUnavailableException: If provider service is unavailable
            InvalidAddressException: If address is not supported by provider
        """
        pass

    @abstractmethod
    async def validate_address(self, address: Address) -> bool:
        """
        Validate if an address is supported by this provider.

        Args:
            address: Address to validate

        Returns:
            bool: True if address is supported
        """
        pass

    @abstractmethod
    async def get_provider_status(self) -> ProviderStatus:
        """
        Get current status of the provider service.

        Returns:
            ProviderStatus: Current provider status
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of the provider."""
        pass

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Get the type of the provider."""
        pass

    @property
    @abstractmethod
    def supported_regions(self) -> List[str]:
        """Get list of supported regions/countries."""
        pass

    @abstractmethod
    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Get rate limiting information for this provider.

        Returns:
            Dict[str, Any]: Rate limit information including remaining requests
        """
        pass


class IByteMe(IProviderService):
    """Interface for ByteMe provider service."""

    @abstractmethod
    async def parse_csv_data(self, csv_content: str) -> List[ProviderOffer]:
        """
        Parse CSV data from ByteMe provider.

        Args:
            csv_content: Raw CSV content

        Returns:
            List[ProviderOffer]: Parsed offers
        """
        pass

    @abstractmethod
    async def get_csv_data_for_address(self, address: Address) -> str:
        """
        Get CSV data for a specific address.

        Args:
            address: Address to get data for

        Returns:
            str: CSV content
        """
        pass


class IVerbynDich(IProviderService):
    """Interface for VerbynDich provider service."""

    @abstractmethod
    async def parse_nested_array_data(self, json_data: Dict[str, Any]) -> List[ProviderOffer]:
        """
        Parse nested array data from VerbynDich provider.

        Args:
            json_data: Raw JSON data with nested arrays

        Returns:
            List[ProviderOffer]: Parsed offers
        """
        pass

    @abstractmethod
    async def get_api_data_for_address(self, address: Address) -> Dict[str, Any]:
        """
        Get API data for a specific address.

        Args:
            address: Address to get data for

        Returns:
            Dict[str, Any]: API response data
        """
        pass


class IWebWunder(IProviderService):
    """Interface for WebWunder provider service."""

    @abstractmethod
    async def get_offers_with_metadata(self, address: Address) -> Dict[str, Any]:
        """
        Get offers with additional metadata from WebWunder.

        Args:
            address: Address to get offers for

        Returns:
            Dict[str, Any]: Offers with metadata
        """
        pass


class IPingPerfect(IProviderService):
    """Interface for PingPerfect provider service."""

    @abstractmethod
    async def sign_request(self, request_data: Dict[str, Any]) -> str:
        """
        Sign a request for PingPerfect API.

        Args:
            request_data: Data to sign

        Returns:
            str: Signed request signature
        """
        pass

    @abstractmethod
    async def get_signed_offers(self, address: Address) -> List[ProviderOffer]:
        """
        Get offers using signed requests.

        Args:
            address: Address to get offers for

        Returns:
            List[ProviderOffer]: Signed and verified offers
        """
        pass


class IProviderRegistry(ABC):
    """Interface for managing multiple provider services."""

    @abstractmethod
    async def register_provider(self, provider: IProviderService) -> bool:
        """
        Register a provider service.

        Args:
            provider: Provider service to register

        Returns:
            bool: True if registration was successful
        """
        pass

    @abstractmethod
    async def unregister_provider(self, provider_name: str) -> bool:
        """
        Unregister a provider service.

        Args:
            provider_name: Name of provider to unregister

        Returns:
            bool: True if unregistration was successful
        """
        pass

    @abstractmethod
    async def get_provider(self, provider_name: str) -> Optional[IProviderService]:
        """
        Get a registered provider by name.

        Args:
            provider_name: Name of the provider

        Returns:
            Optional[IProviderService]: Provider service or None if not found
        """
        pass

    @abstractmethod
    async def get_all_providers(self) -> List[IProviderService]:
        """
        Get all registered providers.

        Returns:
            List[IProviderService]: List of all registered providers
        """
        pass

    @abstractmethod
    async def get_available_providers(self, address: Address) -> List[IProviderService]:
        """
        Get providers that support a specific address.

        Args:
            address: Address to check support for

        Returns:
            List[IProviderService]: List of supporting providers
        """
        pass

    @abstractmethod
    async def get_provider_health_status(self) -> Dict[str, ProviderStatus]:
        """
        Get health status of all registered providers.

        Returns:
            Dict[str, ProviderStatus]: Mapping of provider names to their status
        """
        pass


class IProviderAggregator(ABC):
    """Interface for aggregating results from multiple providers."""

    @abstractmethod
    async def get_aggregated_offers(self, address: Address, provider_names: Optional[List[str]] = None) -> List[ProviderOffer]:
        """
        Get aggregated offers from multiple providers.

        Args:
            address: Address to get offers for
            provider_names: Optional list of specific providers to use

        Returns:
            List[ProviderOffer]: Aggregated list of offers from all providers
        """
        pass

    @abstractmethod
    async def get_offers_with_fallback(
        self, address: Address, primary_providers: List[str], fallback_providers: List[str]
    ) -> List[ProviderOffer]:
        """
        Get offers with fallback strategy.

        Args:
            address: Address to get offers for
            primary_providers: Primary providers to try first
            fallback_providers: Fallback providers if primary fails

        Returns:
            List[ProviderOffer]: Offers from successful providers
        """
        pass

    @abstractmethod
    async def get_parallel_offers(self, address: Address, timeout_seconds: int = 30) -> Dict[str, List[ProviderOffer]]:
        """
        Get offers from all providers in parallel.

        Args:
            address: Address to get offers for
            timeout_seconds: Timeout for each provider request

        Returns:
            Dict[str, List[ProviderOffer]]: Mapping of provider names to their offers
        """
        pass
