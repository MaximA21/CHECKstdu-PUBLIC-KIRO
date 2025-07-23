"""Standalone WebSocket server for container deployment."""

import asyncio
import json
import websockets
from typing import Dict, Any, Optional, Set
from datetime import datetime
from websockets.server import WebSocketServerProtocol

from ..shared.dependency_injection.container import DIContainer
from ..shared.dependency_injection.bootstrap import get_container
from ..infrastructure.config.loader import ConfigLoader
from ..application.interfaces.logging import ILogger
from .websocket_handlers.websocket_server import WebSocketServerController


class StandaloneWebSocketServer:
    """Standalone WebSocket server for container deployment."""

    def __init__(self, config_dir: Optional[str] = None, port: int = 8081, host: str = "0.0.0.0"):
        """Initialize WebSocket server.

        Args:
            config_dir: Configuration directory path
            port: Server port
            host: Server host
        """
        self.host = host
        self.port = port
        self.config_loader = ConfigLoader(config_dir)
        self.container: Optional[DIContainer] = None
        self.logger: Optional[ILogger] = None
        self.websocket_controller: Optional[WebSocketServerController] = None
        self.server = None
        self.connections: Set[WebSocketServerProtocol] = set()

    async def initialize(self) -> None:
        """Initialize server dependencies."""
        try:
            # Load configuration
            config = self.config_loader.load_config()

            # Get dependency injection container
            self.container = get_container()

            # Get logger
            self.logger = self.container.get_logger("websocket_server")

            # Initialize WebSocket controller
            self.websocket_controller = self.container.resolve(WebSocketServerController)

            self.logger.info(
                "WebSocket server initialized", {"host": self.host, "port": self.port, "environment": config.environment.value}
            )

        except Exception as e:
            if self.logger:
                self.logger.error("Failed to initialize WebSocket server", {"error": str(e)}, exception=e)
            raise

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle new WebSocket connection."""
        self.connections.add(websocket)

        try:
            self.logger.info(
                "New WebSocket connection",
                {"remote_address": websocket.remote_address, "path": path, "total_connections": len(self.connections)},
            )

            # Create a wrapper that matches the expected interface
            websocket_wrapper = WebSocketWrapper(websocket)

            # Delegate to controller
            await self.websocket_controller.handle_connection(websocket_wrapper, path)

        except websockets.exceptions.ConnectionClosed:
            self.logger.info("WebSocket connection closed normally", {"remote_address": websocket.remote_address})
        except Exception as e:
            self.logger.error(
                "WebSocket connection error", {"remote_address": websocket.remote_address, "error": str(e)}, exception=e
            )
        finally:
            self.connections.discard(websocket)
            self.logger.debug("WebSocket connection cleaned up", {"total_connections": len(self.connections)})

    async def start(self) -> None:
        """Start the WebSocket server."""
        if not self.websocket_controller:
            await self.initialize()

        self.logger.info("Starting WebSocket server", {"host": self.host, "port": self.port})

        # Start WebSocket server
        self.server = await websockets.serve(
            self.handle_connection, self.host, self.port, ping_interval=30, ping_timeout=10, close_timeout=10
        )

        self.logger.info("WebSocket server started", {"host": self.host, "port": self.port})

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all connections
        if self.connections:
            await asyncio.gather(*[conn.close() for conn in self.connections], return_exceptions=True)
            self.connections.clear()

        if self.logger:
            self.logger.info("WebSocket server stopped")

    def get_connection_count(self) -> int:
        """Get current connection count."""
        return len(self.connections)


class WebSocketWrapper:
    """Wrapper to make websockets.WebSocketServerProtocol compatible with our controller."""

    def __init__(self, websocket: WebSocketServerProtocol):
        self.websocket = websocket

    async def send(self, message: str) -> None:
        """Send message to WebSocket."""
        await self.websocket.send(message)

    async def close(self, code: int = 1000, reason: str = "Normal closure") -> None:
        """Close WebSocket connection."""
        await self.websocket.close(code, reason)

    def __aiter__(self):
        """Make wrapper async iterable."""
        return self

    async def __anext__(self):
        """Get next message from WebSocket."""
        try:
            message = await self.websocket.recv()
            return message
        except websockets.exceptions.ConnectionClosed:
            raise StopAsyncIteration


async def main():
    """Main entry point for standalone WebSocket server."""
    import os

    # Get configuration from environment
    config_dir = os.getenv("CONFIG_DIR", "config")
    host = os.getenv("WS_HOST", "0.0.0.0")
    port = int(os.getenv("WS_PORT", "8081"))

    # Create and start server
    server = StandaloneWebSocketServer(config_dir=config_dir, host=host, port=port)

    try:
        await server.start()

        # Keep server running
        print(f"WebSocket server running on ws://{host}:{port}")
        await asyncio.Future()  # Run forever

    except KeyboardInterrupt:
        print("Shutting down WebSocket server...")
        await server.stop()
    except Exception as e:
        print(f"WebSocket server error: {e}")
        await server.stop()
        raise


if __name__ == "__main__":
    asyncio.run(main())
