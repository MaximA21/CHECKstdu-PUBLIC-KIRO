"""Mock repository implementations for testing purposes."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import uuid
from copy import deepcopy

from ...application.interfaces.repositories import ISearchResultRepository, IConnectionRepository, IProviderOfferRepository
from ...domain.entities.search_result import SearchResult
from ...domain.entities.connection_session import ConnectionSession
from ...domain.entities.provider_offer import ProviderOffer
from ...domain.value_objects.address import Address


class MockSearchResultRepository(ISearchResultRepository):
    """Mock implementation of search result repository for testing."""

    def __init__(self):
        """Initialize with in-memory storage."""
        self._results_by_token: Dict[str, SearchResult] = {}
        self._results_by_request_id: Dict[str, SearchResult] = {}
        self._results_by_address: Dict[str, List[SearchResult]] = {}

    def _get_address_key(self, address: Address) -> str:
        """Generate a consistent key for address-based lookups."""
        return f"{address.normalized_postal_code}_{address.house_number.strip().lower()}_{address.city.strip().lower()}"

    async def save_result(self, result: SearchResult) -> str:
        """Save search result and return share token."""
        # Store by share token
        self._results_by_token[result.share_token] = deepcopy(result)

        # Store by request ID
        self._results_by_request_id[result.request_id] = deepcopy(result)

        # Store by address
        address_key = self._get_address_key(result.address)
        if address_key not in self._results_by_address:
            self._results_by_address[address_key] = []

        # Remove any existing result with same request_id for this address
        self._results_by_address[address_key] = [
            r for r in self._results_by_address[address_key] if r.request_id != result.request_id
        ]
        self._results_by_address[address_key].append(deepcopy(result))

        # Sort by timestamp (newest first)
        self._results_by_address[address_key].sort(key=lambda r: r.timestamp, reverse=True)

        return result.share_token

    async def get_result_by_share_token(self, share_token: str) -> Optional[SearchResult]:
        """Get search result by share token."""
        result = self._results_by_token.get(share_token)
        return deepcopy(result) if result else None

    async def get_result_by_request_id(self, request_id: str) -> Optional[SearchResult]:
        """Get search result by request ID."""
        result = self._results_by_request_id.get(request_id)
        return deepcopy(result) if result else None

    async def update_result(self, result: SearchResult) -> bool:
        """Update an existing search result."""
        if result.share_token not in self._results_by_token:
            return False

        # Update all storage locations
        self._results_by_token[result.share_token] = deepcopy(result)
        self._results_by_request_id[result.request_id] = deepcopy(result)

        # Update in address-based storage
        address_key = self._get_address_key(result.address)
        if address_key in self._results_by_address:
            for i, stored_result in enumerate(self._results_by_address[address_key]):
                if stored_result.request_id == result.request_id:
                    self._results_by_address[address_key][i] = deepcopy(result)
                    break

        return True

    async def delete_result(self, share_token: str) -> bool:
        """Delete a search result by share token."""
        if share_token not in self._results_by_token:
            return False

        result = self._results_by_token[share_token]

        # Remove from all storage locations
        del self._results_by_token[share_token]
        del self._results_by_request_id[result.request_id]

        # Remove from address-based storage
        address_key = self._get_address_key(result.address)
        if address_key in self._results_by_address:
            self._results_by_address[address_key] = [
                r for r in self._results_by_address[address_key] if r.request_id != result.request_id
            ]

            # Clean up empty address entries
            if not self._results_by_address[address_key]:
                del self._results_by_address[address_key]

        return True

    async def get_results_by_address(self, address: Address, limit: int = 10) -> List[SearchResult]:
        """Get recent search results for a specific address."""
        address_key = self._get_address_key(address)
        results = self._results_by_address.get(address_key, [])

        # Filter out expired results
        now = datetime.utcnow()
        active_results = [r for r in results if r.expires_at > now]

        # Return up to limit results
        return [deepcopy(r) for r in active_results[:limit]]

    def clear_all(self) -> None:
        """Clear all stored results (for testing)."""
        self._results_by_token.clear()
        self._results_by_request_id.clear()
        self._results_by_address.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics (for testing/debugging)."""
        return {
            "total_results": len(self._results_by_token),
            "unique_addresses": len(self._results_by_address),
            "expired_results": len([r for r in self._results_by_token.values() if r.expires_at <= datetime.utcnow()]),
        }


