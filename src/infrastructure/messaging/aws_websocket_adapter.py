"""AWS API Gateway WebSocket connection manager adapter implementation."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import boto3
from botocore.exceptions import ClientError

from ...application.interfaces.connections import (
    ConnectionType,
    IConnectionManager,
    IConnectionNotifier,
    ITopicManager,
    MessageType,
)
from ...application.interfaces.repositories import IConnectionRepository
from ...domain.entities.connection_session import ConnectionSession

logger = logging.getLogger(__name__)


class AWSAPIGatewayWebSocketManager(IConnectionManager):
    """AWS API Gateway WebSocket implementation of connection manager interface."""

    def __init__(
        self,
        api_endpoint: str,
        region_name: str = "eu-central-1",
        connection_repository: Optional[IConnectionRepository] = None,
    ):
        """
        Initialize AWS API Gateway WebSocket manager.

        Args:
            api_endpoint: API Gateway WebSocket endpoint URL
            region_name: AWS region name
            connection_repository: Optional repository for connection persistence
        """
        self.api_endpoint = api_endpoint.rstrip("/")
        self.region_name = region_name
        self.connection_repository = connection_repository

        # Initialize API Gateway Management API client
        self._apigw_management = boto3.client(
            "apigatewaymanagementapi", endpoint_url=f"https://{api_endpoint}", region_name=region_name
        )

        logger.info(f"Initialized AWS WebSocket manager for endpoint: {api_endpoint}")

    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific connection."""
        try:
            # Serialize message
            message_data = json.dumps(message, default=str, separators=(",", ":")).encode("utf-8")

            # Send via API Gateway
            self._apigw_management.post_to_connection(ConnectionId=connection_id, Data=message_data)

            logger.debug(f"Sent message to connection {connection_id}")

            # Update last activity if repository is available
            if self.connection_repository:
                try:
                    session = await self.connection_repository.get_connection(connection_id)
                    if session and session.is_connected:
                        session.update_activity()
                        await self.connection_repository.update_connection(session)
                except Exception as e:
                    logger.warning(f"Failed to update connection activity: {e}")

            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            if error_code == "GoneException":
                logger.info(f"Connection {connection_id} is no longer available")
                # Mark connection as disconnected if repository is available
                if self.connection_repository:
                    try:
                        session = await self.connection_repository.get_connection(connection_id)
                        if session:
                            session.disconnect("Connection gone")
                            await self.connection_repository.update_connection(session)
                    except Exception:
                        pass  # Ignore repository errors

                return False
            else:
                logger.error(f"Failed to send message to {connection_id}: {e}")
                return False
        except json.JSONEncodeError as e:
            logger.error(f"Failed to serialize message: {e}")
            return False

    async def send_to_multiple_connections(self, connection_ids: List[str], message: Dict[str, Any]) -> Dict[str, bool]:
        """Send a message to multiple connections."""
        results = {}

        # Serialize message once
        try:
            message_data = json.dumps(message, default=str, separators=(",", ":")).encode("utf-8")
        except json.JSONEncodeError as e:
            logger.error(f"Failed to serialize message: {e}")
            return {conn_id: False for conn_id in connection_ids}

        # Send to each connection
        for connection_id in connection_ids:
            try:
                self._apigw_management.post_to_connection(ConnectionId=connection_id, Data=message_data)
                results[connection_id] = True
                logger.debug(f"Sent message to connection {connection_id}")

            except ClientError as e:
                error_code = e.response["Error"]["Code"]

                if error_code == "GoneException":
                    logger.info(f"Connection {connection_id} is no longer available")
                    # Mark connection as disconnected if repository is available
                    if self.connection_repository:
                        try:
                            session = await self.connection_repository.get_connection(connection_id)
                            if session:
                                session.disconnect("Connection gone")
                                await self.connection_repository.update_connection(session)
                        except Exception:
                            pass  # Ignore repository errors
                else:
                    logger.error(f"Failed to send message to {connection_id}: {e}")

                results[connection_id] = False

        successful_sends = sum(1 for success in results.values() if success)
        logger.info(f"Sent message to {successful_sends}/{len(connection_ids)} connections")

        return results

    async def broadcast_message(self, message: Dict[str, Any], connection_filter: Optional[Dict[str, Any]] = None) -> int:
        """Broadcast a message to all or filtered connections."""
        if not self.connection_repository:
            logger.warning("Cannot broadcast without connection repository")
            return 0

        try:
            # Get active connections
            active_connections = await self.connection_repository.get_active_connections()

            # Apply filter if provided
            if connection_filter:
                filtered_connections = []
                for session in active_connections:
                    # Simple filter implementation - can be extended
                    if self._matches_filter(session, connection_filter):
                        filtered_connections.append(session)
                active_connections = filtered_connections

            # Extract connection IDs
            connection_ids = [session.connection_id for session in active_connections]

            if not connection_ids:
                logger.info("No active connections found for broadcast")
                return 0

            # Send to all connections
            results = await self.send_to_multiple_connections(connection_ids, message)

            successful_sends = sum(1 for success in results.values() if success)
            logger.info(f"Broadcast message to {successful_sends} connections")

            return successful_sends

        except Exception as e:
            logger.error(f"Failed to broadcast message: {e}")
            return 0

    def _matches_filter(self, session: ConnectionSession, filter_criteria: Dict[str, Any]) -> bool:
        """Check if a connection session matches filter criteria."""
        # Simple implementation - can be extended based on requirements
        for key, value in filter_criteria.items():
            if key == "connection_type":
                if session.connection_type.value != value:
                    return False
            elif key == "has_topic":
                if value not in session.subscribed_topics:
                    return False
            elif key == "client_info":
                for info_key, info_value in value.items():
                    if session.get_client_info(info_key) != info_value:
                        return False

        return True

    async def disconnect_connection(self, connection_id: str, reason: str = "Server initiated") -> bool:
        """Disconnect a specific connection."""
        try:
            # API Gateway doesn't have a direct disconnect method
            # We'll send a disconnect message and update the repository

            disconnect_message = {"type": "DISCONNECT", "reason": reason, "timestamp": datetime.utcnow().isoformat()}

            # Try to send disconnect message
            await self.send_to_connection(connection_id, disconnect_message)

            # Update repository
            if self.connection_repository:
                session = await self.connection_repository.get_connection(connection_id)
                if session:
                    session.disconnect(reason)
                    await self.connection_repository.update_connection(session)

            logger.info(f"Disconnected connection {connection_id}: {reason}")
            return True

        except Exception as e:
            logger.error(f"Failed to disconnect connection {connection_id}: {e}")
            return False

    async def is_connection_active(self, connection_id: str) -> bool:
        """Check if a connection is currently active."""
        # Try to send a ping message
        try:
            ping_message = {"type": "PING", "timestamp": datetime.utcnow().isoformat()}

            return await self.send_to_connection(connection_id, ping_message)

        except Exception:
            return False

    async def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a connection."""
        if not self.connection_repository:
            return None

        try:
            session = await self.connection_repository.get_connection(connection_id)
            if session:
                return session.get_connection_summary()
            return None

        except Exception as e:
            logger.error(f"Failed to get connection info for {connection_id}: {e}")
            return None

    async def get_active_connections(self) -> List[str]:
        """Get list of all active connection IDs."""
        if not self.connection_repository:
            return []

        try:
            active_sessions = await self.connection_repository.get_active_connections()
            return [session.connection_id for session in active_sessions]

        except Exception as e:
            logger.error(f"Failed to get active connections: {e}")
            return []

    async def cleanup_stale_connections(self, timeout_minutes: int = 30) -> int:
        """Clean up stale/inactive connections."""
        if not self.connection_repository:
            return 0

        try:
            return await self.connection_repository.cleanup_expired_connections(timeout_minutes)

        except Exception as e:
            logger.error(f"Failed to cleanup stale connections: {e}")
            return 0


class AWSWebSocketTopicManager(ITopicManager):
    """AWS WebSocket topic manager implementation using connection repository."""

    def __init__(self, connection_repository: IConnectionRepository, connection_manager: IConnectionManager):
        """
        Initialize topic manager.

        Args:
            connection_repository: Repository for connection persistence
            connection_manager: Connection manager for sending messages
        """
        self.connection_repository = connection_repository
        self.connection_manager = connection_manager

        logger.info("Initialized AWS WebSocket topic manager")

    async def subscribe_connection_to_topic(self, connection_id: str, topic: str) -> bool:
        """Subscribe a connection to a topic."""
        try:
            session = await self.connection_repository.get_connection(connection_id)
            if not session or not session.is_connected:
                logger.warning(f"Connection {connection_id} not found or not connected")
                return False

            session.subscribe_to_topic(topic)
            await self.connection_repository.update_connection(session)

            logger.info(f"Subscribed connection {connection_id} to topic {topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe connection {connection_id} to topic {topic}: {e}")
            return False

    async def unsubscribe_connection_from_topic(self, connection_id: str, topic: str) -> bool:
        """Unsubscribe a connection from a topic."""
        try:
            session = await self.connection_repository.get_connection(connection_id)
            if not session:
                return False

            session.unsubscribe_from_topic(topic)
            await self.connection_repository.update_connection(session)

            logger.info(f"Unsubscribed connection {connection_id} from topic {topic}")
            return True

        except Exception as e:
            logger.error(f"Failed to unsubscribe connection {connection_id} from topic {topic}: {e}")
            return False

    async def get_connection_topics(self, connection_id: str) -> Set[str]:
        """Get all topics a connection is subscribed to."""
        try:
            session = await self.connection_repository.get_connection(connection_id)
            if session:
                return session.subscribed_topics
            return set()

        except Exception as e:
            logger.error(f"Failed to get topics for connection {connection_id}: {e}")
            return set()

    async def get_topic_connections(self, topic: str) -> Set[str]:
        """Get all connections subscribed to a topic."""
        try:
            active_sessions = await self.connection_repository.get_active_connections()

            subscribed_connections = set()
            for session in active_sessions:
                if session.is_subscribed_to(topic):
                    subscribed_connections.add(session.connection_id)

            return subscribed_connections

        except Exception as e:
            logger.error(f"Failed to get connections for topic {topic}: {e}")
            return set()

    async def publish_to_topic(self, topic: str, message: Dict[str, Any]) -> int:
        """Publish a message to all connections subscribed to a topic."""
        try:
            subscribed_connections = await self.get_topic_connections(topic)

            if not subscribed_connections:
                logger.info(f"No connections subscribed to topic {topic}")
                return 0

            # Add topic information to message
            topic_message = {**message, "topic": topic, "message_type": "TOPIC_MESSAGE"}

            # Send to all subscribed connections
            results = await self.connection_manager.send_to_multiple_connections(list(subscribed_connections), topic_message)

            successful_sends = sum(1 for success in results.values() if success)
            logger.info(f"Published message to topic {topic}: {successful_sends} connections")

            return successful_sends

        except Exception as e:
            logger.error(f"Failed to publish to topic {topic}: {e}")
            return 0

    async def cleanup_topic_subscriptions(self, connection_id: str) -> int:
        """Clean up all topic subscriptions for a connection."""
        try:
            session = await self.connection_repository.get_connection(connection_id)
            if not session:
                return 0

            topic_count = len(session.subscribed_topics)
            session.subscribed_topics.clear()
            await self.connection_repository.update_connection(session)

            logger.info(f"Cleaned up {topic_count} topic subscriptions for connection {connection_id}")
            return topic_count

        except Exception as e:
            logger.error(f"Failed to cleanup topic subscriptions for connection {connection_id}: {e}")
            return 0


class AWSWebSocketNotifier(IConnectionNotifier):
    """AWS WebSocket connection notifier implementation."""

    def __init__(self, connection_manager: IConnectionManager):
        """
        Initialize connection notifier.

        Args:
            connection_manager: Connection manager for sending messages
        """
        self.connection_manager = connection_manager

        logger.info("Initialized AWS WebSocket notifier")

    async def notify_search_initiated(self, connection_id: str, request_id: str, share_token: str) -> bool:
        """Notify connection that a search has been initiated."""
        message = {
            "type": MessageType.SEARCH_INITIATED.value,
            "request_id": request_id,
            "share_token": share_token,
            "message": "Search initiated successfully",
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self.connection_manager.send_to_connection(connection_id, message)

    async def notify_search_progress(self, connection_id: str, request_id: str, provider_name: str, status: str) -> bool:
        """Notify connection of search progress."""
        message = {
            "type": MessageType.SEARCH_PROGRESS.value,
            "request_id": request_id,
            "provider_name": provider_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self.connection_manager.send_to_connection(connection_id, message)

    async def notify_search_results(self, connection_id: str, request_id: str, results_summary: Dict[str, Any]) -> bool:
        """Notify connection that search results are available."""
        message = {
            "type": MessageType.SEARCH_RESULTS.value,
            "request_id": request_id,
            "results_summary": results_summary,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self.connection_manager.send_to_connection(connection_id, message)

    async def notify_search_error(self, connection_id: str, request_id: str, error_message: str) -> bool:
        """Notify connection of a search error."""
        message = {
            "type": MessageType.SEARCH_ERROR.value,
            "request_id": request_id,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return await self.connection_manager.send_to_connection(connection_id, message)
