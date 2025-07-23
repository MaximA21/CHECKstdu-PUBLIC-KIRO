"""Example demonstrating the use of presentation layer controllers."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

from src.application.interfaces.logging import ILogger

# Import the controllers
from src.presentation.controllers.base_controller import ContainerController, HTTPController, WebSocketController
from src.presentation.http_controllers.share_controller import ShareController
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
from src.presentation.websocket_handlers.connection_handler import ConnectHandler


class MockLogger:
    """Mock logger for demonstration."""

    def info(self, message, context=None, **kwargs):
        print(f"INFO: {message} {context or ''}")

    def error(self, message, context=None, exception=None, **kwargs):
        print(f"ERROR: {message} {context or ''}")

    def debug(self, message, context=None, **kwargs):
        print(f"DEBUG: {message} {context or ''}")

    def warning(self, message, context=None, **kwargs):
        print(f"WARNING: {message} {context or ''}")


async def demonstrate_lambda_handler():
    """Demonstrate Lambda handler usage."""
    print("\n=== Lambda Handler Example ===")

    # Mock use case
    share_use_case = AsyncMock()
    share_use_case.execute.return_value = {
        "share_token": "abc123",
        "total_offers": 3,
        "offers": [{"provider": "TestProvider", "speed": 100, "price": 29.99}],
        "metadata": {"address": "Test Street 1, Test City"},
    }

    # Create handler
    logger = MockLogger()
    handler = ShareApiHandler(share_use_case, logger)

    # Simulate Lambda event
    lambda_event = {"pathParameters": {"share_token": "abc123"}, "requestContext": {"requestId": "test-request-123"}}

    # Handle request
    response = await handler.handle_request(lambda_event)

    print(f"Lambda Response Status: {response['statusCode']}")
    print(f"Lambda Response Body: {json.loads(response['body'])}")


async def demonstrate_container_controller():
    """Demonstrate container controller usage."""
    print("\n=== Container Controller Example ===")

    # Mock use case
    share_use_case = AsyncMock()
    share_use_case.execute.return_value = {
        "share_token": "xyz789",
        "total_offers": 5,
        "offers": [{"provider": "ContainerProvider", "speed": 200, "price": 39.99}],
    }

    # Create controller
    logger = MockLogger()
    controller = ShareController(share_use_case, logger)

    # Simulate container request
    container_request = {
        "path_params": {"share_token": "xyz789"},
        "method": "GET",
        "headers": {"Content-Type": "application/json"},
    }

    # Handle request
    response = await controller.handle_request(container_request)

    print(f"Container Response Status: {response['status_code']}")
    print(f"Container Response Data: {response['data']}")


async def demonstrate_websocket_handler():
    """Demonstrate WebSocket handler usage."""
    print("\n=== WebSocket Handler Example ===")

    # Mock use case
    connection_use_case = AsyncMock()
    connection_use_case.establish_connection.return_value = {
        "connection_id": "ws_conn_123",
        "session_id": "session_456",
        "status": "connected",
    }

    # Create handler
    logger = MockLogger()
    handler = ConnectHandler(connection_use_case, logger)

    # Simulate WebSocket event
    websocket_event = {
        "requestContext": {"connectionId": "ws_conn_123", "routeKey": "$connect"},
        "queryStringParameters": {"user_id": "user123", "client_type": "web"},
    }

    # Handle connection
    response = await handler.handle_request(websocket_event)

    print(f"WebSocket Response Status: {response['statusCode']}")
    print(f"WebSocket Response Body: {json.loads(response['body'])}")


class CustomHTTPController(HTTPController):
    """Example of creating a custom HTTP controller."""

    def __init__(self, logger):
        super().__init__(logger)
        self.request_count = 0

    async def handle_request(self, request_data):
        """Handle custom request logic."""
        self.request_count += 1

        # Extract data
        method = request_data.get("httpMethod", "GET")
        path = request_data.get("path", "/")

        # Log request
        self._logger.info(
            "Custom controller handling request", {"method": method, "path": path, "request_number": self.request_count}
        )

        # Custom business logic
        if path == "/health":
            return self._create_success_response(
                {"status": "healthy", "request_count": self.request_count, "timestamp": "2024-01-01T12:00:00Z"}
            )
        elif path == "/error":
            return self._create_error_response(500, "Simulated error")
        else:
            return self._create_success_response({"message": "Custom controller response", "path": path, "method": method})


async def demonstrate_custom_controller():
    """Demonstrate custom controller creation."""
    print("\n=== Custom Controller Example ===")

    logger = MockLogger()
    controller = CustomHTTPController(logger)

    # Test different endpoints
    requests = [
        {"httpMethod": "GET", "path": "/health"},
        {"httpMethod": "POST", "path": "/api/data"},
        {"httpMethod": "GET", "path": "/error"},
    ]

    for request in requests:
        response = await controller.handle_request(request)
        print(f"Request {request['path']}: Status {response['statusCode']}")
        if response["statusCode"] == 200:
            body = json.loads(response["body"])
            print(f"  Response: {body}")


async def demonstrate_error_handling():
    """Demonstrate error handling in controllers."""
    print("\n=== Error Handling Example ===")

    # Mock use case that raises exceptions
    share_use_case = AsyncMock()

    # Import exception types
    from src.shared.exceptions.domain import ShareTokenNotFoundException

    share_use_case.execute.side_effect = ShareTokenNotFoundException("Token not found")

    # Create handler
    logger = MockLogger()
    handler = ShareApiHandler(share_use_case, logger)

    # Test error handling
    event = {"pathParameters": {"share_token": "invalid_token"}}
    response = await handler.handle_request(event)

    print(f"Error Response Status: {response['statusCode']}")
    print(f"Error Response Body: {response['body']}")


async def main():
    """Run all demonstrations."""
    print("Presentation Layer Controllers Demonstration")
    print("=" * 50)

    await demonstrate_lambda_handler()
    await demonstrate_container_controller()
    await demonstrate_websocket_handler()
    await demonstrate_custom_controller()
    await demonstrate_error_handling()

    print("\n" + "=" * 50)
    print("All demonstrations completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
