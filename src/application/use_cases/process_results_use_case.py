"""Process results use case abstracting logic from results_handler Lambda."""

import time
from datetime import datetime
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from .connection_management_use_case import ConnectionManagementUseCase

from ..interfaces.repositories import ISearchResultRepository
from ..interfaces.connections import IConnectionManager
from ..interfaces.providers import IProviderRegistry
from ..interfaces.logging import ILogger
from ...domain.entities.search_result import SearchResult
from ...domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import ProviderUnavailableException, ProcessingException


class ProcessResultsUseCase:
    """Use case for processing provider search results."""

    def __init__(
        self,
        search_result_repository: ISearchResultRepository,
        connection_manager: IConnectionManager,
        provider_registry: IProviderRegistry,
        logger: ILogger,
        connection_management_use_case: Optional["ConnectionManagementUseCase"] = None,
    ):
        self._search_result_repository = search_result_repository
        self._connection_manager = connection_manager
        self._provider_registry = provider_registry
        self._logger = logger
        self._connection_management_use_case = connection_management_use_case

    async def execute(
        self,
        request_id: str,
        provider_name: str,
        raw_results: Any,
        connection_id: Optional[str] = None,
        share_token: Optional[str] = None,
        address_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute process results use case.

        Args:
            request_id: ID of the search request
            provider_name: Name of the provider that returned results
            raw_results: Raw response data from the provider
            connection_id: Optional WebSocket connection ID for notifications
            share_token: Optional token for sharing results
            address_data: Optional address data from search request
            metadata: Optional metadata about the processing

        Returns:
            Dict containing processing results and statistics

        Raises:
            ProcessingException: If result processing fails
        """
        start_time = time.time()

        try:
            self._logger.info(
                "Starting process results use case",
                {"request_id": request_id, "provider_name": provider_name, "connection_id": connection_id},
            )

            # Get or create search result
            search_result = await self._get_or_create_search_result(request_id, share_token, address_data)

            # Process provider response (assuming success for now)
            processing_result = await self._process_successful_response(
                search_result, provider_name, raw_results, metadata or {}
            )

            # Update search result in repository
            await self._search_result_repository.update_result(search_result)

            # Handle connection limit checking and notification
            connection_limit_result = None
            if connection_id and self._connection_management_use_case:
                try:
                    # Increment result count and check limits
                    connection_limit_result = (
                        await self._connection_management_use_case.increment_result_count_and_check_limits(connection_id)
                    )

                    self._logger.info(
                        "Connection limit check completed",
                        {
                            "connection_id": connection_id,
                            "result_count": connection_limit_result.get("result_count", 0),
                            "should_disconnect": connection_limit_result.get("should_disconnect", False),
                            "disconnect_reason": connection_limit_result.get("disconnect_reason"),
                        },
                    )

                except Exception as e:
                    self._logger.warning(
                        "Failed to check connection limits", {"connection_id": connection_id, "error": str(e)}
                    )

            # Send notification to WebSocket connection if still active
            if connection_id and (not connection_limit_result or not connection_limit_result.get("should_disconnect", False)):
                await self._notify_connection(connection_id, request_id, provider_name, processing_result)
            elif connection_id and connection_limit_result and connection_limit_result.get("should_disconnect", False):
                # Send final notification before disconnection
                await self._notify_connection_with_disconnect_info(
                    connection_id, request_id, provider_name, processing_result, connection_limit_result
                )

            processing_time = (time.time() - start_time) * 1000

            self._logger.info(
                "Process results use case completed",
                {
                    "request_id": request_id,
                    "provider_name": provider_name,
                    "processing_time_ms": round(processing_time, 1),
                    "offers_processed": processing_result.get("offers_count", 0),
                    "connection_disconnected": (
                        connection_limit_result.get("should_disconnect", False) if connection_limit_result else False
                    ),
                },
            )

            result = {
                "request_id": request_id,
                "provider_name": provider_name,
                "status": "processed",
                "processing_time_ms": round(processing_time, 1),
                "offers_count": processing_result.get("offers_count", 0),
                "share_token": search_result.share_token,
            }

            # Add connection limit information if available
            if connection_limit_result:
                result["connection_limit_info"] = {
                    "result_count": connection_limit_result.get("result_count", 0),
                    "should_disconnect": connection_limit_result.get("should_disconnect", False),
                    "disconnect_reason": connection_limit_result.get("disconnect_reason"),
                }

            return result

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._logger.error(
                "Process results use case failed",
                {
                    "request_id": request_id,
                    "provider_name": provider_name,
                    "processing_time_ms": round(processing_time, 1),
                    "error": str(e),
                },
                exception=e,
            )

            # Still try to notify connection of failure
            try:
                await self._notify_connection_error(connection_id, request_id, provider_name, str(e))
            except:
                pass  # Don't fail the entire operation if notification fails

            raise ProcessingException(f"Failed to process results: {str(e)}")

    async def _get_or_create_search_result(
        self, request_id: str, share_token: str, address_data: Optional[Dict[str, Any]]
    ) -> SearchResult:
        """Get existing search result or create a new one."""
        # Try to get existing result by request ID
        search_result = await self._search_result_repository.get_result_by_request_id(request_id)

        if search_result:
            self._logger.debug(
                "Found existing search result", {"request_id": request_id, "share_token": search_result.share_token}
            )
            return search_result

        # Create new search result if not found
        if not address_data:
            raise ProcessingException("Address data required to create new search result")

        address = Address(
            street=address_data["street"],
            house_number=address_data["house_number"],
            city=address_data["city"],
            postal_code=address_data["postal_code"],
            country=address_data.get("country", "DE"),
        )

        search_result = SearchResult(request_id=request_id, address=address, share_token=share_token)

        await self._search_result_repository.save_result(search_result)

        self._logger.debug("Created new search result", {"request_id": request_id, "share_token": share_token})

        return search_result

    async def _process_successful_response(
        self, search_result: SearchResult, provider_name: str, raw_response: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process successful provider response."""
        # Get provider service for parsing
        provider_service = await self._provider_registry.get_provider(provider_name)
        if not provider_service:
            raise ProcessingException(f"Provider service not found: {provider_name}")

        # Parse offers based on provider type
        offers = await self._parse_provider_offers(provider_service, raw_response, search_result.address)

        # Add offers to search result
        offers_added = 0
        for offer in offers:
            try:
                search_result.add_offer(offer)
                offers_added += 1
            except ValueError as e:
                self._logger.warning(
                    "Skipped duplicate offer",
                    {"provider_name": provider_name, "product_id": offer.product_id, "error": str(e)},
                )

        # Add processing metadata
        search_result.add_metadata(f"{provider_name}_processed_at", datetime.utcnow().isoformat())
        search_result.add_metadata(f"{provider_name}_offers_count", offers_added)
        search_result.add_metadata(f"{provider_name}_metadata", metadata)

        self._logger.info(
            "Successfully processed provider response",
            {
                "provider_name": provider_name,
                "offers_parsed": len(offers),
                "offers_added": offers_added,
                "total_offers": search_result.offer_count,
            },
        )

        return {
            "status": "success",
            "offers_count": offers_added,
            "offers_data": [self._offer_to_dict(offer) for offer in offers],
            "metadata": metadata,
        }

    async def _process_failed_response(
        self, search_result: SearchResult, provider_name: str, error_details: Any, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process failed provider response."""
        error_message = str(error_details) if error_details else "Unknown error"

        # Add failure metadata
        search_result.add_metadata(f"{provider_name}_failed_at", datetime.utcnow().isoformat())
        search_result.add_metadata(f"{provider_name}_error", error_message)
        search_result.add_metadata(f"{provider_name}_metadata", metadata)

        self._logger.warning(
            "Provider response failed", {"provider_name": provider_name, "error": error_message, "metadata": metadata}
        )

        return {"status": "failed", "offers_count": 0, "error": error_message, "metadata": metadata}

    async def _parse_provider_offers(self, provider_service, raw_response: Any, address: Address) -> List[ProviderOffer]:
        """Parse provider-specific response into standardized offers."""
        try:
            # Use provider service to get offers
            offers = await provider_service.get_offers(address)
            return offers

        except Exception as e:
            self._logger.error(
                "Failed to parse provider offers",
                {"provider_name": provider_service.provider_name, "error": str(e)},
                exception=e,
            )

            # Return empty list on parsing failure
            return []

    def _offer_to_dict(self, offer: ProviderOffer) -> Dict[str, Any]:
        """Convert ProviderOffer entity to dictionary for serialization."""
        return {
            "provider_name": offer.provider_name,
            "product_id": offer.product_id,
            "speed_download_mbps": offer.speed_download_mbps,
            "speed_upload_mbps": offer.speed_upload_mbps,
            "monthly_cost_euros": float(offer.monthly_cost_euros),
            "connection_type": offer.connection_type.value,
            "contract_duration_months": offer.contract_duration_months,
            "setup_fee_euros": float(offer.setup_fee_euros) if offer.setup_fee_euros else None,
            "status": offer.status.value,
            "is_available": offer.is_available,
            "is_fiber": offer.is_fiber,
            "total_first_year_cost": float(offer.total_first_year_cost),
            "cost_per_mbps": float(offer.calculate_monthly_cost_per_mbps()),
            "additional_features": offer.additional_features,
        }

    async def _notify_connection(
        self, connection_id: str, request_id: str, provider_name: str, processing_result: Dict[str, Any]
    ) -> None:
        """Send processing result notification to WebSocket connection."""
        message = {
            "type": "PROVIDER_RESULT",
            "request_id": request_id,
            "provider": provider_name,
            "status": processing_result["status"],
            "offers": processing_result.get("offers_data", []),
            "total_offers": processing_result.get("offers_count", 0),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": processing_result.get("metadata", {}),
        }

        if processing_result["status"] == "failed":
            message["error"] = processing_result.get("error", "Unknown error")

        success = await self._connection_manager.send_to_connection(connection_id, message)

        if success:
            self._logger.debug(
                "Notification sent to connection",
                {"connection_id": connection_id, "request_id": request_id, "provider_name": provider_name},
            )
        else:
            self._logger.warning(
                "Failed to send notification to connection",
                {"connection_id": connection_id, "request_id": request_id, "provider_name": provider_name},
            )

    async def _notify_connection_error(
        self, connection_id: str, request_id: str, provider_name: str, error_message: str
    ) -> None:
        """Send error notification to WebSocket connection."""
        message = {
            "type": "PROVIDER_RESULT",
            "request_id": request_id,
            "provider": provider_name,
            "status": "processing_failed",
            "error": error_message,
            "offers": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self._connection_manager.send_to_connection(connection_id, message)

    async def _notify_connection_with_disconnect_info(
        self,
        connection_id: str,
        request_id: str,
        provider_name: str,
        processing_result: Dict[str, Any],
        connection_limit_result: Dict[str, Any],
    ) -> None:
        """Send processing result notification with disconnect information to WebSocket connection."""
        message = {
            "type": "PROVIDER_RESULT",
            "request_id": request_id,
            "provider": provider_name,
            "status": processing_result["status"],
            "offers": processing_result.get("offers_data", []),
            "total_offers": processing_result.get("offers_count", 0),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": processing_result.get("metadata", {}),
            "connection_info": {
                "will_disconnect": True,
                "disconnect_reason": connection_limit_result.get("disconnect_reason", "Limit reached"),
                "result_count": connection_limit_result.get("result_count", 0),
                "max_results": connection_limit_result.get("max_results", 5),
            },
        }

        if processing_result["status"] == "failed":
            message["error"] = processing_result.get("error", "Unknown error")

        success = await self._connection_manager.send_to_connection(connection_id, message)

        if success:
            self._logger.debug(
                "Final notification sent to connection before disconnect",
                {
                    "connection_id": connection_id,
                    "request_id": request_id,
                    "provider_name": provider_name,
                    "disconnect_reason": connection_limit_result.get("disconnect_reason"),
                },
            )
        else:
            self._logger.warning(
                "Failed to send final notification to connection",
                {"connection_id": connection_id, "request_id": request_id, "provider_name": provider_name},
            )
