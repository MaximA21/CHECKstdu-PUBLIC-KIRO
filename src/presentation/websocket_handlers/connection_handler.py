"""WebSocket handlers for connection management using dependency injection."""

from typing import Dict, Any

from ..controllers.base_controller import WebSocketController
from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from ...application.interfaces.logging import ILogger
from ...shared.exceptions.domain import DomainException


class ConnectHandler(WebSocketController):
    """WebSocket handler for connection establishment."""

    def __init__(self, connection_management_use_case: ConnectionManagementUseCase, logger: ILogger):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebSocket connection request."""
        start_time = self._log_request_start("WebSocket Connect", {})

        try:
            # Extract connection ID
            connection_id = self._extract_connection_id(event)
            if not connection_id:
                return self._create_error_response(400, "Connection ID required")

            # Extract query parameters for connection metadata
            query_params = event.get("queryStringParameters", {}) or {}

            # Execute connection use case
            result = await self._connection_management_use_case.establish_connection(
                connection_id=connection_id, metadata=query_params
            )

            # Log success
            self._log_request_success(
                "WebSocket Connect", {"connection_id": connection_id, "session_id": result.get("session_id")}, start_time
            )

            return self._create_success_response(result)

        except DomainException as e:
            self._log_request_error(
                "WebSocket Connect",
                {"connection_id": connection_id if "connection_id" in locals() else "unknown"},
                start_time,
                e,
            )
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error(
                "WebSocket Connect",
                {"connection_id": connection_id if "connection_id" in locals() else "unknown"},
                start_time,
                e,
            )
            return self._handle_exception(e)


class DisconnectHandler(WebSocketController):
    """WebSocket handler for connection termination."""

    def __init__(self, connection_management_use_case: ConnectionManagementUseCase, logger: ILogger):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebSocket disconnection request."""
        start_time = self._log_request_start("WebSocket Disconnect", {})

        try:
            # Extract connection ID
            connection_id = self._extract_connection_id(event)
            if not connection_id:
                return self._create_error_response(400, "Connection ID required")

            # Execute disconnection use case
            result = await self._connection_management_use_case.terminate_connection(connection_id)

            # Log success
            self._log_request_success(
                "WebSocket Disconnect",
                {"connection_id": connection_id, "session_duration": result.get("session_duration_seconds")},
                start_time,
            )

            return self._create_success_response(result)

        except DomainException as e:
            self._log_request_error(
                "WebSocket Disconnect",
                {"connection_id": connection_id if "connection_id" in locals() else "unknown"},
                start_time,
                e,
            )
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error(
                "WebSocket Disconnect",
                {"connection_id": connection_id if "connection_id" in locals() else "unknown"},
                start_time,
                e,
            )
            return self._handle_exception(e)


class MessageHandler(WebSocketController):
    """WebSocket handler for incoming messages."""

    def __init__(self, connection_management_use_case: ConnectionManagementUseCase, logger: ILogger):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebSocket message."""
        start_time = self._log_request_start("WebSocket Message", {})

        try:
            # Extract connection ID and message
            connection_id = self._extract_connection_id(event)
            if not connection_id:
                return self._create_error_response(400, "Connection ID required")

            message_body = self._extract_message_body(event)
            if not message_body:
                return self._create_error_response(400, "Message body required")

            # Extract message type and data
            message_type = message_body.get("type", "unknown")
            message_data = message_body.get("data", {})

            # Process message based on type
            result = await self._process_message(connection_id, message_type, message_data)

            # Log success
            self._log_request_success(
                "WebSocket Message", {"connection_id": connection_id, "message_type": message_type}, start_time
            )

            return self._create_success_response(result)

        except DomainException as e:
            self._log_request_error(
                "WebSocket Message",
                {"connection_id": connection_id if "connection_id" in locals() else "unknown"},
                start_time,
                e,
            )
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error(
                "WebSocket Message",
                {"connection_id": connection_id if "connection_id" in locals() else "unknown"},
                start_time,
                e,
            )
            return self._handle_exception(e)

    async def _process_message(self, connection_id: str, message_type: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process different types of WebSocket messages."""
        if message_type == "ping":
            # Handle ping message
            result = await self._connection_management_use_case.handle_ping(connection_id)
            return {"type": "pong", "data": result}

        elif message_type == "status_update":
            # Handle status update request
            result = await self._connection_management_use_case.get_connection_status(connection_id)
            return {"type": "status", "data": result}

        elif message_type == "subscribe":
            # Handle subscription to updates
            topic = message_data.get("topic")
            result = await self._connection_management_use_case.subscribe_to_updates(connection_id, topic)
            return {"type": "subscription_confirmed", "data": result}

        elif message_type == "unsubscribe":
            # Handle unsubscription
            topic = message_data.get("topic")
            result = await self._connection_management_use_case.unsubscribe_from_updates(connection_id, topic)
            return {"type": "unsubscription_confirmed", "data": result}

        else:
            # Unknown message type
            self._logger.warning(
                "Unknown WebSocket message type", {"connection_id": connection_id, "message_type": message_type}
            )
            return {"type": "error", "data": {"message": f"Unknown message type: {message_type}"}}


# Lambda entry point functions
def connect_lambda_handler(event, context):
    """Lambda entry point for WebSocket connections."""
    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = ConnectHandler(
        connection_management_use_case=container.get(ConnectionManagementUseCase),
        logger=container.get_logger("websocket_connect"),
    )

    # Handle request
    import asyncio

    return asyncio.run(handler.handle_request(event))


def disconnect_lambda_handler(event, context):
    """Lambda entry point for WebSocket disconnections."""
    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = DisconnectHandler(
        connection_management_use_case=container.get(ConnectionManagementUseCase),
        logger=container.get_logger("websocket_disconnect"),
    )

    # Handle request
    import asyncio

    return asyncio.run(handler.handle_request(event))


def message_lambda_handler(event, context):
    """Lambda entry point for WebSocket messages."""
    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = MessageHandler(
        connection_management_use_case=container.get(ConnectionManagementUseCase),
        logger=container.get_logger("websocket_message"),
    )

    # Handle request
    import asyncio

    return asyncio.run(handler.handle_request(event))
