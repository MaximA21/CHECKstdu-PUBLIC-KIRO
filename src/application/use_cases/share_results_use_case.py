"""Share results use case abstracting logic from share_api Lambda."""

import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ...domain.entities.provider_offer import ProviderOffer
from ...domain.entities.search_result import SearchResult
from ...shared.exceptions.domain import ShareResultsException, ShareTokenNotFoundException
from ..interfaces.logging import ILogger
from ..interfaces.repositories import ISearchResultRepository


class ShareResultsUseCase:
    """Use case for sharing search results via share tokens."""

    def __init__(self, search_result_repository: ISearchResultRepository, logger: ILogger):
        self._search_result_repository = search_result_repository
        self._logger = logger

    async def execute(self, share_token: str) -> Dict[str, Any]:
        """
        Execute share results use case.

        Args:
            share_token: Token to retrieve shared results

        Returns:
            Dict containing shared search results and metadata

        Raises:
            ShareTokenNotFoundException: If share token is not found or expired
            ShareResultsException: If result sharing fails
        """
        start_time = time.time()

        try:
            self._logger.info("Starting share results use case", {"share_token": share_token})

            # Validate share token format
            await self._validate_share_token(share_token)

            # Get search result by share token
            search_result = await self._get_search_result(share_token)

            # Check if result has expired
            await self._check_expiration(search_result)

            # Prepare shared result data
            shared_data = await self._prepare_shared_data(search_result)

            # Log access for analytics
            await self._log_share_access(search_result, shared_data)

            processing_time = (time.time() - start_time) * 1000

            self._logger.info(
                "Share results use case completed",
                {
                    "share_token": share_token,
                    "request_id": search_result.request_id,
                    "total_offers": search_result.offer_count,
                    "processing_time_ms": round(processing_time, 1),
                },
            )

            return shared_data

        except (ShareTokenNotFoundException, ShareResultsException):
            # Re-raise domain exceptions
            raise

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._logger.error(
                "Share results use case failed",
                {"share_token": share_token, "processing_time_ms": round(processing_time, 1), "error": str(e)},
                exception=e,
            )
            raise ShareResultsException(f"Failed to share results: {str(e)}")

    async def get_share_statistics(self, share_token: str) -> Dict[str, Any]:
        """
        Get statistics for a shared result.

        Args:
            share_token: Token to get statistics for

        Returns:
            Dict containing share statistics
        """
        try:
            search_result = await self._get_search_result(share_token)

            stats = search_result.get_summary_stats()

            # Add share-specific metadata
            stats.update(
                {
                    "share_token": share_token,
                    "created_at": search_result.timestamp.isoformat(),
                    "expires_at": search_result.expires_at.isoformat(),
                    "days_until_expiration": search_result.days_until_expiration,
                    "is_expired": search_result.is_expired,
                    "address": search_result.address.full_address,
                    "search_metadata": search_result.search_metadata,
                }
            )

            return stats

        except Exception as e:
            self._logger.error("Failed to get share statistics", {"share_token": share_token, "error": str(e)}, exception=e)
            raise ShareResultsException(f"Failed to get share statistics: {str(e)}")

    async def extend_share_expiration(self, share_token: str, days: int) -> Dict[str, Any]:
        """
        Extend the expiration date of a shared result.

        Args:
            share_token: Token of the result to extend
            days: Number of days to extend

        Returns:
            Dict containing updated expiration information
        """
        try:
            if days <= 0 or days > 365:
                raise ShareResultsException("Extension days must be between 1 and 365")

            search_result = await self._get_search_result(share_token)

            old_expiration = search_result.expires_at
            search_result.extend_expiration(days)

            # Update in repository
            await self._search_result_repository.update_result(search_result)

            self._logger.info(
                "Share expiration extended",
                {
                    "share_token": share_token,
                    "old_expiration": old_expiration.isoformat(),
                    "new_expiration": search_result.expires_at.isoformat(),
                    "days_extended": days,
                },
            )

            return {
                "share_token": share_token,
                "old_expiration": old_expiration.isoformat(),
                "new_expiration": search_result.expires_at.isoformat(),
                "days_extended": days,
                "status": "extended",
            }

        except Exception as e:
            self._logger.error(
                "Failed to extend share expiration", {"share_token": share_token, "days": days, "error": str(e)}, exception=e
            )
            raise ShareResultsException(f"Failed to extend expiration: {str(e)}")

    async def _validate_share_token(self, share_token: str) -> None:
        """Validate share token format."""
        if not share_token or not share_token.strip():
            raise ShareResultsException("Share token is required")

        if len(share_token) < 8:
            raise ShareResultsException("Invalid share token format")

        # Additional validation can be added here (e.g., character set validation)

    async def _get_search_result(self, share_token: str) -> SearchResult:
        """Get search result by share token."""
        search_result = await self._search_result_repository.get_result_by_share_token(share_token)

        if not search_result:
            self._logger.warning("Share token not found", {"share_token": share_token})
            raise ShareTokenNotFoundException(f"Share token not found or expired: {share_token}")

        return search_result

    async def _check_expiration(self, search_result: SearchResult) -> None:
        """Check if search result has expired."""
        if search_result.is_expired:
            self._logger.warning(
                "Attempted access to expired share",
                {
                    "share_token": search_result.share_token,
                    "expired_at": search_result.expires_at.isoformat(),
                    "request_id": search_result.request_id,
                },
            )
            raise ShareTokenNotFoundException("Share link has expired")

    async def _prepare_shared_data(self, search_result: SearchResult) -> Dict[str, Any]:
        """Prepare search result data for sharing."""
        # Get available offers and sort by best value
        available_offers = search_result.get_available_offers()

        # Sort offers by cost per Mbps (best value first)
        sorted_offers = sorted(available_offers, key=lambda offer: offer.calculate_monthly_cost_per_mbps())

        # Convert offers to dictionaries
        offers_data = [self._offer_to_dict(offer) for offer in sorted_offers]

        # Get summary statistics
        summary_stats = search_result.get_summary_stats()

        # Prepare metadata
        metadata = {
            "request_id": search_result.request_id,
            "timestamp": search_result.timestamp.isoformat(),
            "address": {
                "street": search_result.address.street,
                "house_number": search_result.address.house_number,
                "city": search_result.address.city,
                "postal_code": search_result.address.postal_code,
                "country": search_result.address.country,
                "full_address": search_result.address.full_address,
            },
            "search_metadata": search_result.search_metadata,
            "expires_at": search_result.expires_at.isoformat(),
            "days_until_expiration": search_result.days_until_expiration,
        }

        # Add best offers for quick reference
        best_offers = {
            "cheapest": (
                self._offer_to_dict(search_result.get_cheapest_offer()) if search_result.get_cheapest_offer() else None
            ),
            "fastest": self._offer_to_dict(search_result.get_fastest_offer()) if search_result.get_fastest_offer() else None,
            "best_value": (
                self._offer_to_dict(search_result.get_best_value_offer()) if search_result.get_best_value_offer() else None
            ),
        }

        return {
            "share_token": search_result.share_token,
            "metadata": metadata,
            "offers": offers_data,
            "total_offers": len(offers_data),
            "summary_stats": summary_stats,
            "best_offers": best_offers,
            "generated_at": datetime.utcnow().isoformat(),
            "share_url": f"/share/{search_result.share_token}",
        }

    def _offer_to_dict(self, offer: ProviderOffer) -> Dict[str, Any]:
        """Convert ProviderOffer entity to dictionary for API response."""
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
            "speed_ratio": offer.speed_ratio,
            "additional_features": offer.additional_features or {},
        }

    async def _log_share_access(self, search_result: SearchResult, shared_data: Dict[str, Any]) -> None:
        """Log share access for analytics purposes."""
        try:
            # Add access metadata to search result
            access_key = f"share_access_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            search_result.add_metadata(
                access_key,
                {
                    "accessed_at": datetime.utcnow().isoformat(),
                    "offers_shared": len(shared_data["offers"]),
                    "user_agent": "api_access",  # Could be enhanced with actual user agent
                },
            )

            # Update search result with access log
            await self._search_result_repository.update_result(search_result)

            self._logger.debug(
                "Share access logged",
                {
                    "share_token": search_result.share_token,
                    "request_id": search_result.request_id,
                    "offers_shared": len(shared_data["offers"]),
                },
            )

        except Exception as e:
            # Don't fail the entire operation if logging fails
            self._logger.warning("Failed to log share access", {"share_token": search_result.share_token, "error": str(e)})
