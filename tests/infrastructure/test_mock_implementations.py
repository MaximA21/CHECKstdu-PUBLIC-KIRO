"""Tests for mock infrastructure implementations."""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from src.domain.entities.search_result import SearchResult
from src.domain.entities.connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from src.domain.value_objects.address import Address

from src.infrastructure.persistence.mock_repositories import (
    MockSearchResultRepository,
    MockConnectionRepository,
    MockProviderOfferRepository
)
from src.infrastructure.messaging.mock_messaging import (
    MockMessageQueue,
    MockWorkflowOrchestrator,
    MockEventBus
)
from src.infrastructure.messaging.mock_connection_manager import (
    MockConnectionManager,
    MockTopicManager,
    MockConnectionNotifier
)
from src.infrastructure.external_services.mock_providers import (
    MockProviderService,
    MockByteMe,
    MockVerbynDich,
    MockWebWunder,
    MockPingPerfect,
    MockProviderRegistry,
    MockProviderAggregator
)
from src.application.interfaces.messaging import MessagePriority, WorkflowStatus
from src.application.interfaces.providers import ProviderStatus, ProviderType


class TestMockRepositories:
    """Test mock repository implementations."""
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="Musterstraße",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
    
    @pytest.fixture
    def sample_search_result(self, sample_address):
        """Create a sample search result for testing."""
        return SearchResult.create_new(sample_address, "test_request_123")
    
    @pytest.fixture
    def sample_connection_session(self):
        """Create a sample connection session for testing."""
        return ConnectionSession.create_new("conn_123", SessionConnectionType.WEBSOCKET)
    
    @pytest.fixture
    def sample_provider_offer(self):
        """Create a sample provider offer for testing."""
        return ProviderOffer(
            provider_name="TestProvider",
            product_id="test_product_1",
            speed_download_mbps=100,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal("39.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=12
        )

    @pytest.mark.asyncio
    async def test_search_result_repository(self, sample_search_result):
        """Test MockSearchResultRepository functionality."""
        repo = MockSearchResultRepository()
        
        # Test save and retrieve by share token
        share_token = await repo.save_result(sample_search_result)
        assert share_token == sample_search_result.share_token
        
        retrieved = await repo.get_result_by_share_token(share_token)
        assert retrieved is not None
        assert retrieved.request_id == sample_search_result.request_id
        
        # Test retrieve by request ID
        retrieved_by_id = await repo.get_result_by_request_id(sample_search_result.request_id)
        assert retrieved_by_id is not None
        assert retrieved_by_id.share_token == share_token
        
        # Test update
        sample_search_result.add_metadata("test_key", "test_value")
        success = await repo.update_result(sample_search_result)
        assert success
        
        updated = await repo.get_result_by_share_token(share_token)
        assert updated.get_metadata("test_key") == "test_value"
        
        # Test delete
        success = await repo.delete_result(share_token)
        assert success
        
        deleted = await repo.get_result_by_share_token(share_token)
        assert deleted is None
    
    @pytest.mark.asyncio
    async def test_connection_repository(self, sample_connection_session):
        """Test MockConnectionRepository functionality."""
        repo = MockConnectionRepository()
        
        # Test save and retrieve
        connection_id = await repo.save_connection(sample_connection_session)
        assert connection_id == sample_connection_session.connection_id
        
        retrieved = await repo.get_connection(connection_id)
        assert retrieved is not None
        assert retrieved.connection_id == connection_id
        
        # Test update
        sample_connection_session.connect()
        success = await repo.update_connection(sample_connection_session)
        assert success
        
        updated = await repo.get_connection(connection_id)
        assert updated.is_connected
        
        # Test active connections
        active = await repo.get_active_connections()
        assert len(active) == 1
        assert active[0].connection_id == connection_id
        
        # Test delete
        success = await repo.delete_connection(connection_id)
        assert success
        
        deleted = await repo.get_connection(connection_id)
        assert deleted is None
    
    @pytest.mark.asyncio
    async def test_provider_offer_repository(self, sample_address, sample_provider_offer):
        """Test MockProviderOfferRepository functionality."""
        repo = MockProviderOfferRepository()
        
        # Test save and retrieve
        success = await repo.save_offers(sample_address, "TestProvider", [sample_provider_offer])
        assert success
        
        cached = await repo.get_cached_offers(sample_address, "TestProvider")
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].provider_name == "TestProvider"
        
        # Test cache expiration
        expired = await repo.get_cached_offers(sample_address, "TestProvider", max_age_hours=0)
        assert expired is None
        
        # Test invalidation
        await repo.save_offers(sample_address, "TestProvider", [sample_provider_offer])
        success = await repo.invalidate_cache(sample_address, "TestProvider")
        assert success
        
        invalidated = await repo.get_cached_offers(sample_address, "TestProvider")
        assert invalidated is None


