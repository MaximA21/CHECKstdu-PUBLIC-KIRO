"""HTTP server entry point for container deployment."""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
from aiohttp import web, WSMsgType
from aiohttp.web_request import Request
from aiohttp.web_ws import WebSocketResponse

from ..shared.dependency_injection.container import DIContainer
from ..shared.dependency_injection.bootstrap import get_container
from ..infrastructure.config.loader import ConfigLoader
from ..application.interfaces.logging import ILogger
from .http_controllers.search_controller import SearchController
from .http_controllers.share_controller import ShareController
from .websocket_handlers.websocket_server import WebSocketServerController


class HTTPServer:
    """HTTP server for container deployment."""

    def __init__(self, config_dir: Optional[str] = None, port: int = 8080):
        """Initialize HTTP server.

        Args:
            config_dir: Configuration directory path
            port: Server port
        """
        self.port = port
        self.config_loader = ConfigLoader(config_dir)
        self.container: Optional[DIContainer] = None
        self.logger: Optional[ILogger] = None
        self.search_controller: Optional[SearchController] = None
        self.share_controller: Optional[ShareController] = None
        self.websocket_controller: Optional[WebSocketServerController] = None
        self.app: Optional[web.Application] = None

    async def initialize(self) -> None:
        """Initialize server dependencies."""
        try:
            # Load configuration
            config = self.config_loader.load_config()

            # Get dependency injection container
            self.container = get_container()

            # Get logger
            self.logger = self.container.get_logger("http_server")

            # Initialize controllers
            self.search_controller = self.container.resolve(SearchController)
            self.share_controller = self.container.resolve(ShareController)
            self.websocket_controller = self.container.resolve(WebSocketServerController)

            # Create web application
            self.app = web.Application()
            self._setup_routes()
            self._setup_middleware()

            self.logger.info("HTTP server initialized", {"port": self.port, "environment": config.environment.value})

        except Exception as e:
            if self.logger:
                self.logger.error("Failed to initialize HTTP server", {"error": str(e)}, exception=e)
            raise

    def _setup_routes(self) -> None:
        """Set up HTTP routes."""
        # Health check
        self.app.router.add_get("/health", self._health_check)

        # Search API
        self.app.router.add_post("/api/search", self._handle_search)
        self.app.router.add_get("/api/search/{request_id}/status", self._handle_search_status)

        # Share API
        self.app.router.add_get("/api/share/{share_token}", self._handle_share)
        self.app.router.add_get("/api/share/{share_token}/stats", self._handle_share_stats)
        self.app.router.add_post("/api/share/{share_token}/extend", self._handle_share_extend)

        # WebSocket endpoint
        self.app.router.add_get("/ws", self._handle_websocket)

        # Static files (if needed)
        self.app.router.add_get("/", self._handle_root)

    def _setup_middleware(self) -> None:
        """Set up middleware."""

        # CORS middleware
        @web.middleware
        async def cors_handler(request: Request, handler):
            response = await handler(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            return response

        # Error handling middleware
        @web.middleware
        async def error_handler(request: Request, handler):
            try:
                return await handler(request)
            except Exception as e:
                self.logger.error(
                    "Request error", {"path": request.path, "method": request.method, "error": str(e)}, exception=e
                )

                return web.json_response(
                    {"error": "Internal server error", "timestamp": datetime.utcnow().isoformat()}, status=500
                )

        # Request logging middleware
        @web.middleware
        async def logging_middleware(request: Request, handler):
            start_time = datetime.utcnow()

            response = await handler(request)

            duration = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(
                "HTTP request",
                {
                    "method": request.method,
                    "path": request.path,
                    "status": response.status,
                    "duration_seconds": duration,
                    "user_agent": request.headers.get("User-Agent", "unknown"),
                },
            )

            return response

        self.app.middlewares.append(cors_handler)
        self.app.middlewares.append(error_handler)
        self.app.middlewares.append(logging_middleware)

    async def _health_check(self, request: Request) -> web.Response:
        """Health check endpoint."""
        import os

        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "environment": os.environ.get("APP_ENVIRONMENT", "unknown"),
        }

        return web.json_response(health_data)

    async def _handle_root(self, request: Request) -> web.Response:
        """Root endpoint."""
        return web.json_response(
            {
                "service": "WebWunder API",
                "version": "1.0.0",
                "endpoints": {
                    "health": "/health",
                    "search": "/api/search",
                    "share": "/api/share/{share_token}",
                    "websocket": "/ws",
                },
            }
        )

    async def _handle_search(self, request: Request) -> web.Response:
        """Handle search requests."""
        try:
            request_data = await self._extract_request_data(request)
            result = await self.search_controller.handle_request(request_data)

            status_code = 200 if result.get("status") == "success" else 400
            return web.json_response(result, status=status_code)

        except Exception as e:
            self.logger.error("Search request error", {"error": str(e)}, exception=e)
            return web.json_response(
                {"error": "Search request failed", "timestamp": datetime.utcnow().isoformat()}, status=500
            )

    async def _handle_search_status(self, request: Request) -> web.Response:
        """Handle search status requests."""
        try:
            request_data = await self._extract_request_data(request)
            result = await self.search_controller.get_search_status(request_data)

            status_code = 200 if result.get("status") == "success" else 400
            return web.json_response(result, status=status_code)

        except Exception as e:
            self.logger.error("Search status request error", {"error": str(e)}, exception=e)
            return web.json_response(
                {"error": "Search status request failed", "timestamp": datetime.utcnow().isoformat()}, status=500
            )

    async def _handle_share(self, request: Request) -> web.Response:
        """Handle share requests."""
        try:
            request_data = await self._extract_request_data(request)
            result = await self.share_controller.handle_request(request_data)

            status_code = 200 if result.get("status") == "success" else 400
            return web.json_response(result, status=status_code)

        except Exception as e:
            self.logger.error("Share request error", {"error": str(e)}, exception=e)
            return web.json_response({"error": "Share request failed", "timestamp": datetime.utcnow().isoformat()}, status=500)

    async def _handle_share_stats(self, request: Request) -> web.Response:
        """Handle share statistics requests."""
        try:
            request_data = await self._extract_request_data(request)
            result = await self.share_controller.get_statistics(request_data)

            status_code = 200 if result.get("status") == "success" else 400
            return web.json_response(result, status=status_code)

        except Exception as e:
            self.logger.error("Share stats request error", {"error": str(e)}, exception=e)
            return web.json_response(
                {"error": "Share stats request failed", "timestamp": datetime.utcnow().isoformat()}, status=500
            )

    async def _handle_share_extend(self, request: Request) -> web.Response:
        """Handle share extension requests."""
        try:
            request_data = await self._extract_request_data(request)
            result = await self.share_controller.extend_expiration(request_data)

            status_code = 200 if result.get("status") == "success" else 400
            return web.json_response(result, status=status_code)

        except Exception as e:
            self.logger.error("Share extend request error", {"error": str(e)}, exception=e)
            return web.json_response(
                {"error": "Share extend request failed", "timestamp": datetime.utcnow().isoformat()}, status=500
            )

    async def _handle_websocket(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connections."""
        ws = WebSocketResponse()
        await ws.prepare(request)

        try:
            # Delegate to WebSocket controller
            await self.websocket_controller.handle_connection(ws, request.path)
        except Exception as e:
            self.logger.error("WebSocket error", {"error": str(e)}, exception=e)

        return ws

    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract request data for controllers."""
        request_data = {
            "method": request.method,
            "path": request.path,
            "headers": dict(request.headers),
            "query_params": dict(request.query),
            "path_params": dict(request.match_info),
        }

        # Add body for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                if request.content_type == "application/json":
                    request_data["body"] = await request.json()
                else:
                    request_data["body"] = await request.text()
            except Exception:
                request_data["body"] = None

        return request_data

    async def start(self) -> None:
        """Start the HTTP server."""
        if not self.app:
            await self.initialize()

        self.logger.info("Starting HTTP server", {"port": self.port})

        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()

        self.logger.info("HTTP server started", {"port": self.port, "host": "0.0.0.0"})

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self.app:
            await self.app.cleanup()

        if self.logger:
            self.logger.info("HTTP server stopped")


async def main():
    """Main entry point for container deployment."""
    import os

    # Get configuration from environment
    config_dir = os.getenv("CONFIG_DIR", "config")
    port = int(os.getenv("PORT", "8080"))

    # Create and start server
    server = HTTPServer(config_dir=config_dir, port=port)

    try:
        await server.start()

        # Keep server running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("Shutting down server...")
        await server.stop()
    except Exception as e:
        print(f"Server error: {e}")
        await server.stop()
        raise


if __name__ == "__main__":
    asyncio.run(main())
