"""Mock connection manager implementations for testing purposes."""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from copy import deepcopy
from collections import defaultdict
import uuid

from ...application.interfaces.connections import (
    IConnectionManager,
    ITopicManager,
    IConnectionNotifier,
    ConnectionType,
    MessageType,
)
from ...domain.entities.connection_session import ConnectionSession


class MockConnectionManager(IConnectionManager):
    """Mock implementation of connection manager for testing."""

    def __init__(self):
        """Initialize with in-memory connection storage."""
        self._connections: Dict[str, Dict[str, Any]] = {}
        self._sent_messages: List[Dict[str, Any]] = []
        self._connection_info: Dict[str, Dict[str, Any]] = {}

    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific connection."""
        if connection_id not in self._connections:
            return False

        connection = self._connections[connection_id]
        if not connection.get("active", False):
            return False

        # Record the sent message
        sent_message = {
            "connection_id": connection_id,
            "message": deepcopy(message),
            "sent_at": datetime.utcnow(),
            "message_id": str(uuid.uuid4()),
        }
        self._sent_messages.append(sent_message)

        # Update connection last activity
        connection["last_activity"] = datetime.utcnow()

        return True

    async def send_to_multiple_connections(self, connection_ids: List[str], message: Dict[str, Any]) -> Dict[str, bool]:
        """Send a message to multiple connections."""
        results = {}

        for connection_id in connection_ids:
            success = await self.send_to_connection(connection_id, message)
            results[connection_id] = success

        return results

    async def broadcast_message(self, message: Dict[str, Any], connection_filter: Optional[Dict[str, Any]] = None) -> int:
        """Broadcast a message to all or filtered connections."""
        sent_count = 0

        for connection_id, connection in self._connections.items():
            if not connection.get("active", False):
                continue

            # Apply filter if provided
            if connection_filter:
                if not self._connection_matches_filter(connection, connection_filter):
                    continue

            success = await self.send_to_connection(connection_id, message)
            if success:
                sent_count += 1

        return sent_count

    async def disconnect_connection(self, connection_id: str, reason: str = "Server initiated") -> bool:
        """Disconnect a specific connection."""
        if connection_id not in self._connections:
            return False

        connection = self._connections[connection_id]
        connection["active"] = False
        connection["disconnected_at"] = datetime.utcnow()
        connection["disconnect_reason"] = reason

        return True

    async def is_connection_active(self, connection_id: str) -> bool:
        """Check if a connection is currently active."""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        return connection.get("active", False)

    async def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a connection."""
        connection = self._connections.get(connection_id)
        if not connection:
            return None

        return deepcopy(connection)

    async def get_active_connections(self) -> List[str]:
        """Get list of all active connection IDs."""
        return [connection_id for connection_id, connection in self._connections.items() if connection.get("active", False)]

    async def cleanup_stale_connections(self, timeout_minutes: int = 30) -> int:
        """Clean up stale/inactive connections."""
        now = datetime.utcnow()
        timeout_delta = timedelta(minutes=timeout_minutes)
        stale_connections = []

        for connection_id, connection in self._connections.items():
            if not connection.get("active", False):
                continue

            last_activity = connection.get("last_activity")
            if last_activity and (now - last_activity) > timeout_delta:
                stale_connections.append(connection_id)

        # Disconnect stale connections
        for connection_id in stale_connections:
            await self.disconnect_connection(connection_id, "Timeout due to inactivity")

        return len(stale_connections)

    def _connection_matches_filter(self, connection: Dict[str, Any], filter_criteria: Dict[str, Any]) -> bool:
        """Check if a connection matches filter criteria."""
        for key, expected_value in filter_criteria.items():
            connection_value = connection.get(key)

            if isinstance(expected_value, list):
                if connection_value not in expected_value:
                    return False
            else:
                if connection_value != expected_value:
                    return False

        return True

    # Mock-specific methods for testing

    def add_mock_connection(
        self, connection_id: str, connection_type: str = "websocket", client_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a mock connection for testing."""
        self._connections[connection_id] = {
            "connection_id": connection_id,
            "connection_type": connection_type,
            "active": True,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "client_info": client_info or {},
        }

    def get_sent_messages(self, connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get sent messages for testing."""
        if connection_id:
            return [msg for msg in self._sent_messages if msg["connection_id"] == connection_id]
        return deepcopy(self._sent_messages)

    def clear_sent_messages(self) -> None:
        """Clear sent messages history (for testing)."""
        self._sent_messages.clear()

    def clear_all_connections(self) -> None:
        """Clear all connections (for testing)."""
        self._connections.clear()
        self._sent_messages.clear()
        self._connection_info.clear()


class MockTopicManager(ITopicManager):
    """Mock implementation of topic manager for testing."""

    def __init__(self):
        """Initialize with in-memory topic storage."""
        self._connection_topics: Dict[str, Set[str]] = defaultdict(set)
        self._topic_connections: Dict[str, Set[str]] = defaultdict(set)
        self._topic_messages: List[Dict[str, Any]] = []

    async def subscribe_connection_to_topic(self, connection_id: str, topic: str) -> bool:
        """Subscribe a connection to a topic."""
        self._connection_topics[connection_id].add(topic)
        self._topic_connections[topic].add(connection_id)
        return True

    async def unsubscribe_connection_from_topic(self, connection_id: str, topic: str) -> bool:
        """Unsubscribe a connection from a topic."""
        self._connection_topics[connection_id].discard(topic)
        self._topic_connections[topic].discard(connection_id)

        # Clean up empty sets
        if not self._connection_topics[connection_id]:
            del self._connection_topics[connection_id]
        if not self._topic_connections[topic]:
            del self._topic_connections[topic]

        return True

    async def get_connection_topics(self, connection_id: str) -> Set[str]:
        """Get all topics a connection is subscribed to."""
        return self._connection_topics.get(connection_id, set()).copy()

    async def get_topic_connections(self, topic: str) -> Set[str]:
        """Get all connections subscribed to a topic."""
        return self._topic_connections.get(topic, set()).copy()

    async def publish_to_topic(self, topic: str, message: Dict[str, Any]) -> int:
        """Publish a message to all connections subscribed to a topic."""
        connections = self._topic_connections.get(topic, set())

        # Record the published message
        published_message = {
            "topic": topic,
            "message": deepcopy(message),
            "published_at": datetime.utcnow(),
            "connection_count": len(connections),
            "message_id": str(uuid.uuid4()),
        }
        self._topic_messages.append(published_message)

        return len(connections)

    async def cleanup_topic_subscriptions(self, connection_id: str) -> int:
        """Clean up all topic subscriptions for a connection."""
        topics = self._connection_topics.get(connection_id, set()).copy()

        for topic in topics:
            await self.unsubscribe_connection_from_topic(connection_id, topic)

        return len(topics)

    # Mock-specific methods for testing

    def get_published_messages(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get published messages for testing."""
        if topic:
            return [msg for msg in self._topic_messages if msg["topic"] == topic]
        return deepcopy(self._topic_messages)

    def clear_published_messages(self) -> None:
        """Clear published messages history (for testing)."""
        self._topic_messages.clear()

    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions (for testing)."""
        self._connection_topics.clear()
        self._topic_connections.clear()
        self._topic_messages.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get topic manager statistics (for testing)."""
        return {
            "total_connections_with_subscriptions": len(self._connection_topics),
            "total_topics": len(self._topic_connections),
            "total_messages_published": len(self._topic_messages),
        }


class MockConnectionNotifier(IConnectionNotifier):
    """Mock implementation of connection notifier for testing."""

    def __init__(self, connection_manager: MockConnectionManager):
        """Initialize with connection manager dependency."""
        self._connection_manager = connection_manager
        self._notifications_sent: List[Dict[str, Any]] = []

    async def notify_search_initiated(self, connection_id: str, request_id: str, share_token: str) -> bool:
        """Notify connection that a search has been initiated."""
        message = {
            "type": MessageType.SEARCH_INITIATED.value,
            "request_id": request_id,
            "share_token": share_token,
            "timestamp": datetime.utcnow().isoformat(),
        }

        success = await self._connection_manager.send_to_connection(connection_id, message)

        if success:
            self._notifications_sent.append(
                {
                    "connection_id": connection_id,
                    "notification_type": "search_initiated",
                    "request_id": request_id,
                    "share_token": share_token,
                    "sent_at": datetime.utcnow(),
                }
            )

        return success

    async def notify_search_progress(self, connection_id: str, request_id: str, provider_name: str, status: str) -> bool:
        """Notify connection of search progress."""
        message = {
            "type": MessageType.SEARCH_PROGRESS.value,
            "request_id": request_id,
            "provider_name": provider_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        success = await self._connection_manager.send_to_connection(connection_id, message)

        if success:
            self._notifications_sent.append(
                {
                    "connection_id": connection_id,
                    "notification_type": "search_progress",
                    "request_id": request_id,
                    "provider_name": provider_name,
                    "status": status,
                    "sent_at": datetime.utcnow(),
                }
            )

        return success

    async def notify_search_results(self, connection_id: str, request_id: str, results_summary: Dict[str, Any]) -> bool:
        """Notify connection that search results are available."""
        message = {
            "type": MessageType.SEARCH_RESULTS.value,
            "request_id": request_id,
            "results_summary": results_summary,
            "timestamp": datetime.utcnow().isoformat(),
        }

        success = await self._connection_manager.send_to_connection(connection_id, message)

        if success:
            self._notifications_sent.append(
                {
                    "connection_id": connection_id,
                    "notification_type": "search_results",
                    "request_id": request_id,
                    "results_summary": deepcopy(results_summary),
                    "sent_at": datetime.utcnow(),
                }
            )

        return success

    async def notify_search_error(self, connection_id: str, request_id: str, error_message: str) -> bool:
        """Notify connection of a search error."""
        message = {
            "type": MessageType.SEARCH_ERROR.value,
            "request_id": request_id,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        success = await self._connection_manager.send_to_connection(connection_id, message)

        if success:
            self._notifications_sent.append(
                {
                    "connection_id": connection_id,
                    "notification_type": "search_error",
                    "request_id": request_id,
                    "error_message": error_message,
                    "sent_at": datetime.utcnow(),
                }
            )

        return success

    # Mock-specific methods for testing

    def get_notifications_sent(
        self, connection_id: Optional[str] = None, notification_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get sent notifications for testing."""
        notifications = self._notifications_sent

        if connection_id:
            notifications = [n for n in notifications if n["connection_id"] == connection_id]

        if notification_type:
            notifications = [n for n in notifications if n["notification_type"] == notification_type]

        return deepcopy(notifications)

    def clear_notifications_history(self) -> None:
        """Clear notifications history (for testing)."""
        self._notifications_sent.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get notification statistics (for testing)."""
        notification_counts = defaultdict(int)
        for notification in self._notifications_sent:
            notification_counts[notification["notification_type"]] += 1

        return {
            "total_notifications_sent": len(self._notifications_sent),
            "notification_type_breakdown": dict(notification_counts),
            "unique_connections_notified": len(set(n["connection_id"] for n in self._notifications_sent)),
        }
