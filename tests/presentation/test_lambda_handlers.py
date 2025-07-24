"""Unit tests for Lambda handlers."""

import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.presentation.lambda_handlers.search_handler import lambda_handler as search_handler
from src.presentation.lambda_handlers.connect_handler import lambda_handler as connect_handler
from src.presentation.lambda_handlers.disconnect_handler import lambda_handler as disconnect_handler
from src.presentation.lambda_handlers.authorizer_handler import lambda_handler as authorizer_handler


class TestSearchHandler:
    """Test search Lambda handler."""

    @pytest.fixture
    def search_event(self):
        """Sample search event."""
        return {
            "httpMethod": "POST",
            "path": "/search",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "address": {
                    "street": "Test Street 1",
                    "city": "Berlin",
                    "postal_code": "10115",
                    "country": "Germany"
                }
            }),
            "requestContext": {
                "requestId": "test-request-123"
            }
        }

    @pytest.fixture
    def lambda_context(self):
        """Mock Lambda context."""
        context = Mock()
        context.aws_request_id = "test-request-123"
        context.remaining_time_in_millis = lambda: 30000
        return context

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_search_handler_success(self, mock_get_container, search_event, lambda_context):
        """Test successful search request."""
        # Mock container and use case
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_result = Mock()
        mock_result.to_dict.return_value = {
            "request_id": "test-request-123",
            "offers": [
                {
                    "provider_name": "TestProvider",
                    "speed_mbps": 100,
                    "price_monthly": 29.99
                }
            ]
        }
        
        mock_use_case.execute.return_value = mock_result
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        # Execute handler
        response = search_handler(search_event, lambda_context)
        
        # Assertions
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "offers" in body
        assert len(body["offers"]) == 1

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_search_handler_invalid_body(self, mock_get_container, lambda_context):
        """Test search handler with invalid request body."""
        event = {
            "httpMethod": "POST",
            "path": "/search",
            "headers": {"Content-Type": "application/json"},
            "body": "invalid json",
            "requestContext": {"requestId": "test-request-123"}
        }
        
        response = search_handler(event, lambda_context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_search_handler_missing_address(self, mock_get_container, lambda_context):
        """Test search handler with missing address."""
        event = {
            "httpMethod": "POST",
            "path": "/search",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"invalid": "data"}),
            "requestContext": {"requestId": "test-request-123"}
        }
        
        response = search_handler(event, lambda_context)
        
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_search_handler_use_case_error(self, mock_get_container, search_event, lambda_context):
        """Test search handler with use case error."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.execute.side_effect = Exception("Provider error")
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = search_handler(search_event, lambda_context)
        
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body


class TestConnectHandler:
    """Test WebSocket connect handler."""

    @pytest.fixture
    def connect_event(self):
        """Sample WebSocket connect event."""
        return {
            "requestContext": {
                "connectionId": "test-connection-123",
                "routeKey": "$connect",
                "apiId": "test-api-id",
                "stage": "test"
            },
            "headers": {
                "Host": "test.execute-api.eu-central-1.amazonaws.com"
            }
        }

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_connect_handler_success(self, mock_get_container, connect_event, lambda_context):
        """Test successful WebSocket connection."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_session = Mock()
        mock_session.connection_id = "test-connection-123"
        mock_use_case.create_connection.return_value = mock_session
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = connect_handler(connect_event, lambda_context)
        
        assert response["statusCode"] == 200

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_connect_handler_missing_connection_id(self, mock_get_container, lambda_context):
        """Test connect handler with missing connection ID."""
        event = {
            "requestContext": {
                "routeKey": "$connect",
                "apiId": "test-api-id",
                "stage": "test"
            }
        }
        
        response = connect_handler(event, lambda_context)
        
        assert response["statusCode"] == 400

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_connect_handler_use_case_error(self, mock_get_container, connect_event, lambda_context):
        """Test connect handler with use case error."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.create_connection.side_effect = Exception("Database error")
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = connect_handler(connect_event, lambda_context)
        
        assert response["statusCode"] == 500


class TestDisconnectHandler:
    """Test WebSocket disconnect handler."""

    @pytest.fixture
    def disconnect_event(self):
        """Sample WebSocket disconnect event."""
        return {
            "requestContext": {
                "connectionId": "test-connection-123",
                "routeKey": "$disconnect",
                "apiId": "test-api-id",
                "stage": "test"
            }
        }

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_disconnect_handler_success(self, mock_get_container, disconnect_event, lambda_context):
        """Test successful WebSocket disconnection."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.disconnect_connection.return_value = None
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = disconnect_handler(disconnect_event, lambda_context)
        
        assert response["statusCode"] == 200

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_disconnect_handler_connection_not_found(self, mock_get_container, disconnect_event, lambda_context):
        """Test disconnect handler with connection not found."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.disconnect_connection.side_effect = ValueError("Connection not found")
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = disconnect_handler(disconnect_event, lambda_context)
        
        assert response["statusCode"] == 404


class TestAuthorizerHandler:
    """Test API Gateway authorizer handler."""

    @pytest.fixture
    def authorizer_event(self):
        """Sample authorizer event."""
        return {
            "type": "REQUEST",
            "methodArn": "arn:aws:execute-api:eu-central-1:123456789012:test-api/test/POST/search",
            "resource": "/search",
            "path": "/search",
            "httpMethod": "POST",
            "headers": {
                "Authorization": "Bearer valid-token"
            },
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "test-api-id",
                "stage": "test"
            }
        }

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_authorizer_handler_valid_token(self, mock_get_container, authorizer_event, lambda_context):
        """Test authorizer with valid token."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.authorize.return_value = {
            "user_id": "user-123",
            "permissions": ["search"]
        }
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = authorizer_handler(authorizer_event, lambda_context)
        
        assert "policyDocument" in response
        assert response["policyDocument"]["Statement"][0]["Effect"] == "Allow"
        assert "context" in response
        assert response["context"]["user_id"] == "user-123"

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_authorizer_handler_invalid_token(self, mock_get_container, authorizer_event, lambda_context):
        """Test authorizer with invalid token."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.authorize.side_effect = ValueError("Invalid token")
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        response = authorizer_handler(authorizer_event, lambda_context)
        
        assert "policyDocument" in response
        assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"

    def test_authorizer_handler_missing_token(self, lambda_context):
        """Test authorizer with missing token."""
        event = {
            "type": "REQUEST",
            "methodArn": "arn:aws:execute-api:eu-central-1:123456789012:test-api/test/POST/search",
            "headers": {},
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "test-api-id",
                "stage": "test"
            }
        }
        
        response = authorizer_handler(event, lambda_context)
        
        assert "policyDocument" in response
        assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"

    @patch('src.shared.dependency_injection.bootstrap.get_container')
    def test_authorizer_handler_system_error(self, mock_get_container, authorizer_event, lambda_context):
        """Test authorizer with system error."""
        mock_container = Mock()
        mock_use_case = AsyncMock()
        mock_use_case.authorize.side_effect = Exception("Database connection failed")
        mock_container.get.return_value = mock_use_case
        mock_get_container.return_value = mock_container
        
        # System errors should deny access for security
        response = authorizer_handler(authorizer_event, lambda_context)
        
        assert "policyDocument" in response
        assert response["policyDocument"]["Statement"][0]["Effect"] == "Deny"