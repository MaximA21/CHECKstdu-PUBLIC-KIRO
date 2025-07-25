"""Pytest configuration and shared fixtures."""

import asyncio
import os
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

# Set test environment
os.environ["APP_ENVIRONMENT"] = "testing"

from src.infrastructure.config import (
    AppConfig,
    DatabaseConfig,
    DatabaseProvider,
    Environment,
    LoggingConfig,
    LoggingProvider,
    MessagingConfig,
    MessagingProvider,
)
from src.shared.dependency_injection import DIContainer, get_container


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def di_container():
    """Provide a fresh DI container for each test."""
    container = DIContainer()
    return container


@pytest.fixture
def app_config():
    """Provide test application configuration."""
    return AppConfig(
        environment=Environment.TESTING,
        database=DatabaseConfig(provider=DatabaseProvider.MOCK),
        messaging=MessagingConfig(provider=MessagingProvider.MOCK),
        logging=LoggingConfig(provider=LoggingProvider.CONSOLE, level="DEBUG"),
        debug=True,
    )


@pytest.fixture
def mock_aws_services():
    """Mock AWS services for testing."""
    with patch("boto3.client") as mock_boto3_client, patch("boto3.resource") as mock_boto3_resource:

        # Mock DynamoDB
        mock_dynamodb = Mock()
        mock_dynamodb_resource = Mock()

        # Mock SQS
        mock_sqs = Mock()

        # Mock API Gateway Management API
        mock_apigateway = Mock()

        def client_side_effect(service_name, **kwargs):
            if service_name == "dynamodb":
                return mock_dynamodb
            elif service_name == "sqs":
                return mock_sqs
            elif service_name == "apigatewaymanagementapi":
                return mock_apigateway
            return Mock()

        def resource_side_effect(service_name, **kwargs):
            if service_name == "dynamodb":
                return mock_dynamodb_resource
            return Mock()

        mock_boto3_client.side_effect = client_side_effect
        mock_boto3_resource.side_effect = resource_side_effect

        yield {
            "dynamodb": mock_dynamodb,
            "dynamodb_resource": mock_dynamodb_resource,
            "sqs": mock_sqs,
            "apigateway": mock_apigateway,
        }


@pytest.fixture
def sample_search_request():
    """Provide sample search request data."""
    return {
        "address": {"street": "Musterstraße 1", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
        "connection_id": "test-connection-123",
        "request_id": "req-456",
    }


@pytest.fixture
def sample_provider_offer():
    """Provide sample provider offer data."""
    return {
        "provider_name": "TestProvider",
        "offer_id": "offer-123",
        "speed_mbps": 100,
        "price_monthly": 29.99,
        "technology": "fiber",
        "availability": True,
        "installation_fee": 0.0,
    }


@pytest.fixture
def sample_connection_session():
    """Provide sample connection session data."""
    return {
        "connection_id": "test-connection-123",
        "user_id": "user-456",
        "connected_at": "2024-01-01T12:00:00Z",
        "last_activity": "2024-01-01T12:05:00Z",
        "status": "active",
    }


@pytest.fixture
def lambda_context():
    """Provide mock Lambda context."""
    context = Mock()
    context.function_name = "test-function"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:eu-central-1:123456789012:function:test-function"
    context.memory_limit_in_mb = 128
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/test-function"
    context.log_stream_name = "2024/01/01/[$LATEST]test-stream"
    return context


@pytest.fixture
def websocket_event():
    """Provide sample WebSocket API Gateway event."""
    return {
        "requestContext": {
            "connectionId": "test-connection-123",
            "routeKey": "$connect",
            "apiId": "test-api-id",
            "stage": "test",
            "requestId": "test-request-id",
            "identity": {"sourceIp": "127.0.0.1"},
        },
        "headers": {"Host": "test.execute-api.eu-central-1.amazonaws.com", "User-Agent": "test-client"},
        "body": None,
        "isBase64Encoded": False,
    }


@pytest.fixture
def rest_api_event():
    """Provide sample REST API Gateway event."""
    return {
        "httpMethod": "POST",
        "path": "/search",
        "pathParameters": None,
        "queryStringParameters": None,
        "headers": {"Content-Type": "application/json", "Host": "test.execute-api.eu-central-1.amazonaws.com"},
        "body": '{"address": {"street": "Test St", "house_number": "123", "city": "Berlin", "postal_code": "10115", "country": "DE"}}',
        "isBase64Encoded": False,
        "requestContext": {"requestId": "test-request-id", "stage": "test", "apiId": "test-api-id"},
    }


@pytest.fixture(autouse=True)
def reset_di_container():
    """Reset DI container after each test."""
    yield
    # Clear the global container after each test
    import src.shared.dependency_injection.bootstrap as bootstrap_module

    if hasattr(bootstrap_module, "_container"):
        bootstrap_module._container = None


@pytest.fixture
def mock_logger():
    """Provide mock logger for testing."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger
