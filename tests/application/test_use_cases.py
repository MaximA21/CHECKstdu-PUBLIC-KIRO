"""Unit tests for application use cases."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.application.use_cases.share_results_use_case import ShareResultsUseCase
from src.domain.entities.connection_session import ConnectionSession
from src.domain.entities.provider_offer import ProviderOffer
from src.domain.value_objects.address import Address


class TestSearchOffersUseCase:
    """Test SearchOffersUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_provider_registry = Mock()
        self.mock_logger = Mock()
        self.use_case = SearchOffersUseCase(provider_registry=self.mock_provider_registry, logger=self.mock_logger)

    @pytest.mark.asyncio
    async def test_search_offers_success(self):
        """Test successful offer search."""
        # Arrange
        address = Address(street="Test Street 1", city="Berlin", postal_code="10115", country="Germany")

        mock_offers = [
            ProviderOffer(
                provider_name="TestProvider",
                offer_id="offer-1",
                speed_mbps=100,
                price_monthly=29.99,
                technology="fiber",
                availability=True,
                installation_fee=0.0,
            )
        ]

        self.mock_provider_registry.search_offers = AsyncMock(return_value=mock_offers)

        # Act
        result = await self.use_case.execute(address, "req-123")

        # Assert
        assert result.request_id == "req-123"
        assert len(result.offers) == 1
        assert result.offers[0].provider_name == "TestProvider"
        self.mock_provider_registry.search_offers.assert_called_once_with(address)

    @pytest.mark.asyncio
    async def test_search_offers_no_results(self):
        """Test search with no results."""
        # Arrange
        address = Address(street="Remote Street 1", city="Rural Town", postal_code="99999", country="Germany")

        self.mock_provider_registry.search_offers = AsyncMock(return_value=[])

        # Act
        result = await self.use_case.execute(address, "req-124")

        # Assert
        assert result.request_id == "req-124"
        assert len(result.offers) == 0

    @pytest.mark.asyncio
    async def test_search_offers_provider_error(self):
        """Test search with provider error."""
        # Arrange
        address = Address(street="Test Street 1", city="Berlin", postal_code="10115", country="Germany")

        self.mock_provider_registry.search_offers = AsyncMock(side_effect=Exception("Provider API error"))

        # Act & Assert
        with pytest.raises(Exception, match="Provider API error"):
            await self.use_case.execute(address, "req-125")


