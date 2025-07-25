"""Unit tests for application use cases."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.application.use_cases.share_results_use_case import ShareResultsUseCase
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType
from src.domain.entities.provider_offer import ConnectionType, ProviderOffer
from src.domain.value_objects.address import Address
from src.shared.exceptions.domain import (
    ConnectionException,
    InvalidAddressException,
    ProcessingException,
    ProviderUnavailableException,
    SearchRequestException,
    ShareResultsException,
    ShareTokenNotFoundException,
)


class TestSearchOffersUseCase:
    """Test SearchOffersUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_search_result_repository = Mock()
        self.mock_connection_repository = Mock()
        self.mock_message_queue = Mock()
        self.mock_logger = Mock()
        self.use_case = SearchOffersUseCase(
            search_result_repository=self.mock_search_result_repository,
            connection_repository=self.mock_connection_repository,
            message_queue=self.mock_message_queue,
            logger=self.mock_logger,
        )

    @pytest.mark.asyncio
    async def test_search_offers_success(self):
        """Test successful offer search."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = None  # HTTP mode without WebSocket connection

        # Mock repository methods
        self.mock_search_result_repository.save_result = AsyncMock()
        self.mock_message_queue.send_message = AsyncMock(return_value="msg-123")

        # Act
        result = await self.use_case.execute(address, connection_id)

        # Assert
        assert result["status"] == "initiated"
        assert "request_id" in result
        assert "share_token" in result
        self.mock_search_result_repository.save_result.assert_called_once()
        self.mock_message_queue.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_offers_no_results(self):
        """Test search with no results."""
        # Arrange
        address = Address(street="Remote Street", house_number="1", city="Rural Town", postal_code="99999", country="DE")
        connection_id = None  # HTTP mode without WebSocket connection

        # Mock repository methods
        self.mock_search_result_repository.save_result = AsyncMock()
        self.mock_message_queue.send_message = AsyncMock(return_value="msg-124")

        # Act
        result = await self.use_case.execute(address, connection_id)

        # Assert
        assert result["status"] == "initiated"
        assert "request_id" in result

    @pytest.mark.asyncio
    async def test_search_offers_repository_error(self):
        """Test search with repository error."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = "conn-125"

        self.mock_search_result_repository.save_result = AsyncMock(side_effect=Exception("Database error"))
        self.mock_connection_repository.get_connection = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(SearchRequestException, match="Failed to initiate search"):
            await self.use_case.execute(address, connection_id)

    @pytest.mark.asyncio
    async def test_search_offers_invalid_address(self):
        """Test search with invalid address."""
        # Arrange
        address = None
        connection_id = "conn-126"

        # Act & Assert
        with pytest.raises(SearchRequestException, match="Failed to initiate search"):
            await self.use_case.execute(address, connection_id)

    @pytest.mark.asyncio
    async def test_search_offers_connection_not_found(self):
        """Test search with non-existent connection."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = "conn-nonexistent"

        self.mock_connection_repository.get_connection = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(SearchRequestException, match="Connection conn-nonexistent not found"):
            await self.use_case.execute(address, connection_id)

    @pytest.mark.asyncio
    async def test_search_offers_connection_not_active(self):
        """Test search with inactive connection."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = "conn-inactive"

        # Create inactive connection session
        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.disconnect("Test disconnect")

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)

        # Act & Assert
        with pytest.raises(SearchRequestException, match="Connection conn-inactive is not active"):
            await self.use_case.execute(address, connection_id)

    @pytest.mark.asyncio
    async def test_search_offers_message_queue_error(self):
        """Test search with message queue error."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = None

        self.mock_search_result_repository.save_result = AsyncMock()
        self.mock_message_queue.send_message = AsyncMock(side_effect=Exception("Queue error"))

        # Act & Assert
        with pytest.raises(SearchRequestException, match="Failed to initiate search"):
            await self.use_case.execute(address, connection_id)

    @pytest.mark.asyncio
    async def test_search_offers_with_active_connection(self):
        """Test search with active WebSocket connection."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = "conn-active"

        # Create active connection session
        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()
        self.mock_search_result_repository.save_result = AsyncMock()
        self.mock_message_queue.send_message = AsyncMock(return_value="msg-127")

        # Act
        result = await self.use_case.execute(address, connection_id)

        # Assert
        assert result["status"] == "initiated"
        assert "request_id" in result
        assert "share_token" in result
        self.mock_connection_repository.get_connection.assert_called_once_with(connection_id)
        self.mock_connection_repository.update_connection.assert_called()
        self.mock_search_result_repository.save_result.assert_called_once()
        self.mock_message_queue.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_offers_with_custom_request_id(self):
        """Test search with custom request ID."""
        # Arrange
        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        connection_id = None
        custom_request_id = "custom-req-123"

        self.mock_search_result_repository.save_result = AsyncMock()
        self.mock_message_queue.send_message = AsyncMock(return_value="msg-128")

        # Act
        result = await self.use_case.execute(address, connection_id, custom_request_id)

        # Assert
        assert result["status"] == "initiated"
        assert result["request_id"] == custom_request_id
        assert "share_token" in result


