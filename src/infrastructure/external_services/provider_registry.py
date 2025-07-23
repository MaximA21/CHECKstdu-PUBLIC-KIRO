"""Provider registry implementation for managing multiple provider services."""

import logging
from typing import List, Dict, Any, Optional
import asyncio

from ...application.interfaces.providers import IProviderRegistry, IProviderService, ProviderStatus
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import ConfigurationException


class ProviderRegistry(IProviderRegistry):
    """Implementation of provider registry for managing multiple provider services."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize provider registry."""
        self._logger = logger or logging.getLogger(__name__)
        self._providers: Dict[str, IProviderService] = {}
        self._provider_configs: Dict[str, Dict[str, Any]] = {}

    async def register_provider(self, provider: IProviderService) -> bool:
        """Register a provider service."""
        try:
            provider_name = provider.provider_name

            # Validate provider before registration
            if not provider_name:
                raise ConfigurationException("Provider name cannot be empty")

            # Check if provider is already registered
            if provider_name in self._providers:
                self._logger.warning(f"Provider {provider_name} is already registered, replacing...")

            # Register the provider
            self._providers[provider_name] = provider

            # Store provider configuration
            self._provider_configs[provider_name] = {
                "provider_type": provider.provider_type.value,
                "supported_regions": provider.supported_regions,
                "registration_time": asyncio.get_event_loop().time(),
            }

            self._logger.info(f"Successfully registered provider: {provider_name}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to register provider {provider.provider_name}: {e}")
            return False

    async def unregister_provider(self, provider_name: str) -> bool:
        """Unregister a provider service."""
        try:
            if provider_name not in self._providers:
                self._logger.warning(f"Provider {provider_name} is not registered")
                return False

            # Remove provider and its configuration
            del self._providers[provider_name]
            if provider_name in self._provider_configs:
                del self._provider_configs[provider_name]

            self._logger.info(f"Successfully unregistered provider: {provider_name}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to unregister provider {provider_name}: {e}")
            return False

    async def get_provider(self, provider_name: str) -> Optional[IProviderService]:
        """Get a registered provider by name."""
        return self._providers.get(provider_name)

    async def get_all_providers(self) -> List[IProviderService]:
        """Get all registered providers."""
        return list(self._providers.values())

    async def get_available_providers(self, address: Address) -> List[IProviderService]:
        """Get providers that support a specific address."""
        available_providers = []

        for provider_name, provider in self._providers.items():
            try:
                # Check if provider supports the address
                if await provider.validate_address(address):
                    # Check provider status
                    status = await provider.get_provider_status()
                    if status == ProviderStatus.AVAILABLE:
                        available_providers.append(provider)
                        self._logger.debug(f"Provider {provider_name} is available for address")
                    else:
                        self._logger.debug(f"Provider {provider_name} is not available: {status.value}")
                else:
                    self._logger.debug(f"Provider {provider_name} does not support address")

            except Exception as e:
                self._logger.error(f"Error checking provider {provider_name} availability: {e}")
                continue

        self._logger.info(f"Found {len(available_providers)} available providers for address: {address.full_address}")
        return available_providers

    async def get_provider_health_status(self) -> Dict[str, ProviderStatus]:
        """Get health status of all registered providers."""
        health_status = {}

        for provider_name, provider in self._providers.items():
            try:
                status = await provider.get_provider_status()
                health_status[provider_name] = status
                self._logger.debug(f"Provider {provider_name} status: {status.value}")

            except Exception as e:
                self._logger.error(f"Error getting status for provider {provider_name}: {e}")
                health_status[provider_name] = ProviderStatus.ERROR

        return health_status

    async def get_provider_rate_limits(self) -> Dict[str, Dict[str, Any]]:
        """Get rate limit information for all registered providers."""
        rate_limits = {}

        for provider_name, provider in self._providers.items():
            try:
                rate_limit_info = await provider.get_rate_limit_info()
                rate_limits[provider_name] = rate_limit_info

            except Exception as e:
                self._logger.error(f"Error getting rate limits for provider {provider_name}: {e}")
                rate_limits[provider_name] = {"error": str(e)}

        return rate_limits

    async def get_provider_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered providers."""
        total_providers = len(self._providers)
        health_status = await self.get_provider_health_status()

        status_counts = {}
        for status in ProviderStatus:
            status_counts[status.value] = sum(1 for s in health_status.values() if s == status)

        provider_types = {}
        for provider in self._providers.values():
            provider_type = provider.provider_type.value
            provider_types[provider_type] = provider_types.get(provider_type, 0) + 1

        return {
            "total_providers": total_providers,
            "status_distribution": status_counts,
            "provider_types": provider_types,
            "registered_providers": list(self._providers.keys()),
        }

    async def validate_all_providers(self, address: Address) -> Dict[str, bool]:
        """Validate address support for all providers."""
        validation_results = {}

        for provider_name, provider in self._providers.items():
            try:
                is_valid = await provider.validate_address(address)
                validation_results[provider_name] = is_valid

            except Exception as e:
                self._logger.error(f"Error validating address for provider {provider_name}: {e}")
                validation_results[provider_name] = False

        return validation_results

    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific provider."""
        return self._provider_configs.get(provider_name)

    def get_all_provider_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all providers."""
        return self._provider_configs.copy()

    def is_provider_registered(self, provider_name: str) -> bool:
        """Check if a provider is registered."""
        return provider_name in self._providers

    def get_registered_provider_names(self) -> List[str]:
        """Get list of all registered provider names."""
        return list(self._providers.keys())

    async def refresh_provider_status(self) -> Dict[str, ProviderStatus]:
        """Refresh and return current status of all providers."""
        self._logger.info("Refreshing provider status for all registered providers")
        return await self.get_provider_health_status()

    async def get_providers_by_type(self, provider_type: str) -> List[IProviderService]:
        """Get all providers of a specific type."""
        providers_by_type = []

        for provider in self._providers.values():
            if provider.provider_type.value == provider_type:
                providers_by_type.append(provider)

        return providers_by_type

    async def get_providers_by_region(self, region: str) -> List[IProviderService]:
        """Get all providers that support a specific region."""
        providers_by_region = []

        for provider in self._providers.values():
            if region in provider.supported_regions:
                providers_by_region.append(provider)

        return providers_by_region
