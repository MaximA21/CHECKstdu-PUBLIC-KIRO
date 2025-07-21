"""Tests for application use cases."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.application.use_cases import (
    SearchOffersUseCase,
    ProcessResultsUseCase,
    ConnectionManagementUseCase,
    ShareResultsUseCase
)
from src.domain.entities.search_result import SearchResult
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType
from src.domain.value_objects.address import Address


class TestSearchOffersUseCase:
    """Test cases for SearchOffersUseCase."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for SearchOffersUseCase."""
        return {
            'search_result_repository': AsyncMock(),
            'connection_repository': AsyncMock(),
            'message_queue': AsyncMock(),
            'logger': MagicMock()
        }
    
    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Create SearchOffersUseCase instance with mocked dependencies."""
        return SearchOffersUseCase(**mock_dependencies)
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="Musterstraße",
            house_number="123",
            city="Berlin",
            postal_code="10115"
        )
    
    @pytest.fixture
    def sample_connection_session(self):
        """Create a sample connection session for testing."""
        session = ConnectionSession.create_new("test-connection-123")
        session.connect()
        return session
    
    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_dependencies, sample_address, sample_connection_session):
        """Test successful search offers execution."""
        # Arrange
        connection_id = "test-connection-123"
        mock_dependencies['connection_repository'].get_connection.return_value = sample_connection_session
        mock_dependencies['search_result_repository'].save_result.return_value = "share-token-123"
        mock_dependencies['message_queue'].send_message.return_value = "message-id-123"
        
        # Act
        result = await use_case.execute(sample_address, connection_id)
        
        # Assert
        assert result["status"] == "initiated"
        assert "request_id" in result
        assert "share_token" in result
        assert result["message"] == "Search request processed successfully"
        
        # Verify repository calls
        mock_dependencies['connection_repository'].get_connection.assert_called_once_with(connection_id)
        mock_dependencies['search_result_repository'].save_result.assert_called_once()
        mock_dependencies['message_queue'].send_message.assert_called_once()


class TestConnectionManagementUseCase:
    """Test cases for ConnectionManagementUseCase."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for ConnectionManagementUseCase."""
        return {
            'connection_repository': AsyncMock(),
            'connection_manager': AsyncMock(),
            'logger': MagicMock()
        }
    
    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Create ConnectionManagementUseCase instance with mocked dependencies."""
        return ConnectionManagementUseCase(**mock_dependencies)
    
    @pytest.mark.asyncio
    async def test_handle_connect_success(self, use_case, mock_dependencies):
        """Test successful connection handling."""
        # Arrange
        connection_id = "test-connection-456"
        mock_dependencies['connection_repository'].save_connection.return_value = connection_id
        
        # Act
        result = await use_case.handle_connect(connection_id)
        
        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "connected"
        assert "connected_at" in result
        assert result["message"] == "Connection established successfully"
        
        # Verify repository call
        mock_dependencies['connection_repository'].save_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_disconnect_success(self, use_case, mock_dependencies):
        """Test successful disconnection handling."""
        # Arrange
        connection_id = "test-connection-456"
        sample_session = ConnectionSession.create_new(connection_id)
        sample_session.connect()
        
        mock_dependencies['connection_repository'].get_connection.return_value = sample_session
        mock_dependencies['connection_repository'].update_connection.return_value = True
        
        # Act
        result = await use_case.handle_disconnect(connection_id, "Test disconnect")
        
        # Assert
        assert result["connection_id"] == connection_id
        assert result["status"] == "disconnected"
        assert result["reason"] == "Test disconnect"
        assert "disconnected_at" in result
        
        # Verify repository calls
        mock_dependencies['connection_repository'].get_connection.assert_called_once_with(connection_id)
        mock_dependencies['connection_repository'].update_connection.assert_called_once()


class TestShareResultsUseCase:
    """Test cases for ShareResultsUseCase."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for ShareResultsUseCase."""
        return {
            'search_result_repository': AsyncMock(),
            'logger': MagicMock()
        }
    
    @pytest.fixture
    def use_case(self, mock_dependencies):
        """Create ShareResultsUseCase instance with mocked dependencies."""
        return ShareResultsUseCase(**mock_dependencies)
    
    @pytest.fixture
    def sample_search_result(self):
        """Create a sample search result for testing."""
        address = Address(
            street="Teststraße",
            house_number="456",
            city="München",
            postal_code="80331"
        )
        return SearchResult.create_new(address, "test-request-789")
    
    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_dependencies, sample_search_result):
        """Test successful share results execution."""
        # Arrange
        share_token = sample_search_result.share_token
        mock_dependencies['search_result_repository'].get_result_by_share_token.return_value = sample_search_result
        
        # Act
        result = await use_case.execute(share_token)
        
        # Assert
        assert result["share_token"] == share_token
        assert "metadata" in result
        assert "offers" in result
        assert "total_offers" in result
        assert "generated_at" in result
        
        # Verify repository call
        mock_dependencies['search_result_repository'].get_result_by_share_token.assert_called_once_with(share_token)


if __name__ == "__main__":
    pytest.main([__file__])