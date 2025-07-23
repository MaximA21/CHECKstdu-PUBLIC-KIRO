"""Repository interfaces extending the existing IStorageService pattern."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

from ...domain.entities.search_result import SearchResult
from ...domain.entities.connection_session import ConnectionSession
from ...domain.entities.provider_offer import ProviderOffer
from ...domain.value_objects.address import Address


class ISearchResultRepository(ABC):
    """Repository interface for managing search results."""

    @abstractmethod
    async def save_result(self, result: SearchResult) -> str:
        """
        Save search result and return share token.

        Args:
            result: SearchResult entity to save

        Returns:
            str: Share token for accessing the result
        """
        pass

    @abstractmethod
    async def get_result_by_share_token(self, share_token: str) -> Optional[SearchResult]:
        """
        Get search result by share token.

        Args:
            share_token: Token to look up the result

        Returns:
            Optional[SearchResult]: Found result or None
        """
        pass

    @abstractmethod
    async def get_result_by_request_id(self, request_id: str) -> Optional[SearchResult]:
        """
        Get search result by request ID.

        Args:
            request_id: Request ID to look up the result

        Returns:
            Optional[SearchResult]: Found result or None
        """
        pass

    @abstractmethod
    async def update_result(self, result: SearchResult) -> bool:
        """
        Update an existing search result.

        Args:
            result: SearchResult entity to update

        Returns:
            bool: True if update was successful
        """
        pass

    @abstractmethod
    async def delete_result(self, share_token: str) -> bool:
        """
        Delete a search result by share token.

        Args:
            share_token: Token of the result to delete

        Returns:
            bool: True if deletion was successful
        """
        pass

    @abstractmethod
    async def get_results_by_address(self, address: Address, limit: int = 10) -> List[SearchResult]:
        """
        Get recent search results for a specific address.

        Args:
            address: Address to search for
            limit: Maximum number of results to return

        Returns:
            List[SearchResult]: List of matching results
        """
        pass


class IConnectionRepository(ABC):
    """Repository interface for managing connection sessions."""

    @abstractmethod
    async def save_connection(self, session: ConnectionSession) -> str:
        """
        Save connection session and return connection ID.

        Args:
            session: ConnectionSession entity to save

        Returns:
            str: Connection ID
        """
        pass

    @abstractmethod
    async def get_connection(self, connection_id: str) -> Optional[ConnectionSession]:
        """
        Get connection session by connection ID.

        Args:
            connection_id: Connection ID to look up

        Returns:
            Optional[ConnectionSession]: Found session or None
        """
        pass

    @abstractmethod
    async def update_connection(self, session: ConnectionSession) -> bool:
        """
        Update an existing connection session.

        Args:
            session: ConnectionSession entity to update

        Returns:
            bool: True if update was successful
        """
        pass

    @abstractmethod
    async def delete_connection(self, connection_id: str) -> bool:
        """
        Delete a connection session.

        Args:
            connection_id: Connection ID to delete

        Returns:
            bool: True if deletion was successful
        """
        pass

    @abstractmethod
    async def get_active_connections(self) -> List[ConnectionSession]:
        """
        Get all active connection sessions.

        Returns:
            List[ConnectionSession]: List of active connections
        """
        pass

    @abstractmethod
    async def cleanup_expired_connections(self, timeout_minutes: int = 30) -> int:
        """
        Clean up expired/idle connections.

        Args:
            timeout_minutes: Minutes of inactivity before considering expired

        Returns:
            int: Number of connections cleaned up
        """
        pass


class IProviderOfferRepository(ABC):
    """Repository interface for managing provider offers cache."""

    @abstractmethod
    async def save_offers(self, address: Address, provider_name: str, offers: List[ProviderOffer]) -> bool:
        """
        Save provider offers for an address.

        Args:
            address: Address the offers are for
            provider_name: Name of the provider
            offers: List of offers to save

        Returns:
            bool: True if save was successful
        """
        pass

    @abstractmethod
    async def get_cached_offers(
        self, address: Address, provider_name: str, max_age_hours: int = 24
    ) -> Optional[List[ProviderOffer]]:
        """
        Get cached offers for an address and provider.

        Args:
            address: Address to get offers for
            provider_name: Name of the provider
            max_age_hours: Maximum age of cached data in hours

        Returns:
            Optional[List[ProviderOffer]]: Cached offers or None if not found/expired
        """
        pass

    @abstractmethod
    async def invalidate_cache(self, address: Address, provider_name: Optional[str] = None) -> bool:
        """
        Invalidate cached offers for an address.

        Args:
            address: Address to invalidate cache for
            provider_name: Specific provider to invalidate, or None for all providers

        Returns:
            bool: True if invalidation was successful
        """
        pass
