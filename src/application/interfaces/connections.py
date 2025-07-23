"""Connection management interfaces for WebSocket and HTTP connections."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ...domain.entities.connection_session import ConnectionSession


class ConnectionType(Enum):
    """Types of connections supported."""

    WEBSOCKET = "websocket"
    HTTP_POLLING = "http_polling"
    SERVER_SENT_EVENTS = "sse"


class MessageType(Enum):
    """Types of messages that can be sent to connections."""

    SEARCH_INITIATED = "search_initiated"
    SEARCH_PROGRESS = "search_progress"
    SEARCH_RESULTS = "search_results"
    SEARCH_ERROR = "search_error"
    CONNECTION_STATUS = "connection_status"
    SYSTEM_MESSAGE = "system_message"


class IConnectionManager(ABC):
    """Interface for managing client connections."""

    @abstractmethod
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific connection.

        Args:
            connection_id: ID of the connection to send to
            message: Message payload to send

        Returns:
            bool: True if message was sent successfully
        """
        pass

    @abstractmethod
    async def send_to_multiple_connections(self, connection_ids: List[str], message: Dict[str, Any]) -> Dict[str, bool]:
        """
        Send a message to multiple connections.

        Args:
            connection_ids: List of connection IDs to send to
            message: Message payload to send

        Returns:
            Dict[str, bool]: Mapping of connection_id to success status
        """
        pass

    @abstractmethod
    async def broadcast_message(self, message: Dict[str, Any], connection_filter: Optional[Dict[str, Any]] = None) -> int:
        """
        Broadcast a message to all or filtered connections.

        Args:
            message: Message payload to broadcast
            connection_filter: Optional filter criteria for connections

        Returns:
            int: Number of connections the message was sent to
        """
        pass

    @abstractmethod
    async def disconnect_connection(self, connection_id: str, reason: str = "Server initiated") -> bool:
        """
        Disconnect a specific connection.

        Args:
            connection_id: ID of the connection to disconnect
            reason: Reason for disconnection

        Returns:
            bool: True if disconnection was successful
        """
        pass

    @abstractmethod
    async def is_connection_active(self, connection_id: str) -> bool:
        """
        Check if a connection is currently active.

        Args:
            connection_id: ID of the connection to check

        Returns:
            bool: True if connection is active
        """
        pass

    @abstractmethod
    async def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a connection.

        Args:
            connection_id: ID of the connection

        Returns:
            Optional[Dict[str, Any]]: Connection information or None if not found
        """
        pass

    @abstractmethod
    async def get_active_connections(self) -> List[str]:
        """
        Get list of all active connection IDs.

        Returns:
            List[str]: List of active connection IDs
        """
        pass

    @abstractmethod
    async def cleanup_stale_connections(self, timeout_minutes: int = 30) -> int:
        """
        Clean up stale/inactive connections.

        Args:
            timeout_minutes: Minutes of inactivity before considering stale

        Returns:
            int: Number of connections cleaned up
        """
        pass


class ITopicManager(ABC):
    """Interface for managing topic-based subscriptions."""

    @abstractmethod
    async def subscribe_connection_to_topic(self, connection_id: str, topic: str) -> bool:
        """
        Subscribe a connection to a topic.

        Args:
            connection_id: ID of the connection
            topic: Topic to subscribe to

        Returns:
            bool: True if subscription was successful
        """
        pass

    @abstractmethod
    async def unsubscribe_connection_from_topic(self, connection_id: str, topic: str) -> bool:
        """
        Unsubscribe a connection from a topic.

        Args:
            connection_id: ID of the connection
            topic: Topic to unsubscribe from

        Returns:
            bool: True if unsubscription was successful
        """
        pass

    @abstractmethod
    async def get_connection_topics(self, connection_id: str) -> Set[str]:
        """
        Get all topics a connection is subscribed to.

        Args:
            connection_id: ID of the connection

        Returns:
            Set[str]: Set of subscribed topics
        """
        pass

    @abstractmethod
    async def get_topic_connections(self, topic: str) -> Set[str]:
        """
        Get all connections subscribed to a topic.

        Args:
            topic: Topic to get connections for

        Returns:
            Set[str]: Set of connection IDs subscribed to the topic
        """
        pass

    @abstractmethod
    async def publish_to_topic(self, topic: str, message: Dict[str, Any]) -> int:
        """
        Publish a message to all connections subscribed to a topic.

        Args:
            topic: Topic to publish to
            message: Message payload

        Returns:
            int: Number of connections the message was sent to
        """
        pass

    @abstractmethod
    async def cleanup_topic_subscriptions(self, connection_id: str) -> int:
        """
        Clean up all topic subscriptions for a connection.

        Args:
            connection_id: ID of the connection

        Returns:
            int: Number of subscriptions cleaned up
        """
        pass


class IConnectionNotifier(ABC):
    """Interface for sending typed notifications to connections."""

    @abstractmethod
    async def notify_search_initiated(self, connection_id: str, request_id: str, share_token: str) -> bool:
        """
        Notify connection that a search has been initiated.

        Args:
            connection_id: ID of the connection
            request_id: ID of the search request
            share_token: Token for sharing results

        Returns:
            bool: True if notification was sent successfully
        """
        pass

    @abstractmethod
    async def notify_search_progress(self, connection_id: str, request_id: str, provider_name: str, status: str) -> bool:
        """
        Notify connection of search progress.

        Args:
            connection_id: ID of the connection
            request_id: ID of the search request
            provider_name: Name of the provider being processed
            status: Current status of the provider search

        Returns:
            bool: True if notification was sent successfully
        """
        pass

    @abstractmethod
    async def notify_search_results(self, connection_id: str, request_id: str, results_summary: Dict[str, Any]) -> bool:
        """
        Notify connection that search results are available.

        Args:
            connection_id: ID of the connection
            request_id: ID of the search request
            results_summary: Summary of the search results

        Returns:
            bool: True if notification was sent successfully
        """
        pass

    @abstractmethod
    async def notify_search_error(self, connection_id: str, request_id: str, error_message: str) -> bool:
        """
        Notify connection of a search error.

        Args:
            connection_id: ID of the connection
            request_id: ID of the search request
            error_message: Error message to send

        Returns:
            bool: True if notification was sent successfully
        """
        pass
