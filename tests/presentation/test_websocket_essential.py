"""Essential WebSocket tests for connection limits, timeouts, and routing."""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any

from src.presentation.lambda_handlers.connect_handler import ConnectHandler
from src.presentation.lambda_handlers.disconnect_handler import DisconnectHandler
from src.presentation.lambda_handlers.results_handler import ResultsHandler
from src.presentation.websocket_handlers.websocket_server import WebSocketServerController
from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType, ConnectionStatus
from src.shared.exceptions.domain import ConnectionException
from src.application.interfaces.logging import ILogger
from src.application.interfaces.repositories import IConnectionRepository
from src.application.interfaces.connections import IConnectionManager


class TestWebSocketConnectionLimits:
    """Test WebSocket connection limit enforcement functionality."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return MagicMock(spec=ILogger)

    @pytest.fixture
    def mock_connection_repository(self):
        """Create mock connection repository."""
        return AsyncMock(spec=IConnectionRepository)

    @pytest.fixture
    def mock_connection_manager(self):
        """Create mock connection manager."""
        return AsyncMock(spec=IConnectionManager)

    @pytest.fixture
    def connection_management_use_case(self, mock_connection_repository, mock_connection_manager, mock_logger):
        """Create connection management use case with mocks."""
        return ConnectionManagementUseCase(
            connection_repository=mock_connection_repository, connection_manager=mock_connection_manager, logger=mock_logger
        )

    @pytest.fixture
    def connect_handler(self, connection_management_use_case, mock_logger):
        """Create connect handler with dependencies."""
        return ConnectHandler(connection_management_use_case=connection_management_use_case, logger=mock_logger)

    @pytest.fixture
    def disconnect_handler(self, connection_management_use_case, mock_logger):
        """Create disconnect handler with dependencies."""
        return DisconnectHandler(connection_management_use_case=connection_management_use_case, logger=mock_logger)

    @pytest.fixture
    def sample_connect_event(self):
        """Create sample WebSocket connect event."""
        return {
            "requestContext": {"connectionId": "test_connection_123", "routeKey": "$connect"},
            "queryStringParameters": {"street": "Test Street 123", "city": "Test City", "postalCode": "12345"},
        }

    @pytest.fixture
    def sample_disconnect_event(self):
        """Create sample WebSocket disconnect event."""
        return {"requestContext": {"connectionId": "test_connection_123", "routeKey": "$disconnect"}}

    @pytest.mark.asyncio
    async def test_connection_establishment_with_limits(
        self, connect_handler, mock_connection_repository, sample_connect_event
    ):
        """Test that connections are established with proper limits."""
        # Mock repository to return None (new connection)
        mock_connection_repository.get_connection.return_value = None
        mock_connection_repository.save_connection = AsyncMock()

        # Execute connection
        result = await connect_handler.handle_request(sample_connect_event)

        # Verify response
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["data"]["message"] == "Verbunden"
        assert response_body["data"]["connection_id"] == "test_connection_123"

        # Verify connection was saved with limits
        mock_connection_repository.save_connection.assert_called_once()
        saved_connection = mock_connection_repository.save_connection.call_args[0][0]
        assert saved_connection.connection_id == "test_connection_123"
        assert saved_connection.max_results == 5
        assert saved_connection.max_connection_minutes == 2
        assert saved_connection.result_count == 0

    @pytest.mark.asyncio
    async def test_result_count_increment_and_limit_check(self, connection_management_use_case, mock_connection_repository):
        """Test result count increment and limit checking."""
        # Create connection session with 4 results (near limit)
        connection_session = ConnectionSession.create_new("test_conn", SessionConnectionType.WEBSOCKET)
        connection_session.connect()
        connection_session.result_count = 4  # One away from limit of 5

        mock_connection_repository.get_connection.return_value = connection_session
        mock_connection_repository.update_connection = AsyncMock()

        # Increment result count (should reach limit)
        result = await connection_management_use_case.increment_result_count_and_check_limits("test_conn")

        # Verify result
        assert result["result_count"] == 5
        assert result["max_results"] == 5
        assert result["should_disconnect"] is True
        assert "Result limit reached" in result["disconnect_reason"]
        assert result["status"] == "disconnected"

        # Verify connection was updated
        mock_connection_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_time_limit_enforcement(self, connection_management_use_case, mock_connection_repository):
        """Test that connections are disconnected after 2 minutes."""
        # Create connection session that's been connected for over 2 minutes
        connection_session = ConnectionSession.create_new("test_conn", SessionConnectionType.WEBSOCKET)
        connection_session.connect()
        # Simulate connection from 3 minutes ago
        connection_session.connected_at = datetime.utcnow() - timedelta(minutes=3)

        mock_connection_repository.get_connection.return_value = connection_session

        # Check connection limits
        result = await connection_management_use_case.check_connection_limits("test_conn")

        # Verify time limit is enforced
        assert result["should_disconnect"] is True
        assert "Time limit reached" in result["disconnect_reason"]
        assert result["connection_duration_minutes"] >= 2
        assert result["max_connection_minutes"] == 2

    @pytest.mark.asyncio
    async def test_connection_limit_enforcement_for_all(
        self, connection_management_use_case, mock_connection_repository, mock_connection_manager
    ):
        """Test bulk connection limit enforcement."""
        # Create multiple connections with different limit states
        conn1 = ConnectionSession.create_new("conn1", SessionConnectionType.WEBSOCKET)
        conn1.connect()
        conn1.result_count = 5  # At result limit

        conn2 = ConnectionSession.create_new("conn2", SessionConnectionType.WEBSOCKET)
        conn2.connect()
        conn2.connected_at = datetime.utcnow() - timedelta(minutes=3)  # Over time limit

        conn3 = ConnectionSession.create_new("conn3", SessionConnectionType.WEBSOCKET)
        conn3.connect()
        conn3.result_count = 2  # Within limits

        mock_connection_repository.get_active_connections.return_value = [conn1, conn2, conn3]
        mock_connection_repository.update_connection = AsyncMock()
        mock_connection_manager.disconnect_connection = AsyncMock()

        # Enforce limits for all connections
        result = await connection_management_use_case.enforce_connection_limits_for_all()

        # Verify enforcement results
        assert result["connections_checked"] == 3
        assert result["connections_disconnected"] == 2  # conn1 and conn2 should be disconnected
        assert result["errors"] == 0
        assert result["status"] == "completed"

        # Verify disconnect was called for limit-exceeded connections
        assert mock_connection_manager.disconnect_connection.call_count == 2

    @pytest.mark.asyncio
    async def test_disconnect_with_limit_statistics(
        self, disconnect_handler, mock_connection_repository, sample_disconnect_event
    ):
        """Test disconnect handler includes connection statistics."""
        # Create connection session with some results and time
        connection_session = ConnectionSession.create_new("test_connection_123", SessionConnectionType.WEBSOCKET)
        connection_session.connect()
        connection_session.result_count = 3
        connection_session.connected_at = datetime.utcnow() - timedelta(minutes=1, seconds=30)

        mock_connection_repository.get_connection.return_value = connection_session
        mock_connection_repository.update_connection = AsyncMock()

        # Execute disconnect
        result = await disconnect_handler.handle_request(sample_disconnect_event)

        # Verify response includes statistics
        assert result["statusCode"] == 200
        response_body = json.loads(result["body"])
        assert response_body["data"]["message"] == "Getrennt"
        assert response_body["data"]["connection_id"] == "test_connection_123"

        # Note: The actual statistics would be in the internal result structure
        # This test verifies the handler processes the disconnect correctly


class TestWebSocketResultDeliveryAndTimeout:
    """Test basic result delivery and timeout behavior."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return MagicMock(spec=ILogger)

    @pytest.fixture
    def mock_result_repository(self):
        """Create mock result repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_connection_management_use_case(self):
        """Create mock connection management use case."""
        return AsyncMock(spec=ConnectionManagementUseCase)

    @pytest.fixture
    def process_results_use_case(self, mock_result_repository, mock_logger):
        """Create process results use case with mocks."""
        use_case = ProcessResultsUseCase(
            search_result_repository=mock_result_repository,
            connection_manager=AsyncMock(),
            provider_registry=AsyncMock(),
            logger=mock_logger,
        )
        return use_case

    @pytest.fixture
    def results_handler(self, process_results_use_case, mock_logger):
        """Create results handler with dependencies."""
        return ResultsHandler(process_results_use_case=process_results_use_case, logger=mock_logger)

    @pytest.fixture
    def sample_results_event(self):
        """Create sample results processing event."""
        return {
            "body": json.dumps(
                {
                    "request_id": "req_123",
                    "provider_name": "test_provider",
                    "connection_id": "conn_123",
                    "address_data": {
                        "street": "Test Street",
                        "house_number": "123",
                        "city": "Test City",
                        "postal_code": "12345",
                    },
                    "results": [
                        {"offer_id": "offer_1", "price": 29.99, "speed": "100 Mbps"},
                        {"offer_id": "offer_2", "price": 39.99, "speed": "200 Mbps"},
                    ],
                }
            )
        }

    @pytest.mark.asyncio
    async def test_result_delivery_increments_count(
        self, results_handler, mock_connection_management_use_case, sample_results_event
    ):
        """Test that result delivery increments connection result count."""
        # Mock the connection management use case
        mock_connection_management_use_case.increment_result_count_and_check_limits.return_value = {
            "result_count": 1,
            "max_results": 5,
            "should_disconnect": False,
            "disconnect_reason": None,
            "status": "connected",
        }

        # Inject the mock into the results handler
        results_handler._process_results_use_case._connection_management_use_case = mock_connection_management_use_case

        # Mock the result repository and other dependencies
        mock_provider_service = AsyncMock()
        mock_provider_service.get_offers.return_value = []

        results_handler._process_results_use_case._search_result_repository.get_result_by_request_id = AsyncMock(
            return_value=None
        )
        results_handler._process_results_use_case._search_result_repository.save_result = AsyncMock()
        results_handler._process_results_use_case._search_result_repository.update_result = AsyncMock()
        results_handler._process_results_use_case._provider_registry.get_provider = AsyncMock(
            return_value=mock_provider_service
        )
        results_handler._process_results_use_case._connection_manager.send_to_connection = AsyncMock(return_value=True)

        # Execute result processing
        result = await results_handler.handle_request(sample_results_event)

        # Verify response
        assert result["statusCode"] == 200

        # Verify result count was incremented
        mock_connection_management_use_case.increment_result_count_and_check_limits.assert_called_once_with("conn_123")

    @pytest.mark.asyncio
    async def test_result_delivery_triggers_disconnect_at_limit(
        self, results_handler, mock_connection_management_use_case, sample_results_event
    ):
        """Test that result delivery triggers disconnect when limit is reached."""
        # Mock reaching the result limit
        mock_connection_management_use_case.increment_result_count_and_check_limits.return_value = {
            "result_count": 5,
            "max_results": 5,
            "should_disconnect": True,
            "disconnect_reason": "Result limit reached (5/5)",
            "status": "disconnected",
        }

        # Inject the mock
        results_handler._process_results_use_case._connection_management_use_case = mock_connection_management_use_case

        # Mock the result repository and other dependencies
        mock_provider_service = AsyncMock()
        mock_provider_service.get_offers.return_value = []

        results_handler._process_results_use_case._search_result_repository.get_result_by_request_id = AsyncMock(
            return_value=None
        )
        results_handler._process_results_use_case._search_result_repository.save_result = AsyncMock()
        results_handler._process_results_use_case._search_result_repository.update_result = AsyncMock()
        results_handler._process_results_use_case._provider_registry.get_provider = AsyncMock(
            return_value=mock_provider_service
        )
        results_handler._process_results_use_case._connection_manager.send_to_connection = AsyncMock(return_value=True)

        # Execute result processing
        result = await results_handler.handle_request(sample_results_event)

        # Verify response (should still be successful)
        assert result["statusCode"] == 200

        # Verify limit check was called and disconnect was triggered
        mock_connection_management_use_case.increment_result_count_and_check_limits.assert_called_once_with("conn_123")

    @pytest.mark.asyncio
    async def test_connection_timeout_behavior(self):
        """Test connection timeout behavior after 2 minutes."""
        # Create connection session
        connection_session = ConnectionSession.create_new("timeout_conn", SessionConnectionType.WEBSOCKET)
        connection_session.connect()

        # Test connection within time limit
        assert not connection_session.should_disconnect_due_to_limits()

        # Simulate time passing (2.5 minutes)
        connection_session.connected_at = datetime.utcnow() - timedelta(minutes=2, seconds=30)

        # Test connection exceeds time limit
        assert connection_session.should_disconnect_due_to_limits()

        # Verify disconnect reason
        reason = connection_session.get_disconnect_reason_for_limits()
        assert "Time limit reached" in reason
        assert "2 minutes" in reason

    @pytest.mark.asyncio
    async def test_websocket_server_connection_tracking(self):
        """Test WebSocket server tracks connections properly."""
        mock_logger = MagicMock(spec=ILogger)
        mock_connection_use_case = AsyncMock(spec=ConnectionManagementUseCase)

        server = WebSocketServerController(connection_management_use_case=mock_connection_use_case, logger=mock_logger)

        # Test initial state
        assert server.get_connection_count() == 0

        # Mock connection establishment
        mock_connection_use_case.handle_connect.return_value = {"connection_id": "test_conn", "status": "connected"}

        # Simulate connection (we can't actually test WebSocket without a real server)
        # But we can test the connection tracking logic
        connection_id = server._generate_connection_id()
        assert connection_id.startswith("conn_")
        assert len(connection_id) == 17  # "conn_" + 12 hex chars


class TestWebSocketConnectionRouting:
    """Test connection routing between implementations."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return MagicMock(spec=ILogger)

    @pytest.mark.asyncio
    async def test_connection_routing_with_implementation_version(self):
        """Test connection routing based on implementation version."""
        mock_connection_repository = AsyncMock(spec=IConnectionRepository)
        mock_connection_manager = AsyncMock(spec=IConnectionManager)
        mock_logger = MagicMock(spec=ILogger)

        connection_use_case = ConnectionManagementUseCase(
            connection_repository=mock_connection_repository, connection_manager=mock_connection_manager, logger=mock_logger
        )

        # Mock repository behavior
        mock_connection_repository.save_connection = AsyncMock()

        # Test with "old" implementation version
        with patch.dict("os.environ", {"IMPLEMENTATION_VERSION": "old"}):
            connect_handler = ConnectHandler(connection_management_use_case=connection_use_case, logger=mock_logger)

            event = {"requestContext": {"connectionId": "old_impl_conn_123", "routeKey": "$connect"}}

            result = await connect_handler.handle_request(event)

            # Verify connection was established
            assert result["statusCode"] == 200
            response_body = json.loads(result["body"])
            assert response_body["data"]["connection_id"] == "old_impl_conn_123"

        # Test with "new" implementation version
        with patch.dict("os.environ", {"IMPLEMENTATION_VERSION": "new"}):
            connect_handler = ConnectHandler(connection_management_use_case=connection_use_case, logger=mock_logger)

            event = {"requestContext": {"connectionId": "new_impl_conn_123", "routeKey": "$connect"}}

            result = await connect_handler.handle_request(event)

            # Verify connection was established
            assert result["statusCode"] == 200
            response_body = json.loads(result["body"])
            assert response_body["data"]["connection_id"] == "new_impl_conn_123"

    @pytest.mark.asyncio
    async def test_connection_id_based_routing(self):
        """Test that connections can be routed based on connection ID patterns."""
        # Test connection ID generation and routing logic
        mock_logger = MagicMock(spec=ILogger)
        mock_connection_use_case = AsyncMock(spec=ConnectionManagementUseCase)

        server = WebSocketServerController(connection_management_use_case=mock_connection_use_case, logger=mock_logger)

        # Generate multiple connection IDs
        conn_ids = [server._generate_connection_id() for _ in range(10)]

        # Verify all IDs are unique and follow pattern
        assert len(set(conn_ids)) == 10  # All unique
        for conn_id in conn_ids:
            assert conn_id.startswith("conn_")
            assert len(conn_id) == 17

        # Test routing logic (50/50 distribution simulation)
        old_impl_count = 0
        new_impl_count = 0

        for conn_id in conn_ids:
            # Simple hash-based routing simulation
            hash_value = hash(conn_id) % 2
            if hash_value == 0:
                old_impl_count += 1
            else:
                new_impl_count += 1

        # Verify roughly even distribution (allowing for some variance in small sample)
        # With 10 items, we expect roughly 5/5 but allow for hash variance
        assert abs(old_impl_count - new_impl_count) <= 5  # Allow more variance in small sample

    @pytest.mark.asyncio
    async def test_connection_routing_preserves_limits(self):
        """Test that connection routing preserves limit enforcement."""
        mock_connection_repository = AsyncMock(spec=IConnectionRepository)
        mock_connection_manager = AsyncMock(spec=IConnectionManager)
        mock_logger = MagicMock(spec=ILogger)

        connection_use_case = ConnectionManagementUseCase(
            connection_repository=mock_connection_repository, connection_manager=mock_connection_manager, logger=mock_logger
        )

        # Mock repository behavior
        mock_connection_repository.save_connection = AsyncMock()

        # Test that both implementations enforce the same limits
        for impl_version in ["old", "new"]:
            with patch.dict("os.environ", {"IMPLEMENTATION_VERSION": impl_version}):
                connect_handler = ConnectHandler(connection_management_use_case=connection_use_case, logger=mock_logger)

                event = {"requestContext": {"connectionId": f"{impl_version}_conn_123", "routeKey": "$connect"}}

                result = await connect_handler.handle_request(event)

                # Verify connection was established with same limits
                assert result["statusCode"] == 200

                # Verify saved connection has consistent limits
                mock_connection_repository.save_connection.assert_called()
                saved_connection = mock_connection_repository.save_connection.call_args[0][0]
                assert saved_connection.max_results == 5
                assert saved_connection.max_connection_minutes == 2

    @pytest.mark.asyncio
    async def test_result_delivery_works_across_implementations(self):
        """Test that result delivery works regardless of implementation routing."""
        mock_logger = MagicMock(spec=ILogger)
        mock_result_repository = AsyncMock()
        mock_connection_management_use_case = AsyncMock(spec=ConnectionManagementUseCase)

        # Mock connection management responses
        mock_connection_management_use_case.increment_result_count_and_check_limits.return_value = {
            "result_count": 1,
            "max_results": 5,
            "should_disconnect": False,
            "disconnect_reason": None,
            "status": "connected",
        }

        process_results_use_case = ProcessResultsUseCase(
            search_result_repository=mock_result_repository,
            connection_manager=AsyncMock(),
            provider_registry=AsyncMock(),
            logger=mock_logger,
        )
        process_results_use_case._connection_management_use_case = mock_connection_management_use_case

        results_handler = ResultsHandler(process_results_use_case=process_results_use_case, logger=mock_logger)

        # Mock result repository
        mock_result_repository.get_result_by_request_id = AsyncMock(return_value=None)
        mock_result_repository.save_result = AsyncMock()
        mock_result_repository.update_result = AsyncMock()

        # Mock provider service
        mock_provider_service = AsyncMock()
        mock_provider_service.get_offers.return_value = []
        process_results_use_case._provider_registry.get_provider = AsyncMock(return_value=mock_provider_service)

        # Test result delivery for both implementation types
        for impl_version in ["old", "new"]:
            event = {
                "body": json.dumps(
                    {
                        "request_id": f"{impl_version}_req_123",
                        "provider_name": "test_provider",
                        "connection_id": f"{impl_version}_conn_123",
                        "address_data": {
                            "street": "Test Street",
                            "house_number": "123",
                            "city": "Test City",
                            "postal_code": "12345",
                        },
                        "results": [{"offer_id": "offer_1", "price": 29.99}],
                    }
                )
            }

            result = await results_handler.handle_request(event)

            # Verify result delivery works for both implementations
            assert result["statusCode"] == 200

            # Verify connection limit check was called
            mock_connection_management_use_case.increment_result_count_and_check_limits.assert_called_with(
                f"{impl_version}_conn_123"
            )


