"""Tests for presentation layer controllers."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from src.presentation.controllers.base_controller import HTTPController, WebSocketController, ContainerController
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
from src.presentation.http_controllers.share_controller import ShareController
from src.presentation.websocket_handlers.connection_handler import ConnectHandler
from src.application.interfaces.logging import ILogger
from src.shared.exceptions.domain import ShareTokenNotFoundException


class TestHTTPController:
    """Test HTTP controller base functionality."""
    
    def test_create_success_response(self):
        """Test HTTP success response creation."""
        logger = Mock(spec=ILogger)
        
        class TestController(HTTPController):
            async def handle_request(self, request_data):
                return self._create_success_response({"test": "data"})
        
        controller = TestController(logger)
        response = controller._create_success_response({"test": "data"})
        
        assert response["statusCode"] == 200
        assert "application/json" in response["headers"]["Content-Type"]
        assert "test" in response["body"]
    
    def test_create_error_response(self):
        """Test HTTP error response creation."""
        logger = Mock(spec=ILogger)
        
        class TestController(HTTPController):
            async def handle_request(self, request_data):
                return self._create_error_response(400, "Test error")
        
        controller = TestController(logger)
        response = controller._create_error_response(400, "Test error")
        
        assert response["statusCode"] == 400
        assert "error" in response["body"]
    
    def test_extract_path_parameter(self):
        """Test path parameter extraction."""
        logger = Mock(spec=ILogger)
        
        class TestController(HTTPController):
            async def handle_request(self, request_data):
                return {}
        
        controller = TestController(logger)
        
        # Test with valid path parameters
        event = {"pathParameters": {"share_token": "test123"}}
        result = controller._extract_path_parameter(event, "share_token")
        assert result == "test123"
        
        # Test with missing path parameters
        event = {}
        result = controller._extract_path_parameter(event, "share_token")
        assert result is None


class TestShareApiHandler:
    """Test ShareApiHandler functionality."""
    
    @pytest.mark.asyncio
    async def test_handle_request_success(self):
        """Test successful share API request handling."""
        # Mock dependencies
        share_use_case = AsyncMock()
        logger = Mock(spec=ILogger)
        
        # Mock use case response
        share_use_case.execute.return_value = {
            "share_token": "test123",
            "total_offers": 5,
            "offers": []
        }
        
        # Create handler
        handler = ShareApiHandler(share_use_case, logger)
        
        # Test event
        event = {
            "pathParameters": {"share_token": "test123"}
        }
        
        # Execute
        response = await handler.handle_request(event)
        
        # Verify
        assert response["statusCode"] == 200
        share_use_case.execute.assert_called_once_with("test123")
        logger.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_request_missing_token(self):
        """Test share API request with missing token."""
        # Mock dependencies
        share_use_case = AsyncMock()
        logger = Mock(spec=ILogger)
        
        # Create handler
        handler = ShareApiHandler(share_use_case, logger)
        
        # Test event without path parameters
        event = {}
        
        # Execute
        response = await handler.handle_request(event)
        
        # Verify
        assert response["statusCode"] == 400
        assert "Share token required" in response["body"]
        share_use_case.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_request_not_found(self):
        """Test share API request with non-existent token."""
        # Mock dependencies
        share_use_case = AsyncMock()
        logger = Mock(spec=ILogger)
        
        # Mock use case to raise exception
        share_use_case.execute.side_effect = ShareTokenNotFoundException("Token not found")
        
        # Create handler
        handler = ShareApiHandler(share_use_case, logger)
        
        # Test event
        event = {
            "pathParameters": {"share_token": "nonexistent"}
        }
        
        # Execute
        response = await handler.handle_request(event)
        
        # Verify
        assert response["statusCode"] == 404
        assert "Share link not found" in response["body"]


class TestContainerController:
    """Test container controller functionality."""
    
    def test_create_success_response(self):
        """Test container success response creation."""
        logger = Mock(spec=ILogger)
        
        class TestController(ContainerController):
            async def handle_request(self, request_data):
                return self._create_success_response({"test": "data"})
        
        controller = TestController(logger)
        response = controller._create_success_response({"test": "data"})
        
        assert response["status_code"] == 200
        assert "application/json" in response["headers"]["Content-Type"]
        assert response["data"]["test"] == "data"
    
    def test_extract_path_parameter(self):
        """Test path parameter extraction for container requests."""
        logger = Mock(spec=ILogger)
        
        class TestController(ContainerController):
            async def handle_request(self, request_data):
                return {}
        
        controller = TestController(logger)
        
        # Test with valid path parameters
        request_data = {"path_params": {"share_token": "test123"}}
        result = controller._extract_path_parameter(request_data, "share_token")
        assert result == "test123"
        
        # Test with missing path parameters
        request_data = {}
        result = controller._extract_path_parameter(request_data, "share_token")
        assert result is None


class TestWebSocketController:
    """Test WebSocket controller functionality."""
    
    def test_create_success_response(self):
        """Test WebSocket success response creation."""
        logger = Mock(spec=ILogger)
        
        class TestController(WebSocketController):
            async def handle_request(self, request_data):
                return self._create_success_response({"test": "data"})
        
        controller = TestController(logger)
        response = controller._create_success_response({"test": "data"})
        
        assert response["statusCode"] == 200
        body_data = eval(response["body"])  # Simple eval for test
        assert body_data["action"] == "response"
        assert body_data["data"]["test"] == "data"
    
    def test_extract_connection_id(self):
        """Test connection ID extraction."""
        logger = Mock(spec=ILogger)
        
        class TestController(WebSocketController):
            async def handle_request(self, request_data):
                return {}
        
        controller = TestController(logger)
        
        # Test with valid connection ID
        event = {"requestContext": {"connectionId": "conn123"}}
        result = controller._extract_connection_id(event)
        assert result == "conn123"
        
        # Test with missing connection ID
        event = {}
        result = controller._extract_connection_id(event)
        assert result is None


if __name__ == "__main__":
    # Run basic tests
    print("Running controller tests...")
    
    # Test HTTP controller
    test_http = TestHTTPController()
    test_http.test_create_success_response()
    test_http.test_create_error_response()
    test_http.test_extract_path_parameter()
    print("✓ HTTP controller tests passed")
    
    # Test container controller
    test_container = TestContainerController()
    test_container.test_create_success_response()
    test_container.test_extract_path_parameter()
    print("✓ Container controller tests passed")
    
    # Test WebSocket controller
    test_ws = TestWebSocketController()
    test_ws.test_create_success_response()
    test_ws.test_extract_connection_id()
    print("✓ WebSocket controller tests passed")
    
    print("All controller tests passed!")