class TestProcessResultsUseCase:
    """Test ProcessResultsUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repository = Mock()
        self.mock_messaging = Mock()
        self.mock_logger = Mock()
        self.use_case = ProcessResultsUseCase(
            repository=self.mock_repository, messaging=self.mock_messaging, logger=self.mock_logger
        )

    @pytest.mark.asyncio
    async def test_process_results_success(self):
        """Test successful result processing."""
        # Arrange
        offers = [
            ProviderOffer(
                provider_name="Provider1",
                offer_id="offer-1",
                speed_mbps=100,
                price_monthly=29.99,
                technology="fiber",
                availability=True,
                installation_fee=0.0,
            )
        ]

        self.mock_repository.save_search_result = AsyncMock()
        self.mock_messaging.send_results = AsyncMock()

        # Act
        await self.use_case.execute("req-123", "conn-456", offers)

        # Assert
        self.mock_repository.save_search_result.assert_called_once()
        self.mock_messaging.send_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_results_save_error(self):
        """Test result processing with save error."""
        # Arrange
        offers = [
            ProviderOffer(
                provider_name="Provider1",
                offer_id="offer-1",
                speed_mbps=100,
                price_monthly=29.99,
                technology="fiber",
                availability=True,
                installation_fee=0.0,
            )
        ]

        self.mock_repository.save_search_result = AsyncMock(side_effect=Exception("Database error"))

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            await self.use_case.execute("req-123", "conn-456", offers)


class TestConnectionManagementUseCase:
    """Test ConnectionManagementUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repository = Mock()
        self.mock_logger = Mock()
        self.use_case = ConnectionManagementUseCase(repository=self.mock_repository, logger=self.mock_logger)

    @pytest.mark.asyncio
    async def test_create_connection_success(self):
        """Test successful connection creation."""
        # Arrange
        self.mock_repository.save_connection = AsyncMock()

        # Act
        session = await self.use_case.create_connection("conn-123", "user-456")

        # Assert
        assert session.connection_id == "conn-123"
        assert session.user_id == "user-456"
        assert session.status == "active"
        self.mock_repository.save_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_connection_success(self):
        """Test successful connection disconnection."""
        # Arrange
        existing_session = ConnectionSession(
            connection_id="conn-123",
            user_id="user-456",
            connected_at="2024-01-01T12:00:00Z",
            last_activity="2024-01-01T12:05:00Z",
            status="active",
        )

        self.mock_repository.get_connection = AsyncMock(return_value=existing_session)
        self.mock_repository.update_connection = AsyncMock()

        # Act
        await self.use_case.disconnect_connection("conn-123")

        # Assert
        self.mock_repository.get_connection.assert_called_once_with("conn-123")
        self.mock_repository.update_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(self):
        """Test disconnecting non-existent connection."""
        # Arrange
        self.mock_repository.get_connection = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Connection not found"):
            await self.use_case.disconnect_connection("conn-999")

    @pytest.mark.asyncio
    async def test_get_active_connections(self):
        """Test getting active connections."""
        # Arrange
        active_sessions = [
            ConnectionSession(
                connection_id="conn-123",
                user_id="user-456",
                connected_at="2024-01-01T12:00:00Z",
                last_activity="2024-01-01T12:05:00Z",
                status="active",
            ),
            ConnectionSession(
                connection_id="conn-124",
                user_id="user-457",
                connected_at="2024-01-01T12:01:00Z",
                last_activity="2024-01-01T12:06:00Z",
                status="active",
            ),
        ]

        self.mock_repository.get_active_connections = AsyncMock(return_value=active_sessions)

        # Act
        connections = await self.use_case.get_active_connections()

        # Assert
        assert len(connections) == 2
        assert all(conn.status == "active" for conn in connections)


class TestShareResultsUseCase:
    """Test ShareResultsUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repository = Mock()
        self.mock_logger = Mock()
        self.use_case = ShareResultsUseCase(repository=self.mock_repository, logger=self.mock_logger)

    @pytest.mark.asyncio
    async def test_create_share_link_success(self):
        """Test successful share link creation."""
        # Arrange
        self.mock_repository.create_share_token = AsyncMock(return_value="share-token-123")

        # Act
        share_url = await self.use_case.create_share_link("req-123")

        # Assert
        assert "share-token-123" in share_url
        self.mock_repository.create_share_token.assert_called_once_with("req-123")

    @pytest.mark.asyncio
    async def test_get_shared_results_success(self):
        """Test successful shared results retrieval."""
        # Arrange
        mock_result = Mock()
        mock_result.request_id = "req-123"
        mock_result.offers = []

        self.mock_repository.get_results_by_share_token = AsyncMock(return_value=mock_result)

        # Act
        result = await self.use_case.get_shared_results("share-token-123")

        # Assert
        assert result.request_id == "req-123"
        self.mock_repository.get_results_by_share_token.assert_called_once_with("share-token-123")

    @pytest.mark.asyncio
    async def test_get_shared_results_invalid_token(self):
        """Test shared results retrieval with invalid token."""
        # Arrange
        self.mock_repository.get_results_by_share_token = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid or expired share token"):
            await self.use_case.get_shared_results("invalid-token")

    @pytest.mark.asyncio
    async def test_revoke_share_link_success(self):
        """Test successful share link revocation."""
        # Arrange
        self.mock_repository.revoke_share_token = AsyncMock(return_value=True)

        # Act
        result = await self.use_case.revoke_share_link("share-token-123")

        # Assert
        assert result is True
        self.mock_repository.revoke_share_token.assert_called_once_with("share-token-123")

    @pytest.mark.asyncio
    async def test_revoke_share_link_not_found(self):
        """Test share link revocation for non-existent token."""
        # Arrange
        self.mock_repository.revoke_share_token = AsyncMock(return_value=False)

        # Act
        result = await self.use_case.revoke_share_link("nonexistent-token")

        # Assert
        assert result is False