class TestMockMessaging:
    """Test mock messaging implementations."""
    
    @pytest.mark.asyncio
    async def test_message_queue(self):
        """Test MockMessageQueue functionality."""
        queue = MockMessageQueue()
        
        # Test send message
        message = {"test": "data", "value": 123}
        message_id = await queue.send_message("test_queue", message, MessagePriority.HIGH)
        assert message_id is not None
        
        # Test receive messages
        messages = await queue.receive_messages("test_queue", max_messages=1)
        assert len(messages) == 1
        assert messages[0]["body"] == message
        assert messages[0]["message_id"] == message_id
        
        # Test delete message
        receipt_handle = messages[0]["receipt_handle"]
        success = await queue.delete_message("test_queue", receipt_handle)
        assert success
        
        # Test queue attributes
        attributes = await queue.get_queue_attributes("test_queue")
        assert "approximate_number_of_messages" in attributes
        
        # Test purge queue
        await queue.send_message("test_queue", {"test": "purge"})
        success = await queue.purge_queue("test_queue")
        assert success
        
        messages = await queue.receive_messages("test_queue")
        assert len(messages) == 0
    
    @pytest.mark.asyncio
    async def test_workflow_orchestrator(self):
        """Test MockWorkflowOrchestrator functionality."""
        orchestrator = MockWorkflowOrchestrator()
        
        # Test start workflow
        input_data = {"test": "workflow_input"}
        execution_id = await orchestrator.start_workflow("test_workflow", input_data)
        assert execution_id is not None
        
        # Test get status (should be running initially)
        status = await orchestrator.get_workflow_status(execution_id)
        assert status == WorkflowStatus.RUNNING
        
        # Wait for workflow to complete
        await asyncio.sleep(0.5)
        
        # Test final status
        final_status = await orchestrator.get_workflow_status(execution_id)
        assert final_status in [WorkflowStatus.SUCCEEDED, WorkflowStatus.FAILED]
        
        if final_status == WorkflowStatus.SUCCEEDED:
            output = await orchestrator.get_workflow_output(execution_id)
            assert output is not None
            assert "result" in output
        
        # Test list executions
        executions = await orchestrator.list_workflow_executions("test_workflow")
        assert len(executions) >= 1
        assert any(e["execution_id"] == execution_id for e in executions)
    
    @pytest.mark.asyncio
    async def test_event_bus(self):
        """Test MockEventBus functionality."""
        event_bus = MockEventBus()
        
        # Test publish event
        detail = {"test": "event_data"}
        event_id = await event_bus.publish_event("test.event", "test_source", detail)
        assert event_id is not None
        
        # Test subscribe to events
        received_events = []
        
        async def event_handler(event):
            received_events.append(event)
        
        pattern = {"event_type": "test.event"}
        subscription_id = await event_bus.subscribe_to_events(pattern, event_handler)
        assert subscription_id is not None
        
        # Publish another event to trigger subscription
        await event_bus.publish_event("test.event", "test_source", {"new": "data"})
        
        # Give time for async callback
        await asyncio.sleep(0.1)
        
        # Test unsubscribe
        success = await event_bus.unsubscribe_from_events(subscription_id)
        assert success