class MockConnectionRepository(IConnectionRepository):
    """Mock implementation of connection repository for testing."""

    def __init__(self):
        """Initialize with in-memory storage."""
        self._connections: Dict[str, ConnectionSession] = {}

    async def save_connection(self, session: ConnectionSession) -> str:
        """Save connection session and return connection ID."""
        self._connections[session.connection_id] = deepcopy(session)
        return session.connection_id

    async def get_connection(self, connection_id: str) -> Optional[ConnectionSession]:
        """Get connection session by connection ID."""
        session = self._connections.get(connection_id)
        return deepcopy(session) if session else None

    async def update_connection(self, session: ConnectionSession) -> bool:
        """Update an existing connection session."""
        if session.connection_id not in self._connections:
            return False

        self._connections[session.connection_id] = deepcopy(session)
        return True

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection session."""
        if connection_id not in self._connections:
            return False

        del self._connections[connection_id]
        return True

    async def get_active_connections(self) -> List[ConnectionSession]:
        """Get all active connection sessions."""
        active_sessions = [session for session in self._connections.values() if session.is_connected]
        return [deepcopy(session) for session in active_sessions]

    async def cleanup_expired_connections(self, timeout_minutes: int = 30) -> int:
        """Clean up expired/idle connections."""
        expired_ids = []

        for connection_id, session in self._connections.items():
            if session.should_timeout(timeout_minutes):
                expired_ids.append(connection_id)

        # Remove expired connections
        for connection_id in expired_ids:
            del self._connections[connection_id]

        return len(expired_ids)

    def clear_all(self) -> None:
        """Clear all stored connections (for testing)."""
        self._connections.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics (for testing/debugging)."""
        total = len(self._connections)
        active = len([s for s in self._connections.values() if s.is_connected])
        disconnected = len([s for s in self._connections.values() if s.is_disconnected])
        error = len([s for s in self._connections.values() if s.has_error])

        return {
            "total_connections": total,
            "active_connections": active,
            "disconnected_connections": disconnected,
            "error_connections": error,
        }


class MockProviderOfferRepository(IProviderOfferRepository):
    """Mock implementation of provider offer repository for testing."""

    def __init__(self):
        """Initialize with in-memory storage."""
        # Key format: "address_key:provider_name"
        self._cached_offers: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, address: Address, provider_name: str) -> str:
        """Generate cache key for address and provider combination."""
        address_key = f"{address.normalized_postal_code}_{address.house_number.strip().lower()}_{address.city.strip().lower()}"
        return f"{address_key}:{provider_name}"

    async def save_offers(self, address: Address, provider_name: str, offers: List[ProviderOffer]) -> bool:
        """Save provider offers for an address."""
        cache_key = self._get_cache_key(address, provider_name)

        self._cached_offers[cache_key] = {
            "offers": [deepcopy(offer) for offer in offers],
            "cached_at": datetime.utcnow(),
            "address": deepcopy(address),
            "provider_name": provider_name,
        }

        return True

    async def get_cached_offers(
        self, address: Address, provider_name: str, max_age_hours: int = 24
    ) -> Optional[List[ProviderOffer]]:
        """Get cached offers for an address and provider."""
        cache_key = self._get_cache_key(address, provider_name)
        cached_data = self._cached_offers.get(cache_key)

        if not cached_data:
            return None

        # Check if cache is expired
        cached_at = cached_data["cached_at"]
        max_age = timedelta(hours=max_age_hours)

        if datetime.utcnow() - cached_at > max_age:
            # Remove expired cache entry
            del self._cached_offers[cache_key]
            return None

        return [deepcopy(offer) for offer in cached_data["offers"]]

    async def invalidate_cache(self, address: Address, provider_name: Optional[str] = None) -> bool:
        """Invalidate cached offers for an address."""
        if provider_name:
            # Invalidate specific provider
            cache_key = self._get_cache_key(address, provider_name)
            if cache_key in self._cached_offers:
                del self._cached_offers[cache_key]
                return True
            return False
        else:
            # Invalidate all providers for this address
            address_prefix = (
                f"{address.normalized_postal_code}_{address.house_number.strip().lower()}_{address.city.strip().lower()}:"
            )
            keys_to_remove = [key for key in self._cached_offers.keys() if key.startswith(address_prefix)]

            for key in keys_to_remove:
                del self._cached_offers[key]

            return len(keys_to_remove) > 0

    def clear_all(self) -> None:
        """Clear all cached offers (for testing)."""
        self._cached_offers.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics (for testing/debugging)."""
        now = datetime.utcnow()
        expired_count = 0

        for cached_data in self._cached_offers.values():
            if now - cached_data["cached_at"] > timedelta(hours=24):
                expired_count += 1

        return {
            "total_cached_entries": len(self._cached_offers),
            "expired_entries": expired_count,
            "unique_providers": len(set(data["provider_name"] for data in self._cached_offers.values())),
        }
