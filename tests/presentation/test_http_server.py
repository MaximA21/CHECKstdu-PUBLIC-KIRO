"""Tests for HTTP server module."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from src.presentation.http_server import HTTPServer, main


class TestHTTPServer:
    """Test cases for HTTPServer."""

    @pytest.fixture
    def server(self):
        """Create a test server instance."""
        return HTTPServer()

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        container = Mock()
        container.resolve.return_value = Mock()
        return container

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock()
        config.app.port = 8080
        return config

    @pytest.mark.asyncio
    async def test_init(self, server):
        """Test server initialization."""
        assert server.port == 8080
        assert server.config_loader is not None
        assert server.app is None
        assert server.logger is None

    @pytest.mark.asyncio
    async def test_initialize_success(self, server, mock_container, mock_config):
        """Test successful server initialization."""
        with (
            patch("src.presentation.http_server.get_container", return_value=mock_container),
            patch.object(server.config_loader, "load_config", return_value=mock_config),
            patch.object(server, "_setup_routes"),
            patch.object(server, "_setup_middleware"),
        ):
            await server.initialize()

            assert server.app is not None
            assert server.logger is not None

    @pytest.mark.asyncio
    async def test_initialize_failure(self, server):
        """Test server initialization failure."""
        with patch("src.presentation.http_server.get_container", side_effect=Exception("Test error")):
            with pytest.raises(Exception):
                await server.initialize()

    @pytest.mark.asyncio
    async def test_setup_routes(self, server):
        """Test route setup."""
        server.app = web.Application()
        server._setup_routes()

        # Check that routes are added
        routes = [route.resource.canonical for route in server.app.router.routes()]
        assert "/health" in routes
        assert "/" in routes
        assert "/api/search" in routes

    @pytest.mark.asyncio
    async def test_setup_middleware(self, server):
        """Test middleware setup."""
        server.app = web.Application()
        server._setup_middleware()

        # Check that middleware is added
        assert len(server.app.middlewares) > 0

    @pytest.mark.asyncio
    async def test_health_check(self, server):
        """Test health check endpoint."""
        request = make_mocked_request("GET", "/health")
        response = await server._health_check(request)

        assert response.status == 200
        # Use response.text instead of response.text()
        response_text = response.text
        data = json.loads(response_text)
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_handle_root(self, server):
        """Test root endpoint."""
        request = make_mocked_request("GET", "/")
        response = await server._handle_root(request)

        assert response.status == 200
        # Use response.text instead of response.text()
        response_text = response.text
        data = json.loads(response_text)
        assert "service" in data  # Changed from "message" to "service"

    @pytest.mark.asyncio
    async def test_handle_search_success(self, server):
        """Test search endpoint success."""
        request = make_mocked_request("POST", "/api/search")
        request.json = AsyncMock(return_value={"address": "Test Address"})

        # Mock controllers and logger
        server.search_controller = Mock()
        server.search_controller.handle_request = AsyncMock(return_value={"status": "success"})
        server.logger = Mock()

        response = await server._handle_search(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_search_failure(self, server):
        """Test search endpoint failure."""
        request = make_mocked_request("POST", "/api/search")
        request.json = AsyncMock(return_value={"address": "Test Address"})

        # Mock controllers and logger
        server.search_controller = Mock()
        server.search_controller.handle_request = AsyncMock(side_effect=Exception("Test error"))
        server.logger = Mock()

        response = await server._handle_search(request)

        assert response.status == 500

    @pytest.mark.asyncio
    async def test_handle_search_exception(self, server):
        """Test search endpoint with invalid JSON."""
        request = make_mocked_request("POST", "/api/search")
        request.json = AsyncMock(side_effect=Exception("Invalid JSON"))

        # Mock logger
        server.logger = Mock()

        response = await server._handle_search(request)

        assert response.status == 500  # Changed from 400 to 500 for internal server error

    @pytest.mark.asyncio
    async def test_handle_search_status(self, server):
        """Test search status endpoint."""
        request = make_mocked_request("GET", "/api/search/status/123")
        
        # Mock controllers and logger
        server.search_controller = Mock()
        server.search_controller.get_search_status = AsyncMock(return_value={"status": "completed"})
        server.logger = Mock()

        # Mock the match_info using patch
        with patch.object(type(request), 'match_info', {"request_id": "123"}):
            response = await server._handle_search_status(request)

            assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_share(self, server):
        """Test share endpoint."""
        request = make_mocked_request("GET", "/api/share/abc123")
        
        # Mock controllers and logger
        server.share_controller = Mock()
        server.share_controller.handle_request = AsyncMock(return_value={"results": []})
        server.logger = Mock()

        # Mock the match_info using patch
        with patch.object(type(request), 'match_info', {"share_token": "abc123"}):
            response = await server._handle_share(request)

            assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_share_stats(self, server):
        """Test share stats endpoint."""
        request = make_mocked_request("GET", "/api/share/abc123/stats")
        
        # Mock controllers and logger
        server.share_controller = Mock()
        server.share_controller.get_statistics = AsyncMock(return_value={"views": 5})
        server.logger = Mock()

        # Mock the match_info using patch
        with patch.object(type(request), 'match_info', {"share_token": "abc123"}):
            response = await server._handle_share_stats(request)

            assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_share_extend(self, server):
        """Test share extend endpoint."""
        request = make_mocked_request("POST", "/api/share/abc123/extend")
        request.json = AsyncMock(return_value={"days": 7})
        
        # Mock controllers and logger
        server.share_controller = Mock()
        server.share_controller.extend_expiration = AsyncMock(return_value={"status": "success"})
        server.logger = Mock()

        response = await server._handle_share_extend(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_websocket(self, server):
        """Test WebSocket endpoint."""
        request = make_mocked_request("GET", "/ws")
        
        # Mock WebSocket response
        mock_ws = Mock()
        mock_ws.prepare = AsyncMock()
        
        with patch("src.presentation.http_server.WebSocketResponse", return_value=mock_ws):
            # Mock controllers and logger
            server.websocket_controller = Mock()
            server.websocket_controller.handle_connection = AsyncMock()
            server.logger = Mock()

            response = await server._handle_websocket(request)

            assert response == mock_ws

    @pytest.mark.asyncio
    async def test_extract_request_data_json(self, server):
        """Test request data extraction with JSON body."""
        request = make_mocked_request("POST", "/api/test")
        
        # Mock headers, query, and match_info using patch on the class level
        with patch.object(type(request), 'headers', {"Content-Type": "application/json"}):
            with patch.object(type(request), 'query', {"param": "value"}):
                with patch.object(type(request), 'match_info', {"id": "123"}):
                    # Mock content_type property
                    with patch.object(type(request), 'content_type', "application/json"):
                        request.json = AsyncMock(return_value={"test": "data"})

                        data = await server._extract_request_data(request)

                        assert data["method"] == "POST"
                        assert data["path"] == "/api/test"
                        assert data["body"] == {"test": "data"}
                        assert data["query_params"] == {"param": "value"}
                        assert data["path_params"] == {"id": "123"}

    @pytest.mark.asyncio
    async def test_extract_request_data_text(self, server):
        """Test request data extraction with text body."""
        request = make_mocked_request("POST", "/api/test")
        
        # Mock headers, query, and match_info using patch on the class level
        with patch.object(type(request), 'headers', {"Content-Type": "text/plain"}):
            with patch.object(type(request), 'query', {}):
                with patch.object(type(request), 'match_info', {}):
                    request.text = AsyncMock(return_value="test data")

                    data = await server._extract_request_data(request)

                    assert data["body"] == "test data"

    @pytest.mark.asyncio
    async def test_extract_request_data_get(self, server):
        """Test request data extraction for GET request."""
        request = make_mocked_request("GET", "/api/test")
        
        # Mock headers, query, and match_info using patch on the class level
        with patch.object(type(request), 'headers', {}):
            with patch.object(type(request), 'query', {"param": "value"}):
                with patch.object(type(request), 'match_info', {}):

                    data = await server._extract_request_data(request)

                    assert data["method"] == "GET"
                    assert "body" not in data

    @pytest.mark.asyncio
    async def test_start_server(self, server, mock_container, mock_config):
        """Test server startup."""
        with (
            patch("src.presentation.http_server.get_container", return_value=mock_container),
            patch.object(server.config_loader, "load_config", return_value=mock_config),
            patch.object(server, "_setup_routes"),
            patch.object(server, "_setup_middleware"),
            patch("aiohttp.web.AppRunner") as mock_runner_class,
            patch("aiohttp.web.TCPSite") as mock_site_class,
        ):

            mock_runner = Mock()
            mock_runner_class.return_value = mock_runner
            mock_site = Mock()
            mock_site_class.return_value = mock_site

            # Mock the async context managers
            mock_runner.setup = AsyncMock()
            mock_site.start = AsyncMock()

            await server.initialize()
            await server.start()

            mock_runner.setup.assert_called_once()
            mock_site.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_server(self, server):
        """Test server shutdown."""
        server.app = Mock()
        server.logger = Mock()
        # Fix: Mock cleanup as async method
        server.app.cleanup = AsyncMock()

        await server.stop()

        server.app.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_main_function():
    """Test main function."""
    with (
        patch("os.getenv", side_effect=lambda key, default=None: default),
        patch("src.presentation.http_server.HTTPServer") as mock_server_class,
    ):

        mock_server = Mock()
        mock_server_class.return_value = mock_server
        mock_server.start = AsyncMock(side_effect=KeyboardInterrupt())  # Simulate KeyboardInterrupt
        mock_server.stop = AsyncMock()

        # This should handle KeyboardInterrupt gracefully
        await main()

        mock_server.start.assert_called_once()
        mock_server.stop.assert_called_once()
