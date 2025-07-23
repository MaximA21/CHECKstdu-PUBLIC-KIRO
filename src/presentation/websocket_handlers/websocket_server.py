"""WebSocket server for container deployment with abstracted connection management."""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional, Set

from ...application.interfaces.logging import ILogger
from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from ...shared.exceptions.domain import DomainException
from ..controllers.base_controller import BaseController


class WebSocketConnection:
    """Represents a WebSocket connection in container deployment."""

    def __init__(self, connection_id: str, websocket, metadata: Dict[str, Any] = None):
        self.connection_id = connection_id
        self.websocket = websocket
        self.metadata = metadata or {}
        self.connected_at = datetime.utcnow()
        self.subscriptions: Set[str] = set()

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message to WebSocket connection."""
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception:
            return False

    async def close(self, code: int = 1000, reason: str = "Normal closure"):
        """Close WebSocket connection."""
        try:
            await self.websocket.close(code, reason)
        except Exception:
            pass


class WebSocketServerController(BaseController):
    """WebSocket server controller for container deployment."""

    def __init__(self, connection_management_use_case: ConnectionManagementUseCase, logger: ILogger):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case
        self._connections: Dict[str, WebSocketConnection] = {}

    async def handle_connection(self, websocket, path: str) -> None:
        """Handle new WebSocket connection."""
        connection_id = self._generate_connection_id()
        connection = WebSocketConnection(connection_id, websocket)

        try:
            # Register connection
            self._connections[connection_id] = connection

            # Establish connection through use case
            await self._connection_management_use_case.handle_connect(
                connection_id=connection_id, metadata={"path": path, "connected_at": connection.connected_at.isoformat()}
            )

            self._logger.info("WebSocket connection established", {"connection_id": connection_id, "path": path})

            # Send welcome message
            await connection.send_message(
                {"type": "connection_established", "connection_id": connection_id, "timestamp": datetime.utcnow().isoformat()}
            )

            # Handle messages
            await self._handle_messages(connection)

        except Exception as e:
            self._logger.error("WebSocket connection error", {"connection_id": connection_id, "error": str(e)}, exception=e)
        finally:
            # Clean up connection
            await self._cleanup_connection(connection)

    async def _handle_messages(self, connection: WebSocketConnection) -> None:
        """Handle incoming messages from WebSocket connection."""
        try:
            async for message in connection.websocket:
                try:
                    # Parse message
                    message_data = json.loads(message)

                    # Process message
                    response = await self._process_message(connection, message_data)

                    # Send response if available
                    if response:
                        await connection.send_message(response)

                except json.JSONDecodeError:
                    await connection.send_message(
                        {"type": "error", "message": "Invalid JSON format", "timestamp": datetime.utcnow().isoformat()}
                    )
                except Exception as e:
                    self._logger.error(
                        "Message processing error", {"connection_id": connection.connection_id, "error": str(e)}, exception=e
                    )

                    await connection.send_message(
                        {"type": "error", "message": "Message processing failed", "timestamp": datetime.utcnow().isoformat()}
                    )

        except Exception as e:
            self._logger.error(
                "Message handling error", {"connection_id": connection.connection_id, "error": str(e)}, exception=e
            )

    async def _process_message(
        self, connection: WebSocketConnection, message_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process different types of WebSocket messages."""
        message_type = message_data.get("type", "unknown")
        data = message_data.get("data", {})

        try:
            if message_type == "ping":
                # Handle ping message
                result = await self._connection_management_use_case.handle_ping(connection.connection_id)
                return {"type": "pong", "data": result, "timestamp": datetime.utcnow().isoformat()}

            elif message_type == "status_update":
                # Handle status update request
                result = await self._connection_management_use_case.get_connection_status(connection.connection_id)
                return {"type": "status", "data": result, "timestamp": datetime.utcnow().isoformat()}

            elif message_type == "subscribe":
                # Handle subscription to updates
                topic = data.get("topic")
                if topic:
                    connection.subscriptions.add(topic)
                    result = await self._connection_management_use_case.subscribe_to_updates(connection.connection_id, topic)
                    return {"type": "subscription_confirmed", "data": result, "timestamp": datetime.utcnow().isoformat()}
                else:
                    return {
                        "type": "error",
                        "message": "Topic required for subscription",
                        "timestamp": datetime.utcnow().isoformat(),
                    }

            elif message_type == "unsubscribe":
                # Handle unsubscription
                topic = data.get("topic")
                if topic:
                    connection.subscriptions.discard(topic)
                    result = await self._connection_management_use_case.unsubscribe_from_updates(
                        connection.connection_id, topic
                    )
                    return {"type": "unsubscription_confirmed", "data": result, "timestamp": datetime.utcnow().isoformat()}
                else:
                    return {
                        "type": "error",
                        "message": "Topic required for unsubscription",
                        "timestamp": datetime.utcnow().isoformat(),
                    }

            else:
                # Unknown message type
                self._logger.warning(
                    "Unknown WebSocket message type", {"connection_id": connection.connection_id, "message_type": message_type}
                )
                return {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except DomainException as e:
            return {"type": "error", "message": str(e), "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            self._logger.error(
                "Message processing failed",
                {"connection_id": connection.connection_id, "message_type": message_type, "error": str(e)},
                exception=e,
            )
            return {"type": "error", "message": "Internal server error", "timestamp": datetime.utcnow().isoformat()}

    async def _cleanup_connection(self, connection: WebSocketConnection) -> None:
        """Clean up WebSocket connection."""
        try:
            # Remove from connections
            if connection.connection_id in self._connections:
                del self._connections[connection.connection_id]

            # Terminate connection through use case
            await self._connection_management_use_case.handle_disconnect(connection.connection_id)

            # Close WebSocket
            await connection.close()

            self._logger.info(
                "WebSocket connection cleaned up",
                {
                    "connection_id": connection.connection_id,
                    "session_duration": (datetime.utcnow() - connection.connected_at).total_seconds(),
                },
            )

        except Exception as e:
            self._logger.error(
                "Connection cleanup error", {"connection_id": connection.connection_id, "error": str(e)}, exception=e
            )

    async def broadcast_message(self, topic: str, message: Dict[str, Any]) -> int:
        """Broadcast message to all connections subscribed to a topic."""
        sent_count = 0

        for connection in self._connections.values():
            if topic in connection.subscriptions:
                success = await connection.send_message(
                    {"type": "broadcast", "topic": topic, "data": message, "timestamp": datetime.utcnow().isoformat()}
                )
                if success:
                    sent_count += 1

        self._logger.debug(
            "Broadcast message sent",
            {"topic": topic, "connections_sent": sent_count, "total_connections": len(self._connections)},
        )

        return sent_count

    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection."""
        connection = self._connections.get(connection_id)
        if connection:
            return await connection.send_message(message)
        return False

    def get_connection_count(self) -> int:
        """Get current connection count."""
        return len(self._connections)

    def get_connections_by_topic(self, topic: str) -> int:
        """Get count of connections subscribed to a topic."""
        return sum(1 for conn in self._connections.values() if topic in conn.subscriptions)

    def _generate_connection_id(self) -> str:
        """Generate unique connection ID."""
        import uuid

        return f"conn_{uuid.uuid4().hex[:12]}"

    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request (required by base class but not used in WebSocket server)."""
        return {"error": "Direct requests not supported in WebSocket server"}

    def _create_success_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Create success response (required by base class)."""
        return {"status": "success", "data": data}

    def _create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create error response (required by base class)."""
        return {"status": "error", "message": message}
