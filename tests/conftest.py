"""Pytest configuration and shared fixtures."""

import pytest
import pytest_asyncio
import asyncio
import os
from unittest.mock import patch
from datetime import datetime

from src.domain.value_objects.address import Address
from src.domain.entities.search_result import SearchResult
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType
from decimal import Decimal


@pytest.fixture
def test_environment():
    """Set up test environment variables."""
    test_env = {
        'ENVIRONMENT': 'test',
        'LOG_LEVEL': 'DEBUG',
        'USE_MOCK_SERVICES': 'true',
        'AWS_REGION': 'us-east-1',
        'PYTHONPATH': os.getcwd()
    }
    
    with patch.dict(os.environ, test_env):
        yield test_env


@pytest.fixture
def sample_address():
    """Create a sample address for testing."""
    return Address(
        street="Teststraße",
        house_number="123",
        city="Berlin",
        postal_code="10115",
        country="DE"
    )


@pytest.fixture
def sample_address_munich():
    """Create a sample Munich address for testing."""
    return Address(
        street="Musterstraße",
        house_number="456",
        city="München",
        postal_code="80331",
        country="DE"
    )


@pytest.fixture
def sample_search_result(sample_address):
    """Create a sample search result for testing."""
    return SearchResult.create_new(sample_address, "test-request-123")


@pytest.fixture
def sample_connection_session():
    """Create a sample connection session for testing."""
    return ConnectionSession.create_new("test-connection-123", SessionConnectionType.WEBSOCKET)


@pytest.fixture
def sample_provider_offers():
    """Create sample provider offers for testing."""
    return [
        ProviderOffer(
            provider_name="TestProvider1",
            product_id="TEST-001",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        ),
        ProviderOffer(
            provider_name="TestProvider2",
            product_id="TEST-002",
            speed_download_mbps=50,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=12
        ),
        ProviderOffer(
            provider_name="TestProvider3",
            product_id="TEST-003",
            speed_download_mbps=200,
            speed_upload_mbps=100,
            monthly_cost_euros=Decimal("59.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
    ]


@pytest.fixture
def mock_lambda_context():
    """Create a mock AWS Lambda context."""
    from unittest.mock import MagicMock
    
    context = MagicMock()
    context.function_name = "test-function"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.memory_limit_in_mb = "512"
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = f"test-request-{datetime.now().timestamp()}"
    context.log_group_name = "/aws/lambda/test-function"
    context.log_stream_name = f"2023/01/01/[$LATEST]test-stream-{datetime.now().timestamp()}"
    return context


@pytest.fixture
def performance_test_config():
    """Configuration for performance tests."""
    return {
        'max_init_time_ms': 500,
        'max_request_time_ms': 100,
        'max_error_handling_time_ms': 50,
        'min_throughput_rps': 50,
        'max_memory_overhead_mb': 50,
        'max_service_resolution_time_us': 100
    }


# Pytest markers for test categorization
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test collection hooks
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath) or "/domain/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)
        
        # Add slow marker for tests that take longer
        if "concurrent" in item.name or "scalability" in item.name or "memory" in item.name:
            item.add_marker(pytest.mark.slow)


# Async test utilities
@pytest_asyncio.fixture
async def async_test_timeout():
    """Provide a reasonable timeout for async tests."""
    return 30.0  # 30 seconds


# Test data cleanup
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Automatically cleanup test data after each test."""
    yield
    # Cleanup logic here if needed
    pass


# Mock service factories
@pytest.fixture
def mock_repository_factory():
    """Factory for creating mock repositories."""
    from src.infrastructure.persistence.mock_repositories import (
        MockSearchResultRepository,
        MockConnectionRepository
    )
    
    def create_repositories():
        return {
            'search_result': MockSearchResultRepository(),
            'connection': MockConnectionRepository()
        }
    
    return create_repositories


@pytest.fixture
def mock_messaging_factory():
    """Factory for creating mock messaging services."""
    from src.infrastructure.messaging.mock_messaging import (
        MockMessageQueue,
        MockWorkflowOrchestrator
    )
    from src.infrastructure.messaging.mock_connection_manager import MockConnectionManager
    
    def create_messaging():
        return {
            'queue': MockMessageQueue(),
            'orchestrator': MockWorkflowOrchestrator(),
            'connection_manager': MockConnectionManager()
        }
    
    return create_messaging


@pytest_asyncio.fixture
async def mock_provider_factory():
    """Factory for creating mock provider services."""
    from src.infrastructure.external_services.mock_providers import (
        MockProviderService,
        MockProviderRegistry,
        MockProviderAggregator
    )
    
    registry = MockProviderRegistry()
    
    # Register some default providers
    providers = [
        MockProviderService("TestProvider1"),
        MockProviderService("TestProvider2"),
        MockProviderService("TestProvider3")
    ]
    
    for provider in providers:
        await registry.register_provider(provider)
    
    aggregator = MockProviderAggregator(registry)
    
    return {
        'registry': registry,
        'aggregator': aggregator,
        'providers': providers
    }


# Test reporting utilities
@pytest.fixture
def test_metrics():
    """Collect test metrics during execution."""
    metrics = {
        'start_time': datetime.now(),
        'execution_times': [],
        'memory_usage': [],
        'errors': []
    }
    
    yield metrics
    
    metrics['end_time'] = datetime.now()
    metrics['total_duration'] = (metrics['end_time'] - metrics['start_time']).total_seconds()


# Logging configuration for tests
@pytest.fixture(autouse=True)
def configure_test_logging():
    """Configure logging for tests."""
    import logging
    
    # Set up test logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Suppress noisy loggers during tests
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    yield
    
    # Cleanup logging configuration
    logging.getLogger().handlers.clear()