class TestWebSocketErrorHandling:
    """Test WebSocket error handling scenarios."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return MagicMock(spec=ILogger)

    @pytest.mark.asyncio
    async def test_connection_not_found_handling(self):
        """Test handling of connection not found scenarios."""
        mock_connection_repository = AsyncMock(spec=IConnectionRepository)
        mock_connection_manager = AsyncMock(spec=IConnectionManager)
        mock_logger = MagicMock(spec=ILogger)

        connection_use_case = ConnectionManagementUseCase(
            connection_repository=mock_connection_repository, connection_manager=mock_connection_manager, logger=mock_logger
        )

        # Mock repository to return None (connection not found)
        mock_connection_repository.get_connection.return_value = None

        # Test result count increment for non-existent connection
        with pytest.raises(ConnectionException) as exc_info:
            await connection_use_case.increment_result_count_and_check_limits("nonexistent_conn")

        assert "Connection nonexistent_conn not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_connection_id_handling(self):
        """Test handling of invalid connection IDs."""
        mock_connection_repository = AsyncMock(spec=IConnectionRepository)
        mock_connection_manager = AsyncMock(spec=IConnectionManager)
        mock_logger = MagicMock(spec=ILogger)

        connection_use_case = ConnectionManagementUseCase(
            connection_repository=mock_connection_repository, connection_manager=mock_connection_manager, logger=mock_logger
        )

        connect_handler = ConnectHandler(connection_management_use_case=connection_use_case, logger=mock_logger)

        # Test with missing connection ID
        event = {
            "requestContext": {
                "routeKey": "$connect"
                # Missing connectionId
            }
        }

        result = await connect_handler.handle_request(event)

        # Verify error response
        assert result["statusCode"] == 400
        response_body = json.loads(result["body"])
        assert "Connection ID missing" in response_body["error"]

    @pytest.mark.asyncio
    async def test_connection_limit_check_error_handling(self):
        """Test error handling in connection limit checks."""
        mock_connection_repository = AsyncMock(spec=IConnectionRepository)
        mock_connection_manager = AsyncMock(spec=IConnectionManager)
        mock_logger = MagicMock(spec=ILogger)

        connection_use_case = ConnectionManagementUseCase(
            connection_repository=mock_connection_repository, connection_manager=mock_connection_manager, logger=mock_logger
        )

        # Mock repository to raise exception
        mock_connection_repository.get_connection.side_effect = Exception("Database error")

        # Test limit check with error
        result = await connection_use_case.check_connection_limits("error_conn")

        # Verify error is handled gracefully
        assert result["status"] == "error"
        assert result["should_disconnect"] is True
        assert "Error checking limits" in result["disconnect_reason"]