class TestMockConnectionManager:
    """Test mock connection manager implementations."""
    
    @pytest.mark.asyncio
    async def test_connection_manager(self):
        """Test MockConnectionManager functionality."""
        manager = MockConnectionManager()
        
        # Add mock connection
        manager.add_mock_connection("conn_123", "websocket")
        
        # Test send to connection
        message = {"type": "test", "data": "hello"}
        success = await manager.send_to_connection("conn_123", message)
        assert success
        
        # Test get sent messages
        sent_messages = manager.get_sent_messages("conn_123")
        assert len(sent_messages) == 1
        assert sent_messages[0]["message"] == message
        
        # Test send to multiple connections
        manager.add_mock_connection("conn_456", "websocket")
        results = await manager.send_to_multiple_connections(["conn_123", "conn_456"], message)
        assert results["conn_123"] is True
        assert results["conn_456"] is True
        
        # Test broadcast message
        sent_count = await manager.broadcast_message({"broadcast": "test"})
        assert sent_count == 2
        
        # Test get active connections
        active = await manager.get_active_connections()
        assert len(active) == 2
        
        # Test disconnect connection
        success = await manager.disconnect_connection("conn_123")
        assert success
        
        active_after_disconnect = await manager.get_active_connections()
        assert len(active_after_disconnect) == 1
    
    @pytest.mark.asyncio
    async def test_topic_manager(self):
        """Test MockTopicManager functionality."""
        topic_manager = MockTopicManager()
        
        # Test subscribe to topic
        success = await topic_manager.subscribe_connection_to_topic("conn_123", "test_topic")
        assert success
        
        # Test get connection topics
        topics = await topic_manager.get_connection_topics("conn_123")
        assert "test_topic" in topics
        
        # Test get topic connections
        connections = await topic_manager.get_topic_connections("test_topic")
        assert "conn_123" in connections
        
        # Test publish to topic
        message = {"topic_message": "hello"}
        sent_count = await topic_manager.publish_to_topic("test_topic", message)
        assert sent_count == 1
        
        # Test unsubscribe
        success = await topic_manager.unsubscribe_connection_from_topic("conn_123", "test_topic")
        assert success
        
        topics_after_unsub = await topic_manager.get_connection_topics("conn_123")
        assert "test_topic" not in topics_after_unsub
    
    @pytest.mark.asyncio
    async def test_connection_notifier(self):
        """Test MockConnectionNotifier functionality."""
        connection_manager = MockConnectionManager()
        connection_manager.add_mock_connection("conn_123", "websocket")
        
        notifier = MockConnectionNotifier(connection_manager)
        
        # Test search initiated notification
        success = await notifier.notify_search_initiated("conn_123", "req_123", "token_123")
        assert success
        
        # Test search progress notification
        success = await notifier.notify_search_progress("conn_123", "req_123", "TestProvider", "processing")
        assert success
        
        # Test search results notification
        results_summary = {"total_offers": 5, "providers": 3}
        success = await notifier.notify_search_results("conn_123", "req_123", results_summary)
        assert success
        
        # Test search error notification
        success = await notifier.notify_search_error("conn_123", "req_123", "Test error message")
        assert success
        
        # Verify notifications were sent
        notifications = notifier.get_notifications_sent("conn_123")
        assert len(notifications) == 4
        
        # Verify notification types
        notification_types = [n["notification_type"] for n in notifications]
        assert "search_initiated" in notification_types
        assert "search_progress" in notification_types
        assert "search_results" in notification_types
        assert "search_error" in notification_types