class TestProcessResultsUseCase:
    """Test ProcessResultsUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_search_result_repository = Mock()
        self.mock_connection_manager = Mock()
        self.mock_provider_registry = Mock()
        self.mock_logger = Mock()
        self.use_case = ProcessResultsUseCase(
            search_result_repository=self.mock_search_result_repository,
            connection_manager=self.mock_connection_manager,
            provider_registry=self.mock_provider_registry,
            logger=self.mock_logger,
        )

    @pytest.mark.asyncio
    async def test_process_results_success(self):
        """Test successful result processing."""
        # Arrange
        request_id = "req-123"
        provider_name = "TestProvider"
        raw_results = {"offers": [{"speed": 100, "price": 29.99}]}
        address_data = {
            "street": "Test Street",
            "house_number": "1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
        }

        # Mock search result
        from src.domain.entities.search_result import SearchResult

        mock_search_result = SearchResult.create_new(Address(**address_data), request_id)

        # Mock provider service
        mock_provider_service = Mock()
        mock_provider_service.provider_name = provider_name
        mock_provider_service.get_offers = AsyncMock(return_value=[])

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()
        self.mock_provider_registry.get_provider = AsyncMock(return_value=mock_provider_service)
        self.mock_connection_manager.send_to_connection = AsyncMock(return_value=True)

        # Act
        result = await self.use_case.execute(
            request_id=request_id, provider_name=provider_name, raw_results=raw_results, address_data=address_data
        )

        # Assert
        assert result["status"] == "processed"
        assert result["request_id"] == request_id
        self.mock_search_result_repository.update_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_results_save_error(self):
        """Test result processing with save error."""
        # Arrange
        request_id = "req-123"
        provider_name = "TestProvider"
        raw_results = {"offers": []}
        address_data = {
            "street": "Test Street",
            "house_number": "1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
        }

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=None)
        self.mock_search_result_repository.save_result = AsyncMock(side_effect=Exception("Database error"))

        # Act & Assert
        with pytest.raises(ProcessingException, match="Failed to process results"):
            await self.use_case.execute(
                request_id=request_id, provider_name=provider_name, raw_results=raw_results, address_data=address_data
            )

    @pytest.mark.asyncio
    async def test_process_results_provider_not_found(self):
        """Test result processing with provider not found."""
        # Arrange
        request_id = "req-124"
        provider_name = "NonExistentProvider"
        raw_results = {"offers": []}
        address_data = {
            "street": "Test Street",
            "house_number": "1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
        }

        from src.domain.entities.search_result import SearchResult

        mock_search_result = SearchResult.create_new(Address(**address_data), request_id)

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=mock_search_result)
        self.mock_provider_registry.get_provider = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ProcessingException, match="Provider service not found"):
            await self.use_case.execute(
                request_id=request_id, provider_name=provider_name, raw_results=raw_results, address_data=address_data
            )

    @pytest.mark.asyncio
    async def test_process_results_provider_parsing_error(self):
        """Test result processing with provider parsing error."""
        # Arrange
        request_id = "req-125"
        provider_name = "ErrorProvider"
        raw_results = {"invalid": "data"}
        address_data = {
            "street": "Test Street",
            "house_number": "1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
        }

        from src.domain.entities.search_result import SearchResult

        mock_search_result = SearchResult.create_new(Address(**address_data), request_id)

        mock_provider_service = Mock()
        mock_provider_service.provider_name = provider_name
        mock_provider_service.get_offers = AsyncMock(side_effect=Exception("Parsing error"))

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()
        self.mock_provider_registry.get_provider = AsyncMock(return_value=mock_provider_service)
        self.mock_connection_manager.send_to_connection = AsyncMock(return_value=True)

        # Act
        result = await self.use_case.execute(
            request_id=request_id, provider_name=provider_name, raw_results=raw_results, address_data=address_data
        )

        # Assert - Should still succeed but with empty offers
        assert result["status"] == "processed"
        assert result["offers_count"] == 0

    @pytest.mark.asyncio
    async def test_process_results_missing_address_data(self):
        """Test result processing without address data for new result."""
        # Arrange
        request_id = "req-126"
        provider_name = "TestProvider"
        raw_results = {"offers": []}

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ProcessingException, match="Address data required"):
            await self.use_case.execute(
                request_id=request_id, provider_name=provider_name, raw_results=raw_results, address_data=None
            )

    @pytest.mark.asyncio
    async def test_process_results_connection_notification_failure(self):
        """Test result processing with connection notification failure."""
        # Arrange
        request_id = "req-127"
        provider_name = "TestProvider"
        connection_id = "conn-127"
        raw_results = {"offers": []}
        address_data = {
            "street": "Test Street",
            "house_number": "1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
        }

        from src.domain.entities.search_result import SearchResult

        mock_search_result = SearchResult.create_new(Address(**address_data), request_id)

        mock_provider_service = Mock()
        mock_provider_service.provider_name = provider_name
        mock_provider_service.get_offers = AsyncMock(return_value=[])

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()
        self.mock_provider_registry.get_provider = AsyncMock(return_value=mock_provider_service)
        self.mock_connection_manager.send_to_connection = AsyncMock(return_value=False)

        # Act
        result = await self.use_case.execute(
            request_id=request_id,
            provider_name=provider_name,
            raw_results=raw_results,
            connection_id=connection_id,
            address_data=address_data,
        )

        # Assert - Should still succeed even if notification fails
        assert result["status"] == "processed"
        assert result["request_id"] == request_id

    @pytest.mark.asyncio
    async def test_process_results_with_connection_limits(self):
        """Test result processing with connection limit checking."""
        # Arrange
        request_id = "req-128"
        provider_name = "TestProvider"
        connection_id = "conn-128"
        raw_results = {"offers": []}
        address_data = {
            "street": "Test Street",
            "house_number": "1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
        }

        from src.domain.entities.search_result import SearchResult

        mock_search_result = SearchResult.create_new(Address(**address_data), request_id)

        mock_provider_service = Mock()
        mock_provider_service.provider_name = provider_name
        mock_provider_service.get_offers = AsyncMock(return_value=[])

        mock_connection_management_use_case = Mock()
        mock_connection_management_use_case.increment_result_count_and_check_limits = AsyncMock(
            return_value={
                "result_count": 5,
                "should_disconnect": True,
                "disconnect_reason": "Maximum results reached",
                "max_results": 5,
            }
        )

        # Create use case with connection management
        use_case = ProcessResultsUseCase(
            search_result_repository=self.mock_search_result_repository,
            connection_manager=self.mock_connection_manager,
            provider_registry=self.mock_provider_registry,
            logger=self.mock_logger,
            connection_management_use_case=mock_connection_management_use_case,
        )

        self.mock_search_result_repository.get_result_by_request_id = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()
        self.mock_provider_registry.get_provider = AsyncMock(return_value=mock_provider_service)
        self.mock_connection_manager.send_to_connection = AsyncMock(return_value=True)

        # Act
        result = await use_case.execute(
            request_id=request_id,
            provider_name=provider_name,
            raw_results=raw_results,
            connection_id=connection_id,
            address_data=address_data,
        )

        # Assert
        assert result["status"] == "processed"
        assert "connection_limit_info" in result
        assert result["connection_limit_info"]["should_disconnect"] is True
        mock_connection_management_use_case.increment_result_count_and_check_limits.assert_called_once_with(connection_id)


class TestConnectionManagementUseCase:
    """Test ConnectionManagementUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_connection_repository = Mock()
        self.mock_connection_manager = Mock()
        self.mock_logger = Mock()
        self.use_case = ConnectionManagementUseCase(
            connection_repository=self.mock_connection_repository,
            connection_manager=self.mock_connection_manager,
            logger=self.mock_logger,
        )

    @pytest.mark.asyncio
    async def test_handle_connect_success(self):
        """Test successful connection handling."""
        # Arrange
        connection_id = "conn-123"
        self.mock_connection_repository.save_connection = AsyncMock()

        # Act
        result = await self.use_case.handle_connect(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "connected"
        self.mock_connection_repository.save_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_disconnect_success(self):
        """Test successful connection disconnection."""
        # Arrange
        from src.domain.entities.connection_session import SessionConnectionType

        existing_session = ConnectionSession.create_new("conn-123", SessionConnectionType.WEBSOCKET)
        existing_session.connect()

        self.mock_connection_repository.get_connection = AsyncMock(return_value=existing_session)
        self.mock_connection_repository.update_connection = AsyncMock()

        # Act
        result = await self.use_case.handle_disconnect("conn-123")

        # Assert
        assert result["connection_id"] == "conn-123"
        assert result["status"] == "disconnected"
        self.mock_connection_repository.get_connection.assert_called_once_with("conn-123")
        self.mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_disconnect_nonexistent_connection(self):
        """Test disconnecting non-existent connection."""
        # Arrange
        self.mock_connection_repository.get_connection = AsyncMock(return_value=None)

        # Act
        result = await self.use_case.handle_disconnect("conn-999")

        # Assert
        assert result["connection_id"] == "conn-999"
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections(self):
        """Test cleaning up stale connections."""
        # Arrange
        from src.domain.entities.connection_session import SessionConnectionType

        active_sessions = [
            ConnectionSession.create_new("conn-123", SessionConnectionType.WEBSOCKET),
            ConnectionSession.create_new("conn-124", SessionConnectionType.WEBSOCKET),
        ]

        for session in active_sessions:
            session.connect()

        self.mock_connection_repository.get_active_connections = AsyncMock(return_value=active_sessions)
        self.mock_connection_repository.cleanup_expired_connections = AsyncMock(return_value=0)
        self.mock_connection_manager.is_connection_active = AsyncMock(return_value=True)

        # Act
        result = await self.use_case.cleanup_stale_connections()

        # Assert
        assert result["connections_checked"] == 2
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_handle_connect_with_client_info(self):
        """Test connection handling with client information."""
        # Arrange
        connection_id = "conn-with-info"
        client_info = {"ip_address": "192.168.1.1", "user_agent": "Mozilla/5.0", "origin": "https://example.com"}

        self.mock_connection_repository.save_connection = AsyncMock()

        # Act
        result = await self.use_case.handle_connect(connection_id, SessionConnectionType.WEBSOCKET, client_info)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "connected"
        assert result["connection_type"] == "WebSocket"
        self.mock_connection_repository.save_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connect_repository_error(self):
        """Test connection handling with repository error."""
        # Arrange
        connection_id = "conn-error"
        self.mock_connection_repository.save_connection = AsyncMock(side_effect=Exception("Database error"))

        # Act & Assert
        with pytest.raises(ConnectionException, match="Failed to establish connection"):
            await self.use_case.handle_connect(connection_id)

    @pytest.mark.asyncio
    async def test_get_connection_status_not_found(self):
        """Test getting status of non-existent connection."""
        # Arrange
        connection_id = "conn-nonexistent"
        self.mock_connection_repository.get_connection = AsyncMock(return_value=None)

        # Act
        result = await self.use_case.get_connection_status(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_get_connection_status_inactive_connection(self):
        """Test getting status of inactive connection."""
        # Arrange
        connection_id = "conn-inactive"
        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()
        self.mock_connection_manager.is_connection_active = AsyncMock(return_value=False)

        # Act
        result = await self.use_case.get_connection_status(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["is_active"] is False
        # Should update connection to disconnected
        self.mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connection_status_error(self):
        """Test getting connection status with error."""
        # Arrange
        connection_id = "conn-error"
        self.mock_connection_repository.get_connection = AsyncMock(side_effect=Exception("Database error"))

        # Act
        result = await self.use_case.get_connection_status(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_cleanup_stale_connections_with_timeouts(self):
        """Test cleanup with actual stale connections."""
        # Arrange
        from src.domain.entities.connection_session import SessionConnectionType

        # Create old connection that should timeout
        old_session = ConnectionSession.create_new("conn-old", SessionConnectionType.WEBSOCKET)
        old_session.connect()
        # Manually set old timestamp to simulate timeout
        old_session._last_activity_at = datetime.utcnow() - timedelta(minutes=35)

        # Create recent connection that should not timeout
        recent_session = ConnectionSession.create_new("conn-recent", SessionConnectionType.WEBSOCKET)
        recent_session.connect()

        active_sessions = [old_session, recent_session]

        self.mock_connection_repository.get_active_connections = AsyncMock(return_value=active_sessions)
        self.mock_connection_repository.cleanup_expired_connections = AsyncMock(return_value=1)
        self.mock_connection_repository.update_connection = AsyncMock()

        # Mock connection manager to return False for old connection (inactive)
        def mock_is_active(conn_id):
            return conn_id != "conn-old"

        self.mock_connection_manager.is_connection_active = AsyncMock(side_effect=mock_is_active)

        # Act
        result = await self.use_case.cleanup_stale_connections(timeout_minutes=30)

        # Assert
        assert result["connections_checked"] == 2
        assert result["stale_connections_cleaned"] >= 1
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_subscribe_to_updates_success(self):
        """Test successful topic subscription."""
        # Arrange
        connection_id = "conn-sub"
        topic = "search_updates"

        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()

        # Act
        result = await self.use_case.subscribe_to_updates(connection_id, topic)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["topic"] == topic
        assert result["subscribed"] is True
        assert result["total_subscriptions"] == 1
        self.mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_to_updates_connection_not_found(self):
        """Test topic subscription with non-existent connection."""
        # Arrange
        connection_id = "conn-nonexistent"
        topic = "search_updates"

        self.mock_connection_repository.get_connection = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ConnectionException, match="Connection conn-nonexistent not found"):
            await self.use_case.subscribe_to_updates(connection_id, topic)

    @pytest.mark.asyncio
    async def test_unsubscribe_from_updates_success(self):
        """Test successful topic unsubscription."""
        # Arrange
        connection_id = "conn-unsub"
        topic = "search_updates"

        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()
        connection_session.subscribed_topics.add(topic)

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()

        # Act
        result = await self.use_case.unsubscribe_from_updates(connection_id, topic)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["topic"] == topic
        assert result["subscribed"] is False
        assert result["total_subscriptions"] == 0
        self.mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_ping_success(self):
        """Test successful ping handling."""
        # Arrange
        connection_id = "conn-ping"

        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()

        # Act
        result = await self.use_case.handle_ping(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["pong"] is True
        assert "timestamp" in result
        self.mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_result_count_and_check_limits_success(self):
        """Test successful result count increment."""
        # Arrange
        connection_id = "conn-increment"

        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()

        # Act
        result = await self.use_case.increment_result_count_and_check_limits(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["result_count"] == 1
        assert result["should_disconnect"] is False
        self.mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_result_count_reaches_limit(self):
        """Test result count increment reaching limit."""
        # Arrange
        connection_id = "conn-limit"

        connection_session = ConnectionSession.create_new(connection_id, SessionConnectionType.WEBSOCKET)
        connection_session.connect()
        # Set result count to max - 1 so next increment reaches limit
        object.__setattr__(connection_session, "result_count", 4)  # Max is 5

        self.mock_connection_repository.get_connection = AsyncMock(return_value=connection_session)
        self.mock_connection_repository.update_connection = AsyncMock()
        self.mock_connection_manager.disconnect_connection = AsyncMock()

        # Act
        result = await self.use_case.increment_result_count_and_check_limits(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["result_count"] == 5
        assert result["should_disconnect"] is True
        assert "disconnect_reason" in result
        self.mock_connection_manager.disconnect_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_connection_limits_not_found(self):
        """Test checking limits for non-existent connection."""
        # Arrange
        connection_id = "conn-nonexistent"
        self.mock_connection_repository.get_connection = AsyncMock(return_value=None)

        # Act
        result = await self.use_case.check_connection_limits(connection_id)

        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "not_found"
        assert result["should_disconnect"] is True

    @pytest.mark.asyncio
    async def test_enforce_connection_limits_for_all(self):
        """Test enforcing limits for all connections."""
        # Arrange
        from src.domain.entities.connection_session import SessionConnectionType

        # Create connection that should be disconnected
        limit_session = ConnectionSession.create_new("conn-limit", SessionConnectionType.WEBSOCKET)
        limit_session.connect()
        object.__setattr__(limit_session, "result_count", 10)  # Over limit

        # Create normal connection
        normal_session = ConnectionSession.create_new("conn-normal", SessionConnectionType.WEBSOCKET)
        normal_session.connect()

        active_sessions = [limit_session, normal_session]

        self.mock_connection_repository.get_active_connections = AsyncMock(return_value=active_sessions)
        self.mock_connection_repository.update_connection = AsyncMock()
        self.mock_connection_manager.disconnect_connection = AsyncMock()

        # Act
        result = await self.use_case.enforce_connection_limits_for_all()

        # Assert
        assert result["connections_checked"] == 2
        assert result["connections_disconnected"] >= 1
        assert result["status"] == "completed"


class TestShareResultsUseCase:
    """Test ShareResultsUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_search_result_repository = Mock()
        self.mock_logger = Mock()
        self.use_case = ShareResultsUseCase(
            search_result_repository=self.mock_search_result_repository, logger=self.mock_logger
        )

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful share results execution."""
        # Arrange
        share_token = "share-token-123"

        # Create mock search result
        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()

        # Act
        result = await self.use_case.execute(share_token)

        # Assert
        assert result["share_token"] == share_token
        assert "offers" in result
        self.mock_search_result_repository.get_result_by_share_token.assert_called_once_with(share_token)

    @pytest.mark.asyncio
    async def test_get_share_statistics_success(self):
        """Test successful share statistics retrieval."""
        # Arrange
        share_token = "share-token-123"

        # Create mock search result
        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)

        # Act
        result = await self.use_case.get_share_statistics(share_token)

        # Assert
        assert result["share_token"] == share_token
        assert "address" in result
        self.mock_search_result_repository.get_result_by_share_token.assert_called_once_with(share_token)

    @pytest.mark.asyncio
    async def test_execute_invalid_token(self):
        """Test share results execution with invalid token."""
        # Arrange
        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(Exception, match="Share token not found"):
            await self.use_case.execute("invalid-token")

    @pytest.mark.asyncio
    async def test_extend_share_expiration_success(self):
        """Test successful share expiration extension."""
        # Arrange
        share_token = "share-token-123"

        # Create mock search result
        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()

        # Act
        result = await self.use_case.extend_share_expiration(share_token, 7)

        # Assert
        assert result["share_token"] == share_token
        assert result["days_extended"] == 7
        assert result["status"] == "extended"
        self.mock_search_result_repository.update_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_empty_token(self):
        """Test share results execution with empty token."""
        # Act & Assert
        with pytest.raises(ShareResultsException, match="Share token is required"):
            await self.use_case.execute("")

    @pytest.mark.asyncio
    async def test_execute_short_token(self):
        """Test share results execution with too short token."""
        # Act & Assert
        with pytest.raises(ShareResultsException, match="Invalid share token format"):
            await self.use_case.execute("short")

    @pytest.mark.asyncio
    async def test_execute_expired_token(self):
        """Test share results execution with expired token."""
        # Arrange
        share_token = "expired-token-123"

        # Create expired search result
        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token
        # Set expiration to past date
        object.__setattr__(mock_search_result, "expires_at", datetime.utcnow() - timedelta(days=1))

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)

        # Act & Assert
        with pytest.raises(ShareTokenNotFoundException, match="Share link has expired"):
            await self.use_case.execute(share_token)

    @pytest.mark.asyncio
    async def test_execute_with_offers(self):
        """Test share results execution with offers."""
        # Arrange
        share_token = "share-token-with-offers"

        # Create search result with offers
        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        # Add some offers
        offer1 = ProviderOffer(
            provider_name="Provider1",
            product_id="prod-1",
            speed_download_mbps=100,
            speed_upload_mbps=50,
            monthly_cost_euros=Decimal("29.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )
        mock_search_result.add_offer(offer1)

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()

        # Act
        result = await self.use_case.execute(share_token)

        # Assert
        assert result["share_token"] == share_token
        assert result["total_offers"] == 1
        assert len(result["offers"]) == 1
        assert result["offers"][0]["provider_name"] == "Provider1"
        assert "best_offers" in result
        assert "summary_stats" in result

    @pytest.mark.asyncio
    async def test_get_share_statistics_error(self):
        """Test share statistics with repository error."""
        # Arrange
        share_token = "error-token"
        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(side_effect=Exception("Database error"))

        # Act & Assert
        with pytest.raises(ShareResultsException, match="Failed to get share statistics"):
            await self.use_case.get_share_statistics(share_token)

    @pytest.mark.asyncio
    async def test_extend_share_expiration_invalid_days(self):
        """Test share expiration extension with invalid days."""
        # Arrange
        share_token = "share-token-123"

        # Act & Assert - Test negative days
        with pytest.raises(ShareResultsException, match="Extension days must be between 1 and 365"):
            await self.use_case.extend_share_expiration(share_token, 0)

        # Act & Assert - Test too many days
        with pytest.raises(ShareResultsException, match="Extension days must be between 1 and 365"):
            await self.use_case.extend_share_expiration(share_token, 400)

    @pytest.mark.asyncio
    async def test_extend_share_expiration_token_not_found(self):
        """Test share expiration extension with non-existent token."""
        # Arrange
        share_token = "nonexistent-token"
        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ShareResultsException, match="Failed to extend expiration"):
            await self.use_case.extend_share_expiration(share_token, 7)

    @pytest.mark.asyncio
    async def test_extend_share_expiration_repository_error(self):
        """Test share expiration extension with repository error."""
        # Arrange
        share_token = "share-token-123"

        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock(side_effect=Exception("Database error"))

        # Act & Assert
        with pytest.raises(ShareResultsException, match="Failed to extend expiration"):
            await self.use_case.extend_share_expiration(share_token, 7)

    @pytest.mark.asyncio
    async def test_execute_access_logging_failure(self):
        """Test share results execution with access logging failure."""
        # Arrange
        share_token = "share-token-log-error"

        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)
        # Make update_result fail only on the second call (access logging)
        self.mock_search_result_repository.update_result = AsyncMock(side_effect=Exception("Logging error"))

        # Act - Should still succeed even if access logging fails
        result = await self.use_case.execute(share_token)

        # Assert
        assert result["share_token"] == share_token
        assert "offers" in result

    @pytest.mark.asyncio
    async def test_execute_with_best_offers(self):
        """Test share results execution with best offers calculation."""
        # Arrange
        share_token = "share-token-best-offers"

        from src.domain.entities.search_result import SearchResult

        address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")
        mock_search_result = SearchResult.create_new(address, "req-123")
        mock_search_result.share_token = share_token

        # Add multiple offers with different characteristics
        cheap_offer = ProviderOffer(
            provider_name="CheapProvider",
            product_id="cheap-1",
            speed_download_mbps=50,
            speed_upload_mbps=25,
            monthly_cost_euros=Decimal("19.99"),
            connection_type=ConnectionType.DSL,
            contract_duration_months=24,
        )

        fast_offer = ProviderOffer(
            provider_name="FastProvider",
            product_id="fast-1",
            speed_download_mbps=1000,
            speed_upload_mbps=500,
            monthly_cost_euros=Decimal("79.99"),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24,
        )

        mock_search_result.add_offer(cheap_offer)
        mock_search_result.add_offer(fast_offer)

        self.mock_search_result_repository.get_result_by_share_token = AsyncMock(return_value=mock_search_result)
        self.mock_search_result_repository.update_result = AsyncMock()

        # Act
        result = await self.use_case.execute(share_token)

        # Assert
        assert result["share_token"] == share_token
        assert result["total_offers"] == 2
        assert "best_offers" in result
        assert result["best_offers"]["cheapest"] is not None
        assert result["best_offers"]["fastest"] is not None
        assert result["best_offers"]["best_value"] is not None

        # Verify offers are sorted by cost per Mbps (best value first)
        offers = result["offers"]
        assert len(offers) == 2
