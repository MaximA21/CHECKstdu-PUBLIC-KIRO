"""Tests for connection limit enforcement functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType, ConnectionStatus
from src.shared.exceptions.domain import ConnectionException


class TestConnectionLimitEnforcement:
    """Test cases for connection limit enforcement."""
    
    @pytest.fixture
    def mock_connection_repository(self):
        """Mock connection repository."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_connection_manager(self):
        """Mock connection manager."""
        return AsyncMock()
    
    @pytest.fixture
    def mock_logger(self):
        """Mock logger."""
        return MagicMock()
    
    @pytest.fixture
    def connection_management_use_case(self, mock_connection_repository, mock_connection_manager, mock_logger):
        """Connection management use case with mocked dependencies."""
        return ConnectionManagementUseCase(
            connection_repository=mock_connection_repository,
            connection_manager=mock_connection_manager,
            logger=mock_logger
        )
    
    @pytest.mark.asyncio
    async def test_increment_result_count_and_check_limits_success(
        self, 
        connection_management_use_case, 
        mock_connection_repository
    ):
        """Test successful result count increment and limit checking."""
        # Setup
        connection_id = "test-connection-123"
        connection_session = ConnectionSession.create_new(connection_id)
        connection_session.connect()
        
        mock_connection_repository.get_connection.return_value = connection_session
        mock_connection_repository.update_connection.return_value = True
        
        # Execute
        result = await connection_management_use_case.increment_result_count_and_check_limits(connection_id)
        
        # Verify
        assert result["connection_id"] == connection_id
        assert result["result_count"] == 1
        assert result["max_results"] == 5
        assert result["should_disconnect"] == False
        assert result["disconnect_reason"] is None
        assert result["status"] == "connected"
        
        # Verify repository calls
        mock_connection_repository.get_connection.assert_called_once_with(connection_id)
        mock_connection_repository.update_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_increment_result_count_reaches_limit(
        self, 
        connection_management_use_case, 
        mock_connection_repository,
        mock_connection_manager
    ):
        """Test result count increment that reaches the limit."""
        # Setup
        connection_id = "test-connection-123"
        connection_session = ConnectionSession.create_new(connection_id)
        connection_session.connect()
        
        # Set result count to 4 (one away from limit)
        for _ in range(4):
            connection_session.increment_result_count()
        
        mock_connection_repository.get_connection.return_value = connection_session
        mock_connection_repository.update_connection.return_value = True
        mock_connection_manager.disconnect_connection.return_value = True
        
        # Execute
        result = await connection_management_use_case.increment_result_count_and_check_limits(connection_id)
        
        # Verify
        assert result["connection_id"] == connection_id
        assert result["result_count"] == 5
        assert result["max_results"] == 5
        assert result["should_disconnect"] == True
        assert "Result limit reached" in result["disconnect_reason"]
        assert result["status"] == "disconnected"
        
        # Verify connection manager was called to disconnect
        mock_connection_manager.disconnect_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_connection_limits_time_limit(
        self, 
        connection_management_use_case, 
        mock_connection_repository
    ):
        """Test connection limit checking for time limit."""
        # Setup
        connection_id = "test-connection-123"
        past_time = datetime.utcnow() - timedelta(minutes=3)
        
        connection_session = ConnectionSession(
            connection_id=connection_id,
            status=ConnectionStatus.CONNECTED,
            connected_at=past_time,
            last_activity_at=past_time
        )
        
        mock_connection_repository.get_connection.return_value = connection_session
        
        # Execute
        result = await connection_management_use_case.check_connection_limits(connection_id)
        
        # Verify
        assert result["connection_id"] == connection_id
        assert result["should_disconnect"] == True
        assert "Time limit reached" in result["disconnect_reason"]
        assert result["connection_duration_minutes"] >= 2
        assert result["max_connection_minutes"] == 2
    
    @pytest.mark.asyncio
    async def test_check_connection_limits_not_found(
        self, 
        connection_management_use_case, 
        mock_connection_repository
    ):
        """Test connection limit checking for non-existent connection."""
        # Setup
        connection_id = "non-existent-connection"
        mock_connection_repository.get_connection.return_value = None
        
        # Execute
        result = await connection_management_use_case.check_connection_limits(connection_id)
        
        # Verify
        assert result["connection_id"] == connection_id
        assert result["status"] == "not_found"
        assert result["should_disconnect"] == True
        assert result["disconnect_reason"] == "Connection not found"
    
    @pytest.mark.asyncio
    async def test_enforce_connection_limits_for_all(
        self, 
        connection_management_use_case, 
        mock_connection_repository,
        mock_connection_manager
    ):
        """Test enforcing connection limits for all connections."""
        # Setup - create connections with different states
        connection1 = ConnectionSession.create_new("conn-1")
        connection1.connect()
        # This one should be disconnected due to result limit
        for _ in range(5):
            connection1.increment_result_count()
        
        connection2 = ConnectionSession.create_new("conn-2")
        connection2.connect()
        # This one is within limits
        connection2.increment_result_count()
        
        # This one should be disconnected due to time limit
        past_time = datetime.utcnow() - timedelta(minutes=3)
        connection3 = ConnectionSession(
            connection_id="conn-3",
            status=ConnectionStatus.CONNECTED,
            connected_at=past_time,
            last_activity_at=past_time
        )
        
        mock_connection_repository.get_active_connections.return_value = [
            connection1, connection2, connection3
        ]
        mock_connection_repository.update_connection.return_value = True
        mock_connection_manager.disconnect_connection.return_value = True
        
        # Execute
        result = await connection_management_use_case.enforce_connection_limits_for_all()
        
        # Verify
        assert result["connections_checked"] == 3
        assert result["connections_disconnected"] == 2  # conn-1 and conn-3
        assert result["errors"] == 0
        assert result["status"] == "completed"
        
        # Verify connection manager was called to disconnect the right connections
        assert mock_connection_manager.disconnect_connection.call_count == 2
    
    @pytest.mark.asyncio
    async def test_increment_result_count_connection_not_found(
        self, 
        connection_management_use_case, 
        mock_connection_repository
    ):
        """Test result count increment when connection is not found."""
        # Setup
        connection_id = "non-existent-connection"
        mock_connection_repository.get_connection.return_value = None
        
        # Execute and verify exception
        with pytest.raises(ConnectionException, match="Connection non-existent-connection not found"):
            await connection_management_use_case.increment_result_count_and_check_limits(connection_id)
    
    @pytest.mark.asyncio
    async def test_increment_result_count_connection_not_active(
        self, 
        connection_management_use_case, 
        mock_connection_repository
    ):
        """Test result count increment when connection is not active."""
        # Setup
        connection_id = "inactive-connection"
        connection_session = ConnectionSession.create_new(connection_id)
        # Don't connect it, so it's not active
        
        mock_connection_repository.get_connection.return_value = connection_session
        
        # Execute and verify exception
        with pytest.raises(ConnectionException, match="Connection inactive-connection is not active"):
            await connection_management_use_case.increment_result_count_and_check_limits(connection_id)