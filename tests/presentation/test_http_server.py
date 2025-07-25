"""Tests for HTTP server module."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from src.presentation.http_server import HTTPServer


class TestHTTPServer:
    """Test cases for HTTPServer."""

    @pytest.fixture
    def server(self):
        """Create a test server instance."""
        return HTTPServer(port=8080)

    @pytest.fixture
    def mock_container(self):
        """Create a mock DI container."""
        container = Mock()
        container.get_logger.return_value = Mock()
        container.resolve.side_effect = lambda cls: Mock()
        return container

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock()
        config.environment.value = "testing"
        return config

    @pytest.mark.asyncio
    async def test_init(self, server):
        """Test server initialization."""
        assert server.port == 8080
        assert server.container is None
        assert server.logger is None
        assert server.app is None

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

            assert server.container is not None
            assert server.logger is not None
            assert server.app is not None
            assert server.search_controller is not None
            assert server.share_controller is not None
            assert server.websocket_controller is not None

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
        routes = list(server.app.router.routes())
        assert len(routes) > 0

    @pytest.mark.asyncio
    async def test_setup_middleware(self, server):
        """Test middleware setup."""
        server.app = web.Application()
        server.logger = Mock()
        server._setup_middleware()

        # Check that middlewares are added
        assert len(server.app.middlewares) > 0

    @pytest.mark.asyncio
    async def test_health_check(self, server):
        """Test health check endpoint."""
        request = make_mocked_request("GET", "/health")

        response = await server._health_check(request)

        assert response.status == 200
        # Fix: response.text is a property, not a method in aiohttp
        response_text = response.text if isinstance(response.text, str) else await response.text()
        data = json.loads(response_text)
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_handle_root(self, server):
        """Test root endpoint."""
        request = make_mocked_request("GET", "/")

        response = await server._handle_root(request)

        assert response.status == 200
        # Fix: response.text is a property, not a method in aiohttp
        response_text = response.text if isinstance(response.text, str) else await response.text()
        data = json.loads(response_text)
        assert data["service"] == "WebWunder API"
        assert "endpoints" in data

    @pytest.mark.asyncio
    async def test_handle_search_success(self, server):
        """Test successful search request."""
        server.search_controller = Mock()
        server.search_controller.handle_request = AsyncMock(return_value={"status": "success", "data": "test"})
        server.logger = Mock()

        request = make_mocked_request("POST", "/api/search")
        request.json = AsyncMock(return_value={"address": "test"})

        response = await server._handle_search(request)

        assert response.status == 200
        # Fix: response.text is a property, not a method in aiohttp
        response_text = response.text if isinstance(response.text, str) else await response.text()
        data = json.loads(response_text)
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_search_failure(self, server):
        """Test failed search request."""
        server.search_controller = Mock()
        server.search_controller.handle_request = AsyncMock(return_value={"status": "error", "message": "test error"})
        server.logger = Mock()

        request = make_mocked_request("POST", "/api/search")
        request.json = AsyncMock(return_value={"address": "test"})

        response = await server._handle_search(request)

        assert response.status == 400

    @pytest.mark.asyncio
    async def test_handle_search_exception(self, server):
        """Test search request with exception."""
        server.search_controller = Mock()
        server.search_controller.handle_request = AsyncMock(side_effect=Exception("Test error"))
        server.logger = Mock()

        request = make_mocked_request("POST", "/api/search")
        request.json = AsyncMock(return_value={"address": "test"})

        response = await server._handle_search(request)

        assert response.status == 500

    @pytest.mark.asyncio
    async def test_handle_search_status(self, server):
        """Test search status endpoint."""
        server.search_controller = Mock()
        server.search_controller.get_status = AsyncMock(return_value={"status": "completed"})
        server.logger = Mock()

        # Fix: Use proper aiohttp request mocking for path parameters
        request = make_mocked_request("GET", "/api/search/123/status")
        # Mock the match_info property properly
        type(request).match_info = Mock(return_value={"request_id": "123"})

        response = await server._handle_search_status(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_share(self, server):
        """Test share endpoint."""
        server.share_controller = Mock()
        server.share_controller.get_shared_data = AsyncMock(return_value={"status": "success", "data": "test"})
        server.logger = Mock()

        request = make_mocked_request("GET", "/api/share/test-token")
        # Fix: Mock the match_info property properly
        type(request).match_info = Mock(return_value={"share_token": "test-token"})

        response = await server._handle_share(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_share_stats(self, server):
        """Test share stats endpoint."""
        server.share_controller = Mock()
        server.share_controller.get_statistics = AsyncMock(return_value={"status": "success", "stats": {}})
        server.logger = Mock()

        request = make_mocked_request("GET", "/api/share/test-token/stats")
        # Fix: Mock the match_info property properly
        type(request).match_info = Mock(return_value={"share_token": "test-token"})

        response = await server._handle_share_stats(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_share_extend(self, server):
        """Test share extend endpoint."""
        server.share_controller = Mock()
        server.share_controller.extend_expiration = AsyncMock(return_value={"status": "success"})
        server.logger = Mock()

        request = make_mocked_request("POST", "/api/share/test-token/extend")
        # Fix: Mock the match_info property properly
        type(request).match_info = Mock(return_value={"share_token": "test-token"})
        request.json = AsyncMock(return_value={"days": 7})

        response = await server._handle_share_extend(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_handle_websocket(self, server):
        """Test WebSocket endpoint."""
        server.websocket_controller = Mock()
        server.websocket_controller.handle_connection = AsyncMock()
        server.logger = Mock()

        request = make_mocked_request("GET", "/ws")

        response = await server._handle_websocket(request)

        assert response is not None

    @pytest.mark.asyncio
    async def test_extract_request_data_json(self, server):
        """Test request data extraction with JSON body."""
        request = make_mocked_request("POST", "/api/test")
        # Fix: Mock cached properties properly
        type(request).headers = Mock(return_value={"Content-Type": "application/json"})
        request.json = AsyncMock(return_value={"test": "data"})
        type(request).query = Mock(return_value={"param": "value"})
        type(request).match_info = Mock(return_value={"id": "123"})

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
        # Fix: Mock cached properties properly
        type(request).headers = Mock(return_value={"Content-Type": "text/plain"})
        request.text = AsyncMock(return_value="test data")
        type(request).query = Mock(return_value={})
        type(request).match_info = Mock(return_value={})

        data = await server._extract_request_data(request)

        assert data["body"] == "test data"

    @pytest.mark.asyncio
    async def test_extract_request_data_get(self, server):
        """Test request data extraction for GET request."""
        request = make_mocked_request("GET", "/api/test")
        # Fix: Mock cached properties properly
        type(request).query = Mock(return_value={"param": "value"})
        type(request).match_info = Mock(return_value={})

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
        mock_server.start = AsyncMock()
        mock_server.stop = AsyncMock()

        # Mock asyncio.sleep to avoid infinite loop
        with patch("asyncio.sleep", side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                from src.presentation.http_server import main

                await main()

        mock_server.start.assert_called_once()
        mock_server.stop.assert_called_once()
