"""Connection management use case abstracting connect/disconnect handler logic."""

from datetime import datetime
from typing import Any, Dict, Optional

from ...domain.entities.connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType
from ...shared.exceptions.domain import ConnectionException
from ..interfaces.connections import IConnectionManager
from ..interfaces.logging import ILogger
from ..interfaces.repositories import IConnectionRepository


class ConnectionManagementUseCase:
    """Use case for managing WebSocket connection lifecycle."""

    def __init__(self, connection_repository: IConnectionRepository, connection_manager: IConnectionManager, logger: ILogger):
        self._connection_repository = connection_repository
        self._connection_manager = connection_manager
        self._logger = logger

    async def handle_connect(
        self,
        connection_id: str,
        connection_type: SessionConnectionType = SessionConnectionType.WEBSOCKET,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle new connection establishment.

        Args:
            connection_id: Unique connection identifier
            connection_type: Type of connection (WebSocket, HTTP polling, etc.)
            client_info: Optional client information (IP, user agent, etc.)

        Returns:
            Dict containing connection details and status

        Raises:
            ConnectionException: If connection handling fails
        """
        try:
            self._logger.info(
                "Handling new connection", {"connection_id": connection_id, "connection_type": connection_type.value}
            )

            # Create new connection session
            connection_session = ConnectionSession.create_new(connection_id, connection_type)

            # Add client information if provided
            if client_info:
                for key, value in client_info.items():
                    connection_session.add_client_info(key, value)

            # Mark as connected
            connection_session.connect()

            # Save connection session
            await self._connection_repository.save_connection(connection_session)

            # Log successful connection
            self._logger.info(
                "Connection established successfully",
                {
                    "connection_id": connection_id,
                    "connection_type": connection_type.value,
                    "connected_at": connection_session.connected_at.isoformat(),
                },
            )

            return {
                "connection_id": connection_id,
                "status": "connected",
                "connected_at": connection_session.connected_at.isoformat(),
                "connection_type": connection_type.value,
                "message": "Connection established successfully",
            }

        except Exception as e:
            self._logger.error("Failed to handle connection", {"connection_id": connection_id, "error": str(e)}, exception=e)
            raise ConnectionException(f"Failed to establish connection: {str(e)}")

    async def handle_disconnect(self, connection_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle connection disconnection.

        Args:
            connection_id: Connection identifier to disconnect
            reason: Optional reason for disconnection

        Returns:
            Dict containing disconnection details and status

        Raises:
            ConnectionException: If disconnection handling fails
        """
        try:
            self._logger.info(
                "Handling connection disconnect", {"connection_id": connection_id, "reason": reason or "Client initiated"}
            )

            # Get existing connection session
            connection_session = await self._connection_repository.get_connection(connection_id)

            if not connection_session:
                self._logger.warning("Connection not found for disconnect", {"connection_id": connection_id})
                return {"connection_id": connection_id, "status": "not_found", "message": "Connection not found"}

            # Mark as disconnected
            connection_session.disconnect(reason)

            # Clean up any topic subscriptions
            await self._cleanup_connection_subscriptions(connection_session)

            # Update connection session
            await self._connection_repository.update_connection(connection_session)

            # Calculate connection duration for logging
            duration_seconds = (
                int(connection_session.connection_duration.total_seconds()) if connection_session.connection_duration else 0
            )

            self._logger.info(
                "Connection disconnected successfully",
                {
                    "connection_id": connection_id,
                    "reason": reason or "Client initiated",
                    "duration_seconds": duration_seconds,
                    "disconnected_at": connection_session.disconnected_at.isoformat(),
                },
            )

            return {
                "connection_id": connection_id,
                "status": "disconnected",
                "disconnected_at": connection_session.disconnected_at.isoformat(),
                "duration_seconds": duration_seconds,
                "reason": reason or "Client initiated",
                "message": "Connection disconnected successfully",
            }

        except Exception as e:
            self._logger.error("Failed to handle disconnect", {"connection_id": connection_id, "error": str(e)}, exception=e)
            raise ConnectionException(f"Failed to disconnect connection: {str(e)}")

    async def get_connection_status(self, connection_id: str) -> Dict[str, Any]:
        """
        Get current status of a connection.

        Args:
            connection_id: Connection identifier to check

        Returns:
            Dict containing connection status and details
        """
        try:
            connection_session = await self._connection_repository.get_connection(connection_id)

            if not connection_session:
                return {"connection_id": connection_id, "status": "not_found", "message": "Connection not found"}

            # Check if connection is still active via connection manager
            is_active = await self._connection_manager.is_connection_active(connection_id)

            # If connection manager says it's not active but our record says connected,
            # update our record
            if not is_active and connection_session.is_connected:
                connection_session.disconnect("Connection lost")
                await self._connection_repository.update_connection(connection_session)

            return {
                "connection_id": connection_id,
                "status": connection_session.status.value.lower(),
                "is_active": is_active,
                "connected_at": (connection_session.connected_at.isoformat() if connection_session.connected_at else None),
                "last_activity_at": (
                    connection_session.last_activity_at.isoformat() if connection_session.last_activity_at else None
                ),
                "connection_type": connection_session.connection_type.value,
                "idle_duration_seconds": (
                    int(connection_session.idle_duration.total_seconds()) if connection_session.idle_duration else None
                ),
                "subscribed_topics": list(connection_session.subscribed_topics),
            }

        except Exception as e:
            self._logger.error(
                "Failed to get connection status", {"connection_id": connection_id, "error": str(e)}, exception=e
            )
            return {"connection_id": connection_id, "status": "error", "error": str(e)}

    async def cleanup_stale_connections(self, timeout_minutes: int = 30) -> Dict[str, Any]:
        """
        Clean up stale/inactive connections.

        Args:
            timeout_minutes: Minutes of inactivity before considering stale

        Returns:
            Dict containing cleanup statistics
        """
        try:
            self._logger.info("Starting stale connection cleanup", {"timeout_minutes": timeout_minutes})

            # Get all active connections
            active_connections = await self._connection_repository.get_active_connections()

            stale_count = 0
            error_count = 0

            for connection_session in active_connections:
                try:
                    # Check if connection should timeout
                    if connection_session.should_timeout(timeout_minutes):
                        # Verify with connection manager
                        is_active = await self._connection_manager.is_connection_active(connection_session.connection_id)

                        if not is_active:
                            # Disconnect stale connection
                            connection_session.disconnect("Timeout due to inactivity")
                            await self._connection_repository.update_connection(connection_session)
                            stale_count += 1

                            self._logger.debug(
                                "Cleaned up stale connection",
                                {
                                    "connection_id": connection_session.connection_id,
                                    "idle_minutes": (
                                        int(connection_session.idle_duration.total_seconds() / 60)
                                        if connection_session.idle_duration
                                        else 0
                                    ),
                                },
                            )

                except Exception as e:
                    error_count += 1
                    self._logger.warning(
                        "Error cleaning up connection", {"connection_id": connection_session.connection_id, "error": str(e)}
                    )

            # Also use repository's cleanup method
            repo_cleanup_count = await self._connection_repository.cleanup_expired_connections(timeout_minutes)

            total_cleaned = stale_count + repo_cleanup_count

            self._logger.info(
                "Stale connection cleanup completed",
                {
                    "connections_checked": len(active_connections),
                    "stale_connections_cleaned": total_cleaned,
                    "errors": error_count,
                    "timeout_minutes": timeout_minutes,
                },
            )

            return {
                "connections_checked": len(active_connections),
                "stale_connections_cleaned": total_cleaned,
                "errors": error_count,
                "timeout_minutes": timeout_minutes,
                "status": "completed",
            }

        except Exception as e:
            self._logger.error("Failed to cleanup stale connections", {"error": str(e)}, exception=e)
            raise ConnectionException(f"Failed to cleanup stale connections: {str(e)}")

    async def subscribe_to_updates(self, connection_id: str, topic: str) -> Dict[str, Any]:
        """Subscribe a connection to topic updates."""
        try:
            # Get connection session
            connection_session = await self._connection_repository.get_connection(connection_id)
            if not connection_session:
                raise ConnectionException(f"Connection {connection_id} not found")

            # Add topic to subscriptions
            connection_session.subscribed_topics.add(topic)

            # Update in repository
            await self._connection_repository.update_connection(connection_session)

            self._logger.info("Connection subscribed to topic", {"connection_id": connection_id, "topic": topic})

            return {
                "connection_id": connection_id,
                "topic": topic,
                "subscribed": True,
                "total_subscriptions": len(connection_session.subscribed_topics),
            }

        except Exception as e:
            self._logger.error(
                "Failed to subscribe to updates",
                {"connection_id": connection_id, "topic": topic, "error": str(e)},
                exception=e,
            )
            raise ConnectionException(f"Failed to subscribe to updates: {str(e)}")

    async def unsubscribe_from_updates(self, connection_id: str, topic: str) -> Dict[str, Any]:
        """Unsubscribe a connection from topic updates."""
        try:
            # Get connection session
            connection_session = await self._connection_repository.get_connection(connection_id)
            if not connection_session:
                raise ConnectionException(f"Connection {connection_id} not found")

            # Remove topic from subscriptions
            connection_session.subscribed_topics.discard(topic)

            # Update in repository
            await self._connection_repository.update_connection(connection_session)

            self._logger.info("Connection unsubscribed from topic", {"connection_id": connection_id, "topic": topic})

            return {
                "connection_id": connection_id,
                "topic": topic,
                "subscribed": False,
                "total_subscriptions": len(connection_session.subscribed_topics),
            }

        except Exception as e:
            self._logger.error(
                "Failed to unsubscribe from updates",
                {"connection_id": connection_id, "topic": topic, "error": str(e)},
                exception=e,
            )
            raise ConnectionException(f"Failed to unsubscribe from updates: {str(e)}")

    async def handle_ping(self, connection_id: str) -> Dict[str, Any]:
        """Handle ping message from connection."""
        try:
            # Get connection session
            connection_session = await self._connection_repository.get_connection(connection_id)
            if not connection_session:
                raise ConnectionException(f"Connection {connection_id} not found")

            # Update last activity
            connection_session.update_activity()
            await self._connection_repository.update_connection(connection_session)

            return {"connection_id": connection_id, "pong": True, "timestamp": datetime.utcnow().isoformat()}

        except Exception as e:
            self._logger.error("Failed to handle ping", {"connection_id": connection_id, "error": str(e)}, exception=e)
            raise ConnectionException(f"Failed to handle ping: {str(e)}")

    async def increment_result_count_and_check_limits(self, connection_id: str) -> Dict[str, Any]:
        """
        Increment result count for a connection and check if limits are reached.

        Args:
            connection_id: Connection identifier

        Returns:
            Dict containing result count and limit status

        Raises:
            ConnectionException: If connection handling fails
        """
        try:
            self._logger.debug("Incrementing result count and checking limits", {"connection_id": connection_id})

            # Get connection session
            connection_session = await self._connection_repository.get_connection(connection_id)
            if not connection_session:
                raise ConnectionException(f"Connection {connection_id} not found")

            if not connection_session.is_connected:
                raise ConnectionException(f"Connection {connection_id} is not active")

            # Increment result count
            new_count = connection_session.increment_result_count()

            # Check if limits are reached
            should_disconnect = connection_session.should_disconnect_due_to_limits()
            disconnect_reason = None

            if should_disconnect:
                disconnect_reason = connection_session.get_disconnect_reason_for_limits()
                connection_session.disconnect(disconnect_reason)

                self._logger.info(
                    "Connection disconnected due to limits",
                    {"connection_id": connection_id, "result_count": new_count, "reason": disconnect_reason},
                )

            # Update connection session
            await self._connection_repository.update_connection(connection_session)

            # If disconnected, also close the actual connection
            if should_disconnect:
                try:
                    await self._connection_manager.disconnect_connection(connection_id, disconnect_reason)
                except Exception as e:
                    self._logger.warning(
                        "Failed to disconnect connection via connection manager",
                        {"connection_id": connection_id, "error": str(e)},
                    )

            return {
                "connection_id": connection_id,
                "result_count": new_count,
                "max_results": connection_session.max_results,
                "should_disconnect": should_disconnect,
                "disconnect_reason": disconnect_reason,
                "status": connection_session.status.value.lower(),
            }

        except Exception as e:
            self._logger.error(
                "Failed to increment result count and check limits",
                {"connection_id": connection_id, "error": str(e)},
                exception=e,
            )
            raise ConnectionException(f"Failed to handle result count: {str(e)}")

    async def check_connection_limits(self, connection_id: str) -> Dict[str, Any]:
        """
        Check if a connection has reached its limits without incrementing count.

        Args:
            connection_id: Connection identifier

        Returns:
            Dict containing limit status
        """
        try:
            connection_session = await self._connection_repository.get_connection(connection_id)
            if not connection_session:
                return {
                    "connection_id": connection_id,
                    "status": "not_found",
                    "should_disconnect": True,
                    "disconnect_reason": "Connection not found",
                }

            should_disconnect = connection_session.should_disconnect_due_to_limits()
            disconnect_reason = None

            if should_disconnect:
                disconnect_reason = connection_session.get_disconnect_reason_for_limits()

            return {
                "connection_id": connection_id,
                "result_count": connection_session.result_count,
                "max_results": connection_session.max_results,
                "should_disconnect": should_disconnect,
                "disconnect_reason": disconnect_reason,
                "status": connection_session.status.value.lower(),
                "connection_duration_minutes": (
                    int(connection_session.connection_duration.total_seconds() / 60)
                    if connection_session.connection_duration
                    else 0
                ),
                "max_connection_minutes": connection_session.max_connection_minutes,
            }

        except Exception as e:
            self._logger.error(
                "Failed to check connection limits", {"connection_id": connection_id, "error": str(e)}, exception=e
            )
            return {
                "connection_id": connection_id,
                "status": "error",
                "should_disconnect": True,
                "disconnect_reason": f"Error checking limits: {str(e)}",
            }

    async def enforce_connection_limits_for_all(self) -> Dict[str, Any]:
        """
        Check and enforce connection limits for all active connections.

        Returns:
            Dict containing enforcement statistics
        """
        try:
            self._logger.info("Starting connection limit enforcement for all connections")

            # Get all active connections
            active_connections = await self._connection_repository.get_active_connections()

            disconnected_count = 0
            error_count = 0
            checked_count = 0

            for connection_session in active_connections:
                try:
                    checked_count += 1

                    # Check if connection should be disconnected due to limits
                    if connection_session.should_disconnect_due_to_limits():
                        disconnect_reason = connection_session.get_disconnect_reason_for_limits()

                        # Disconnect the connection
                        connection_session.disconnect(disconnect_reason)
                        await self._connection_repository.update_connection(connection_session)

                        # Also disconnect via connection manager
                        try:
                            await self._connection_manager.disconnect_connection(
                                connection_session.connection_id, disconnect_reason
                            )
                        except Exception as e:
                            self._logger.warning(
                                "Failed to disconnect connection via manager",
                                {"connection_id": connection_session.connection_id, "error": str(e)},
                            )

                        disconnected_count += 1

                        self._logger.info(
                            "Connection disconnected due to limits",
                            {
                                "connection_id": connection_session.connection_id,
                                "reason": disconnect_reason,
                                "result_count": connection_session.result_count,
                                "connection_duration_minutes": (
                                    int(connection_session.connection_duration.total_seconds() / 60)
                                    if connection_session.connection_duration
                                    else 0
                                ),
                            },
                        )

                except Exception as e:
                    error_count += 1
                    self._logger.warning(
                        "Error enforcing limits for connection",
                        {"connection_id": connection_session.connection_id, "error": str(e)},
                    )

            self._logger.info(
                "Connection limit enforcement completed",
                {"connections_checked": checked_count, "connections_disconnected": disconnected_count, "errors": error_count},
            )

            return {
                "connections_checked": checked_count,
                "connections_disconnected": disconnected_count,
                "errors": error_count,
                "status": "completed",
            }

        except Exception as e:
            self._logger.error("Failed to enforce connection limits", {"error": str(e)}, exception=e)
            raise ConnectionException(f"Failed to enforce connection limits: {str(e)}")

    async def _cleanup_connection_subscriptions(self, connection_session: ConnectionSession) -> None:
        """Clean up topic subscriptions for a disconnecting connection."""
        if not connection_session.subscribed_topics:
            return

        try:
            # Note: In a real implementation, you might want to use a topic manager
            # to properly unsubscribe from all topics. For now, we just clear the set.
            connection_session.subscribed_topics.clear()

            self._logger.debug("Cleaned up connection subscriptions", {"connection_id": connection_session.connection_id})

        except Exception as e:
            self._logger.warning(
                "Failed to cleanup connection subscriptions",
                {"connection_id": connection_session.connection_id, "error": str(e)},
            )
