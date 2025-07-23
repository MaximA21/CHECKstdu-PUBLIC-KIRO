"""Search offers use case abstracting logic from search_handler Lambda."""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from ..interfaces.repositories import ISearchResultRepository, IConnectionRepository
from ..interfaces.messaging import IMessageQueue, MessagePriority
from ..interfaces.logging import ILogger
from ...domain.entities.search_result import SearchResult
from ...domain.entities.connection_session import ConnectionSession
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import InvalidAddressException, SearchRequestException


class SearchOffersUseCase:
    """Use case for initiating internet offer searches."""

    def __init__(
        self,
        search_result_repository: ISearchResultRepository,
        connection_repository: IConnectionRepository,
        message_queue: IMessageQueue,
        logger: ILogger,
    ):
        self._search_result_repository = search_result_repository
        self._connection_repository = connection_repository
        self._message_queue = message_queue
        self._logger = logger

    async def execute(self, address: Address, connection_id: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute search offers use case.

        Args:
            address: Address to search offers for
            connection_id: WebSocket connection ID for notifications
            request_id: Optional custom request ID

        Returns:
            Dict containing request_id, share_token, and status

        Raises:
            InvalidAddressException: If address is invalid
            SearchRequestException: If search request fails
        """
        try:
            self._logger.info(
                "Starting search offers use case", {"connection_id": connection_id, "address": address.full_address}
            )

            # Validate address
            await self._validate_address(address)

            # Verify connection exists and is active (optional for HTTP-only mode)
            connection_session = None
            if connection_id is not None:
                connection_session = await self._verify_connection(connection_id)

            # Generate request ID if not provided
            if request_id is None:
                request_id = str(uuid.uuid4())

            # Create search result entity
            search_result = SearchResult.create_new(address, request_id)

            # Save initial search result
            await self._search_result_repository.save_result(search_result)

            # Update connection session with current search (if connection exists)
            if connection_session is not None:
                await self._update_connection_with_search(connection_session, search_result)

            # Send search request to message queue for processing
            await self._queue_search_request(search_result, connection_id)

            self._logger.info(
                "Search offers use case completed successfully",
                {"request_id": request_id, "share_token": search_result.share_token, "connection_id": connection_id},
            )

            return {
                "request_id": request_id,
                "share_token": search_result.share_token,
                "status": "initiated",
                "message": "Search request processed successfully",
            }

        except InvalidAddressException as e:
            self._logger.warning("Invalid address provided", {"address": address.full_address, "error": str(e)})
            raise

        except Exception as e:
            self._logger.error("Search offers use case failed", {"connection_id": connection_id, "error": str(e)}, exception=e)
            raise SearchRequestException(f"Failed to initiate search: {str(e)}")

    async def _validate_address(self, address: Address) -> None:
        """Validate the provided address."""
        if not address:
            raise InvalidAddressException("Address is required")

        # Address validation is handled by the Address value object itself
        # Additional business logic validation can be added here

        self._logger.debug("Address validation passed", {"address": address.full_address})

    async def _verify_connection(self, connection_id: str) -> ConnectionSession:
        """Verify that the connection exists and is active."""
        connection_session = await self._connection_repository.get_connection(connection_id)

        if not connection_session:
            raise SearchRequestException(f"Connection {connection_id} not found")

        if not connection_session.is_connected:
            raise SearchRequestException(f"Connection {connection_id} is not active")

        # Update last activity
        connection_session.update_activity()
        await self._connection_repository.update_connection(connection_session)

        self._logger.debug("Connection verified", {"connection_id": connection_id, "status": connection_session.status.value})

        return connection_session

    async def _update_connection_with_search(self, connection_session: ConnectionSession, search_result: SearchResult) -> None:
        """Update connection session with current search information."""
        connection_session.add_session_data("current_request_id", search_result.request_id)
        connection_session.add_session_data("current_share_token", search_result.share_token)
        connection_session.add_session_data("last_search_address", search_result.address.full_address)
        connection_session.add_session_data("last_search_timestamp", datetime.utcnow().isoformat())

        await self._connection_repository.update_connection(connection_session)

        self._logger.debug(
            "Connection updated with search info",
            {"connection_id": connection_session.connection_id, "request_id": search_result.request_id},
        )

    async def _queue_search_request(self, search_result: SearchResult, connection_id: str) -> None:
        """Queue the search request for processing by provider services."""
        message = {
            "request_id": search_result.request_id,
            "connection_id": connection_id,
            "address": {
                "street": search_result.address.street,
                "house_number": search_result.address.house_number,
                "city": search_result.address.city,
                "postal_code": search_result.address.postal_code,
                "country": search_result.address.country,
            },
            "share_token": search_result.share_token,
            "timestamp": datetime.utcnow().isoformat(),
            "search_metadata": search_result.search_metadata,
        }

        # Send to search queue with normal priority
        message_id = await self._message_queue.send_message(
            queue_name="search_requests", message=message, priority=MessagePriority.NORMAL
        )

        self._logger.info(
            "Search request queued",
            {"request_id": search_result.request_id, "message_id": message_id, "queue": "search_requests"},
        )
