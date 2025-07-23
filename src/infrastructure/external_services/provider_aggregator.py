"""Provider aggregator implementation for combining results from multiple providers."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...application.interfaces.providers import IProviderAggregator, IProviderRegistry, IProviderService, ProviderStatus
from ...domain.entities.provider_offer import ProviderOffer
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import ProviderUnavailableException


class ProviderAggregator(IProviderAggregator):
    """Implementation of provider aggregator for combining results from multiple providers."""

    def __init__(self, registry: IProviderRegistry, logger: Optional[logging.Logger] = None):
        """Initialize provider aggregator with registry."""
        self._registry = registry
        self._logger = logger or logging.getLogger(__name__)
        self._default_timeout = 30
        self._max_concurrent_requests = 10

    async def get_aggregated_offers(self, address: Address, provider_names: Optional[List[str]] = None) -> List[ProviderOffer]:
        """Get aggregated offers from multiple providers."""
        try:
            start_time = datetime.utcnow()

            # Get providers to query
            if provider_names:
                providers = []
                for name in provider_names:
                    provider = await self._registry.get_provider(name)
                    if provider:
                        providers.append(provider)
                    else:
                        self._logger.warning(f"Provider {name} not found in registry")
            else:
                providers = await self._registry.get_available_providers(address)

            if not providers:
                self._logger.warning(f"No providers available for address: {address.full_address}")
                return []

            self._logger.info(f"Aggregating offers from {len(providers)} providers for {address.full_address}")

            # Get offers from all providers concurrently
            all_offers = []
            tasks = []

            # Limit concurrent requests
            semaphore = asyncio.Semaphore(self._max_concurrent_requests)

            for provider in providers:
                task = self._get_provider_offers_with_semaphore(semaphore, provider, address)
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                provider_name = providers[i].provider_name

                if isinstance(result, Exception):
                    self._logger.error(f"Error getting offers from {provider_name}: {result}")
                    continue

                if isinstance(result, list):
                    all_offers.extend(result)
                    self._logger.info(f"Got {len(result)} offers from {provider_name}")
                else:
                    self._logger.warning(f"Unexpected result type from {provider_name}: {type(result)}")

            # Remove duplicates based on provider_name and product_id
            unique_offers = self._deduplicate_offers(all_offers)

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            self._logger.info(
                f"Aggregated {len(unique_offers)} unique offers from {len(providers)} providers in {processing_time:.2f}s"
            )

            return unique_offers

        except Exception as e:
            self._logger.error(f"Error aggregating offers: {e}")
            return []

    async def get_offers_with_fallback(
        self, address: Address, primary_providers: List[str], fallback_providers: List[str]
    ) -> List[ProviderOffer]:
        """Get offers with fallback strategy."""
        try:
            self._logger.info(f"Getting offers with fallback strategy for {address.full_address}")

            # Try primary providers first
            primary_offers = await self.get_aggregated_offers(address, primary_providers)

            if primary_offers:
                self._logger.info(f"Got {len(primary_offers)} offers from primary providers")
                return primary_offers

            # If no offers from primary, try fallback providers
            self._logger.info("No offers from primary providers, trying fallback providers")
            fallback_offers = await self.get_aggregated_offers(address, fallback_providers)

            if fallback_offers:
                self._logger.info(f"Got {len(fallback_offers)} offers from fallback providers")
                return fallback_offers

            self._logger.warning("No offers available from primary or fallback providers")
            return []

        except Exception as e:
            self._logger.error(f"Error in fallback strategy: {e}")
            return []

    async def get_parallel_offers(self, address: Address, timeout_seconds: int = 30) -> Dict[str, List[ProviderOffer]]:
        """Get offers from all providers in parallel."""
        try:
            start_time = datetime.utcnow()

            # Get all available providers
            providers = await self._registry.get_available_providers(address)

            if not providers:
                self._logger.warning(f"No providers available for address: {address.full_address}")
                return {}

            self._logger.info(f"Getting parallel offers from {len(providers)} providers with {timeout_seconds}s timeout")

            # Create tasks for each provider
            tasks = {}
            semaphore = asyncio.Semaphore(self._max_concurrent_requests)

            for provider in providers:
                task = self._get_provider_offers_with_timeout(semaphore, provider, address, timeout_seconds)
                tasks[provider.provider_name] = task

            # Wait for all tasks to complete or timeout
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

            # Process results
            parallel_results = {}
            for i, (provider_name, result) in enumerate(zip(tasks.keys(), results)):
                if isinstance(result, Exception):
                    self._logger.error(f"Error getting offers from {provider_name}: {result}")
                    parallel_results[provider_name] = []
                elif isinstance(result, list):
                    parallel_results[provider_name] = result
                    self._logger.info(f"Got {len(result)} offers from {provider_name}")
                else:
                    self._logger.warning(f"Unexpected result type from {provider_name}: {type(result)}")
                    parallel_results[provider_name] = []

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            total_offers = sum(len(offers) for offers in parallel_results.values())
            self._logger.info(f"Got {total_offers} total offers from {len(providers)} providers in {processing_time:.2f}s")

            return parallel_results

        except Exception as e:
            self._logger.error(f"Error getting parallel offers: {e}")
            return {}

    async def get_best_offers(self, address: Address, max_offers: int = 10, sort_by: str = "price") -> List[ProviderOffer]:
        """Get the best offers based on specified criteria."""
        try:
            # Get all offers
            all_offers = await self.get_aggregated_offers(address)

            if not all_offers:
                return []

            # Sort offers based on criteria
            if sort_by == "price":
                sorted_offers = sorted(all_offers, key=lambda x: x.monthly_cost_euros)
            elif sort_by == "speed":
                sorted_offers = sorted(all_offers, key=lambda x: x.speed_download_mbps, reverse=True)
            elif sort_by == "value":
                # Sort by price per Mbps
                sorted_offers = sorted(all_offers, key=lambda x: x.calculate_monthly_cost_per_mbps())
            else:
                # Default to price sorting
                sorted_offers = sorted(all_offers, key=lambda x: x.monthly_cost_euros)

            # Return top offers
            best_offers = sorted_offers[:max_offers]

            self._logger.info(f"Selected {len(best_offers)} best offers sorted by {sort_by}")
            return best_offers

        except Exception as e:
            self._logger.error(f"Error getting best offers: {e}")
            return []

    async def get_offers_by_connection_type(
        self, address: Address, connection_types: List[str]
    ) -> Dict[str, List[ProviderOffer]]:
        """Get offers filtered by connection types."""
        try:
            # Get all offers
            all_offers = await self.get_aggregated_offers(address)

            # Group by connection type
            offers_by_type = {}

            for connection_type in connection_types:
                filtered_offers = [
                    offer for offer in all_offers if offer.connection_type.value.upper() == connection_type.upper()
                ]
                offers_by_type[connection_type] = filtered_offers
                self._logger.info(f"Found {len(filtered_offers)} offers for {connection_type}")

            return offers_by_type

        except Exception as e:
            self._logger.error(f"Error getting offers by connection type: {e}")
            return {}

    async def _get_provider_offers_with_semaphore(
        self, semaphore: asyncio.Semaphore, provider: IProviderService, address: Address
    ) -> List[ProviderOffer]:
        """Get offers from a provider with semaphore control."""
        async with semaphore:
            try:
                return await provider.get_offers(address)
            except Exception as e:
                self._logger.error(f"Error getting offers from {provider.provider_name}: {e}")
                return []

    async def _get_provider_offers_with_timeout(
        self, semaphore: asyncio.Semaphore, provider: IProviderService, address: Address, timeout_seconds: int
    ) -> List[ProviderOffer]:
        """Get offers from a provider with timeout."""
        async with semaphore:
            try:
                return await asyncio.wait_for(provider.get_offers(address), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                self._logger.warning(f"Timeout getting offers from {provider.provider_name}")
                return []
            except Exception as e:
                self._logger.error(f"Error getting offers from {provider.provider_name}: {e}")
                return []

    def _deduplicate_offers(self, offers: List[ProviderOffer]) -> List[ProviderOffer]:
        """Remove duplicate offers based on provider_name and product_id."""
        seen = set()
        unique_offers = []

        for offer in offers:
            key = (offer.provider_name, offer.product_id)
            if key not in seen:
                seen.add(key)
                unique_offers.append(offer)
            else:
                self._logger.debug(f"Removing duplicate offer: {offer.provider_name} - {offer.product_id}")

        return unique_offers

    async def get_aggregation_statistics(self, address: Address) -> Dict[str, Any]:
        """Get statistics about the aggregation process."""
        try:
            start_time = datetime.utcnow()

            # Get parallel results for detailed statistics
            parallel_results = await self.get_parallel_offers(address, self._default_timeout)

            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()

            # Calculate statistics
            total_offers = sum(len(offers) for offers in parallel_results.values())
            successful_providers = len([p for p, offers in parallel_results.items() if offers])
            failed_providers = len(parallel_results) - successful_providers

            provider_stats = {}
            for provider_name, offers in parallel_results.items():
                provider_stats[provider_name] = {"offer_count": len(offers), "success": len(offers) > 0}

            return {
                "total_offers": total_offers,
                "successful_providers": successful_providers,
                "failed_providers": failed_providers,
                "processing_time_seconds": processing_time,
                "provider_statistics": provider_stats,
                "address": address.full_address,
            }

        except Exception as e:
            self._logger.error(f"Error getting aggregation statistics: {e}")
            return {}
