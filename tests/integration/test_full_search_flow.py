"""Integration tests for full search flow using mock implementations."""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.entities.search_result import SearchResult
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType
from src.domain.value_objects.address import Address

from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.application.use_cases.share_results_use_case import ShareResultsUseCase

from src.infrastructure.persistence.mock_repositories import (
    MockSearchResultRepository,
    MockConnectionRepository
)
from src.infrastructure.messaging.mock_messaging import (
    MockMessageQueue,
    MockWorkflowOrchestrator
)
from src.infrastructure.messaging.mock_connection_manager import MockConnectionManager
from src.infrastructure.external_services.mock_providers import (
    MockProviderService,
    MockProviderRegistry,
    MockProviderAggregator
)
from src.infrastructure.logging.console_logger import ConsoleLogger


class TestFullSearchFlow:
    """Integration tests for complete search flow."""
    
    @pytest_asyncio.fixture
    async def setup_infrastructure(self):
        """Set up mock infrastructure for integration tests."""
        # Repositories
        search_result_repo = MockSearchResultRepository()
        connection_repo = MockConnectionRepository()
        
        # Messaging
        message_queue = MockMessageQueue()
        workflow_orchestrator = MockWorkflowOrchestrator()
        connection_manager = MockConnectionManager()
        
        # Providers
        provider_registry = MockProviderRegistry()
        provider1 = MockProviderService("TestProvider1")
        provider2 = MockProviderService("TestProvider2")
        
        await provider_registry.register_provider(provider1)
        await provider_registry.register_provider(provider2)
        
        provider_aggregator = MockProviderAggregator(provider_registry)
        
        # Logger
        logger = ConsoleLogger("integration_test")
        
        # Use cases
        search_use_case = SearchOffersUseCase(
            search_result_repository=search_result_repo,
            connection_repository=connection_repo,
            message_queue=message_queue,
            logger=logger
        )
        
        process_results_use_case = ProcessResultsUseCase(
            search_result_repository=search_result_repo,
            connection_manager=connection_manager,
            provider_registry=provider_registry,
            logger=logger
        )
        
        connection_use_case = ConnectionManagementUseCase(
            connection_repository=connection_repo,
            connection_manager=connection_manager,
            logger=logger
        )
        
        share_results_use_case = ShareResultsUseCase(
            search_result_repository=search_result_repo,
            logger=logger
        )
        
        return {
            'repositories': {
                'search_result': search_result_repo,
                'connection': connection_repo
            },
            'messaging': {
                'queue': message_queue,
                'orchestrator': workflow_orchestrator,
                'connection_manager': connection_manager
            },
            'providers': {
                'registry': provider_registry,
                'aggregator': provider_aggregator
            },
            'use_cases': {
                'search': search_use_case,
                'process_results': process_results_use_case,
                'connection': connection_use_case,
                'share_results': share_results_use_case
            }
        }
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="Teststraße",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
    
    @pytest.mark.asyncio
    async def test_complete_search_flow(self, setup_infrastructure, sample_address):
        """Test complete search flow from connection to results sharing."""
        infra = setup_infrastructure
        
        # Step 1: Establish connection
        connection_id = "test-conn-123"
        infra['messaging']['connection_manager'].add_mock_connection(connection_id, "websocket")
        
        connect_result = await infra['use_cases']['connection'].handle_connect(connection_id)
        assert connect_result['status'] == 'connected'
        assert connect_result['connection_id'] == connection_id
        
        # Step 2: Initiate search
        search_result = await infra['use_cases']['search'].execute(sample_address, connection_id)
        assert search_result['status'] == 'initiated'
        assert 'request_id' in search_result
        assert 'share_token' in search_result
        
        request_id = search_result['request_id']
        share_token = search_result['share_token']
        
        # Step 3: Process results (simulate provider responses)
        process_result = await infra['use_cases']['process_results'].execute(
            request_id=request_id,
            connection_id=connection_id,
            provider_name="TestProvider1",
            status="success",
            raw_response={"offers": [{"product_id": "TEST-001", "speed": 100}]},
            share_token=share_token,
            address_data=sample_address.__dict__
        )
        assert process_result['status'] == 'processed'
        assert process_result['offers_count'] >= 0
        
        # Step 4: Share results
        shared_result = await infra['use_cases']['share_results'].execute(share_token)
        assert shared_result['share_token'] == share_token
        assert 'offers' in shared_result
        assert len(shared_result['offers']) > 0
        assert shared_result['total_offers'] > 0
        
        # Step 5: Disconnect
        disconnect_result = await infra['use_cases']['connection'].handle_disconnect(
            connection_id, "Test completed"
        )
        assert disconnect_result['status'] == 'disconnected'
        assert disconnect_result['reason'] == "Test completed"
    
    @pytest.mark.asyncio
    async def test_search_flow_with_multiple_providers(self, setup_infrastructure, sample_address):
        """Test search flow with multiple providers returning different offers."""
        infra = setup_infrastructure
        
        # Add more providers
        provider3 = MockProviderService("TestProvider3")
        provider4 = MockProviderService("TestProvider4")
        
        await infra['providers']['registry'].register_provider(provider3)
        await infra['providers']['registry'].register_provider(provider4)
        
        connection_id = "test-conn-multi"
        infra['messaging']['connection_manager'].add_mock_connection(connection_id, "websocket")
        
        # Connect and search
        await infra['use_cases']['connection'].handle_connect(connection_id)
        search_result = await infra['use_cases']['search'].execute(sample_address, connection_id)
        
        # Process results
        process_result = await infra['use_cases']['process_results'].execute(
            request_id=search_result['request_id'],
            connection_id=connection_id,
            provider_name="TestProvider1",
            status="success",
            raw_response={"offers": [{"product_id": "TEST-001", "speed": 100}]},
            share_token=search_result['share_token'],
            address_data=sample_address.__dict__
        )
        
        # Verify provider contributed
        assert process_result['offers_count'] >= 0
        
        # Share and verify results
        shared_result = await infra['use_cases']['share_results'].execute(search_result['share_token'])
        
        # Check that we have offers from multiple providers
        provider_names = set()
        for offer in shared_result['offers']:
            provider_names.add(offer['provider_name'])
        
        assert len(provider_names) >= 4  # All 4 providers should have contributed
    
    @pytest.mark.asyncio
    async def test_search_flow_error_handling(self, setup_infrastructure, sample_address):
        """Test search flow error handling scenarios."""
        infra = setup_infrastructure
        
        # Test with invalid connection ID
        with pytest.raises(Exception):
            await infra['use_cases']['search'].execute(sample_address, "invalid-connection")
        
        # Test sharing with invalid token
        shared_result = await infra['use_cases']['share_results'].execute("invalid-token")
        assert shared_result['error'] == 'not_found'
        
        # Test processing with invalid request ID
        process_result = await infra['use_cases']['process_results'].execute(
            request_id="invalid-request",
            connection_id="test-conn",
            provider_name="TestProvider1",
            status="success",
            raw_response={"offers": []},
            share_token="invalid-token",
            address_data=sample_address.__dict__
        )
        assert process_result['status'] == 'failed'
    
    @pytest.mark.asyncio
    async def test_concurrent_searches(self, setup_infrastructure, sample_address):
        """Test handling multiple concurrent searches."""
        infra = setup_infrastructure
        
        # Set up multiple connections
        connection_ids = [f"conn-{i}" for i in range(5)]
        for conn_id in connection_ids:
            infra['messaging']['connection_manager'].add_mock_connection(conn_id, "websocket")
            await infra['use_cases']['connection'].handle_connect(conn_id)
        
        # Start concurrent searches
        search_tasks = []
        for conn_id in connection_ids:
            task = infra['use_cases']['search'].execute(sample_address, conn_id)
            search_tasks.append(task)
        
        # Wait for all searches to complete
        search_results = await asyncio.gather(*search_tasks)
        
        # Verify all searches succeeded
        assert len(search_results) == 5
        for result in search_results:
            assert result['status'] == 'initiated'
            assert 'request_id' in result
            assert 'share_token' in result
        
        # Verify all request IDs are unique
        request_ids = [result['request_id'] for result in search_results]
        assert len(set(request_ids)) == 5
        
        # Process all results concurrently
        process_tasks = []
        for i, result in enumerate(search_results):
            task = infra['use_cases']['process_results'].execute(
                request_id=result['request_id'],
                connection_id=connection_ids[i],
                provider_name="TestProvider1",
                status="success",
                raw_response={"offers": [{"product_id": f"TEST-{i}", "speed": 100}]},
                share_token=result['share_token'],
                address_data=sample_address.__dict__
            )
            process_tasks.append(task)
        
        process_results = await asyncio.gather(*process_tasks)
        
        # Verify all processing succeeded
        for result in process_results:
            assert result['status'] == 'processed'
            assert result['offers_count'] >= 0
    
    @pytest.mark.asyncio
    async def test_search_result_persistence(self, setup_infrastructure, sample_address):
        """Test that search results are properly persisted and retrievable."""
        infra = setup_infrastructure
        
        connection_id = "test-conn-persist"
        infra['messaging']['connection_manager'].add_mock_connection(connection_id, "websocket")
        
        # Connect and search
        await infra['use_cases']['connection'].handle_connect(connection_id)
        search_result = await infra['use_cases']['search'].execute(sample_address, connection_id)
        
        # Process results
        await infra['use_cases']['process_results'].execute(
            request_id=search_result['request_id'],
            connection_id=connection_id,
            provider_name="TestProvider1",
            status="success",
            raw_response={"offers": [{"product_id": "TEST-001", "speed": 100}]},
            share_token=search_result['share_token'],
            address_data=sample_address.__dict__
        )
        
        # Verify result can be retrieved by share token
        shared_result = await infra['use_cases']['share_results'].execute(search_result['share_token'])
        assert shared_result['share_token'] == search_result['share_token']
        
        # Verify result can be retrieved by request ID
        stored_result = await infra['repositories']['search_result'].get_result_by_request_id(
            search_result['request_id']
        )
        assert stored_result is not None
        assert stored_result.request_id == search_result['request_id']
        assert stored_result.share_token == search_result['share_token']
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, setup_infrastructure):
        """Test complete connection lifecycle management."""
        infra = setup_infrastructure
        
        connection_id = "test-conn-lifecycle"
        infra['messaging']['connection_manager'].add_mock_connection(connection_id, "websocket")
        
        # Test connection establishment
        connect_result = await infra['use_cases']['connection'].handle_connect(connection_id)
        assert connect_result['status'] == 'connected'
        
        # Verify connection is stored
        stored_connection = await infra['repositories']['connection'].get_connection(connection_id)
        assert stored_connection is not None
        assert stored_connection.is_connected
        
        # Test connection activity update
        stored_connection.update_activity()
        await infra['repositories']['connection'].update_connection(stored_connection)
        
        # Test disconnection
        disconnect_result = await infra['use_cases']['connection'].handle_disconnect(
            connection_id, "Normal closure"
        )
        assert disconnect_result['status'] == 'disconnected'
        
        # Verify connection state is updated
        updated_connection = await infra['repositories']['connection'].get_connection(connection_id)
        assert updated_connection is not None
        assert not updated_connection.is_connected
        assert updated_connection.disconnect_reason == "Normal closure"


if __name__ == "__main__":
    pytest.main([__file__])