class TestMockProviders:
    """Test mock provider implementations."""
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="Teststraße",
            house_number="42",
            city="München",
            postal_code="80331",
            country="DE"
        )
    
    @pytest.mark.asyncio
    async def test_mock_provider_service(self, sample_address):
        """Test MockProviderService functionality."""
        provider = MockProviderService("TestProvider", ProviderType.API_BASED)
        
        # Test basic properties
        assert provider.provider_name == "TestProvider"
        assert provider.provider_type == ProviderType.API_BASED
        assert "DE" in provider.supported_regions
        
        # Test address validation
        valid = await provider.validate_address(sample_address)
        assert valid
        
        # Test get offers
        offers = await provider.get_offers(sample_address)
        assert len(offers) > 0
        assert all(offer.provider_name == "TestProvider" for offer in offers)
        
        # Test provider status
        status = await provider.get_provider_status()
        assert status == ProviderStatus.AVAILABLE
        
        # Test rate limit info
        rate_info = await provider.get_rate_limit_info()
        assert "remaining_requests" in rate_info
        assert "total_calls" in rate_info
    
    @pytest.mark.asyncio
    async def test_byteme_provider(self, sample_address):
        """Test MockByteMe provider functionality."""
        provider = MockByteMe()
        
        # Test CSV parsing
        csv_data = await provider.get_csv_data_for_address(sample_address)
        assert "product_id" in csv_data
        assert "download_speed" in csv_data
        
        offers = await provider.parse_csv_data(csv_data)
        assert len(offers) > 0
        assert all(offer.provider_name == "ByteMe" for offer in offers)
    
    @pytest.mark.asyncio
    async def test_verbyndich_provider(self, sample_address):
        """Test MockVerbynDich provider functionality."""
        provider = MockVerbynDich()
        
        # Test API data parsing
        api_data = await provider.get_api_data_for_address(sample_address)
        assert "data" in api_data
        assert "products" in api_data["data"]
        
        offers = await provider.parse_nested_array_data(api_data)
        assert len(offers) > 0
        assert all(offer.provider_name == "VerbynDich" for offer in offers)
    
    @pytest.mark.asyncio
    async def test_webwunder_provider(self, sample_address):
        """Test MockWebWunder provider functionality."""
        provider = MockWebWunder()
        
        # Test offers with metadata
        offers_with_metadata = await provider.get_offers_with_metadata(sample_address)
        assert "offers" in offers_with_metadata
        assert "address_metadata" in offers_with_metadata
        
        offers = offers_with_metadata["offers"]
        assert len(offers) > 0
        assert all("metadata" in offer for offer in offers)
    
    @pytest.mark.asyncio
    async def test_pingperfect_provider(self, sample_address):
        """Test MockPingPerfect provider functionality."""
        provider = MockPingPerfect()
        
        # Test request signing
        request_data = {"test": "data"}
        signature = await provider.sign_request(request_data)
        assert signature.startswith("mock_signature_")
        
        # Test signed offers
        offers = await provider.get_signed_offers(sample_address)
        assert len(offers) > 0
        assert all(offer.has_feature("request_signature") for offer in offers)
        assert all(offer.get_feature("verified") is True for offer in offers)
    
    @pytest.mark.asyncio
    async def test_provider_registry(self, sample_address):
        """Test MockProviderRegistry functionality."""
        registry = MockProviderRegistry()
        provider1 = MockProviderService("Provider1")
        provider2 = MockProviderService("Provider2")
        
        # Test register providers
        success1 = await registry.register_provider(provider1)
        success2 = await registry.register_provider(provider2)
        assert success1 and success2
        
        # Test get provider
        retrieved = await registry.get_provider("Provider1")
        assert retrieved is not None
        assert retrieved.provider_name == "Provider1"
        
        # Test get all providers
        all_providers = await registry.get_all_providers()
        assert len(all_providers) == 2
        
        # Test get available providers
        available = await registry.get_available_providers(sample_address)
        assert len(available) == 2
        
        # Test health status
        health = await registry.get_provider_health_status()
        assert len(health) == 2
        assert all(status == ProviderStatus.AVAILABLE for status in health.values())
        
        # Test unregister
        success = await registry.unregister_provider("Provider1")
        assert success
        
        remaining = await registry.get_all_providers()
        assert len(remaining) == 1
    
    @pytest.mark.asyncio
    async def test_provider_aggregator(self, sample_address):
        """Test MockProviderAggregator functionality."""
        registry = MockProviderRegistry()
        provider1 = MockProviderService("Provider1")
        provider2 = MockProviderService("Provider2")
        
        await registry.register_provider(provider1)
        await registry.register_provider(provider2)
        
        aggregator = MockProviderAggregator(registry)
        
        # Test aggregated offers
        offers = await aggregator.get_aggregated_offers(sample_address)
        assert len(offers) > 0
        
        # Should have offers from both providers
        provider_names = set(offer.provider_name for offer in offers)
        assert "Provider1" in provider_names
        assert "Provider2" in provider_names
        
        # Test specific providers
        specific_offers = await aggregator.get_aggregated_offers(sample_address, ["Provider1"])
        assert len(specific_offers) > 0
        assert all(offer.provider_name == "Provider1" for offer in specific_offers)
        
        # Test parallel offers
        parallel_results = await aggregator.get_parallel_offers(sample_address)
        assert "Provider1" in parallel_results
        assert "Provider2" in parallel_results
        assert len(parallel_results["Provider1"]) > 0
        assert len(parallel_results["Provider2"]) > 0


if __name__ == "__main__":
    pytest.main([__file__])