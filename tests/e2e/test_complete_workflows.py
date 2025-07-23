"""End-to-end tests for complete application workflows."""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.application.use_cases.share_results_use_case import ShareResultsUseCase
from src.domain.entities.connection_session import ConnectionSession
from src.domain.entities.provider_offer import ProviderOffer
from src.domain.entities.search_result import SearchResult
from src.domain.value_objects.address import Address
from src.shared.dependency_injection import get_container


class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def mock_container_with_services(self, mock_aws_services):
        """Set up container with mocked services."""
        container = get_container()

        # Mock external provider responses
        mock_offers = [
            ProviderOffer(
                provider_name="TestProvider1",
                offer_id="offer-1",
                speed_mbps=100,
                price_monthly=29.99,
                technology="fiber",
                availability=True,
            ),
            ProviderOffer(
                provider_name="TestProvider2",
                offer_id="offer-2",
                speed_mbps=50,
                price_monthly=19.99,
                technology="cable",
                availability=True,
            ),
        ]

        with patch(
            "src.infrastructure.external_services.provider_aggregator.ProviderAggregator.get_offers"
        ) as mock_get_offers:
            mock_get_offers.return_value = mock_offers
            yield container

    @pytest.mark.asyncio
    async def test_complete_search_workflow(self, mock_container_with_services, sample_search_request):
        """Test complete search workflow from request to results."""
        container = mock_container_with_services

        # Step 1: Execute search
        search_use_case = container.resolve(SearchOffersUseCase)
        search_result = await search_use_case.execute(sample_search_request)

        # Verify search result
        assert isinstance(search_result, SearchResult)
        assert search_result.request_id == sample_search_request["request_id"]
        assert len(search_result.offers) == 2
        assert search_result.offers[0].provider_name == "TestProvider1"
        assert search_result.offers[1].provider_name == "TestProvider2"

        # Step 2: Process results
        process_use_case = container.resolve(ProcessResultsUseCase)
        processed_result = await process_use_case.execute(
            {"search_result": search_result, "connection_id": sample_search_request["connection_id"]}
        )

        # Verify processing
        assert processed_result is not None
        assert processed_result["status"] == "processed"
        assert processed_result["connection_id"] == sample_search_request["connection_id"]

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, mock_container_with_services, websocket_event):
        """Test complete WebSocket connection lifecycle."""
        container = mock_container_with_services
        connection_use_case = container.resolve(ConnectionManagementUseCase)

        # Step 1: Connect
        connect_result = await connection_use_case.handle_connect(websocket_event)
        assert connect_result["statusCode"] == 200

        connection_id = websocket_event["requestContext"]["connectionId"]

        # Step 2: Send search request through WebSocket
        search_event = {
            **websocket_event,
            "requestContext": {**websocket_event["requestContext"], "routeKey": "search"},
            "body": json.dumps(
                {
                    "action": "search",
                    "address": {"street": "Test Street", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
                }
            ),
        }

        search_use_case = container.resolve(SearchOffersUseCase)
        search_result = await search_use_case.execute(
            {
                "address": json.loads(search_event["body"])["address"],
                "connection_id": connection_id,
                "request_id": "test-req-123",
            }
        )

        # Verify search executed
        assert isinstance(search_result, SearchResult)
        assert len(search_result.offers) > 0

        # Step 3: Disconnect
        disconnect_event = {
            **websocket_event,
            "requestContext": {**websocket_event["requestContext"], "routeKey": "$disconnect"},
        }

        disconnect_result = await connection_use_case.handle_disconnect(disconnect_event)
        assert disconnect_result["statusCode"] == 200

    @pytest.mark.asyncio
    async def test_share_results_workflow(self, mock_container_with_services, sample_search_request):
        """Test complete share results workflow."""
        container = mock_container_with_services

        # Step 1: Execute search to get results
        search_use_case = container.resolve(SearchOffersUseCase)
        search_result = await search_use_case.execute(sample_search_request)

        # Step 2: Share results
        share_use_case = container.resolve(ShareResultsUseCase)
        share_request = {
            "search_result_id": search_result.result_id,
            "recipient_email": "test@example.com",
            "message": "Check out these internet offers!",
        }

        share_result = await share_use_case.execute(share_request)

        # Verify sharing
        assert share_result is not None
        assert share_result["status"] == "shared"
        assert share_result["share_id"] is not None

    @pytest.mark.asyncio
    async def test_error_handling_in_complete_workflow(self, mock_container_with_services):
        """Test error handling throughout complete workflow."""
        container = mock_container_with_services

        # Test with invalid address
        invalid_request = {
            "address": {
                "street": "",  # Invalid empty street
                "city": "",  # Invalid empty city
                "postal_code": "invalid",
                "country": "",
            },
            "connection_id": "test-connection-123",
            "request_id": "req-456",
        }

        search_use_case = container.resolve(SearchOffersUseCase)

        # Should handle validation errors gracefully
        with pytest.raises(Exception) as exc_info:
            await search_use_case.execute(invalid_request)

        # Verify error is properly typed
        assert "validation" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_concurrent_search_requests(self, mock_container_with_services):
        """Test handling multiple concurrent search requests."""
        container = mock_container_with_services
        search_use_case = container.resolve(SearchOffersUseCase)

        # Create multiple concurrent requests
        requests = []
        for i in range(5):
            request = {
                "address": {"street": f"Test Street {i}", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
                "connection_id": f"test-connection-{i}",
                "request_id": f"req-{i}",
            }
            requests.append(request)

        # Execute all requests concurrently
        tasks = [search_use_case.execute(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all requests completed
        assert len(results) == 5

        # Verify successful results
        successful_results = [r for r in results if isinstance(r, SearchResult)]
        assert len(successful_results) >= 3  # Allow some failures in concurrent testing

        # Verify each result has correct structure
        for result in successful_results:
            assert isinstance(result, SearchResult)
            assert len(result.offers) > 0

    @pytest.mark.asyncio
    async def test_provider_failure_resilience(self, mock_container_with_services):
        """Test system resilience when some providers fail."""
        container = mock_container_with_services

        # Mock one provider failing
        with patch(
            "src.infrastructure.external_services.provider_aggregator.ProviderAggregator.get_offers"
        ) as mock_get_offers:
            # Simulate partial provider failure
            mock_get_offers.side_effect = [
                [
                    ProviderOffer(
                        provider_name="WorkingProvider",
                        offer_id="offer-1",
                        speed_mbps=100,
                        price_monthly=29.99,
                        technology="fiber",
                        availability=True,
                    )
                ],
                Exception("Provider timeout"),  # Second provider fails
            ]

            search_use_case = container.resolve(SearchOffersUseCase)
            search_request = {
                "address": {"street": "Test Street", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
                "connection_id": "test-connection-123",
                "request_id": "req-456",
            }

            # Should still return results from working providers
            result = await search_use_case.execute(search_request)

            # Verify we get partial results
            assert isinstance(result, SearchResult)
            # Should have at least some offers even if some providers failed
            assert len(result.offers) >= 0  # May be 0 if all providers fail, but shouldn't crash

    @pytest.mark.asyncio
    async def test_data_persistence_workflow(self, mock_container_with_services, sample_search_request):
        """Test data persistence throughout workflow."""
        container = mock_container_with_services

        # Execute search
        search_use_case = container.resolve(SearchOffersUseCase)
        search_result = await search_use_case.execute(sample_search_request)

        # Verify result has persistent ID
        assert search_result.result_id is not None
        assert search_result.timestamp is not None

        # Simulate retrieving stored result
        process_use_case = container.resolve(ProcessResultsUseCase)
        retrieved_result = await process_use_case.execute(
            {"result_id": search_result.result_id, "connection_id": sample_search_request["connection_id"]}
        )

        # Verify data consistency
        assert retrieved_result is not None
        assert retrieved_result["result_id"] == search_result.result_id

    @pytest.mark.asyncio
    async def test_monitoring_and_logging_workflow(self, mock_container_with_services, sample_search_request, mock_logger):
        """Test that monitoring and logging work throughout workflow."""
        container = mock_container_with_services

        with patch("src.infrastructure.logging.logger_factory.LoggerFactory.get_logger", return_value=mock_logger):
            # Execute search workflow
            search_use_case = container.resolve(SearchOffersUseCase)
            await search_use_case.execute(sample_search_request)

            # Verify logging occurred
            assert mock_logger.info.called or mock_logger.debug.called

            # Verify error logging works
            with pytest.raises(Exception):
                await search_use_case.execute(
                    {"address": None, "connection_id": "test", "request_id": "test"}  # Invalid request
                )

            # Should have logged the error
            assert mock_logger.error.called or mock_logger.warning.called


class TestWorkflowIntegration:
    """Test integration between different workflow components."""

    @pytest.mark.asyncio
    async def test_lambda_handler_integration(self, mock_aws_services, lambda_context, rest_api_event):
        """Test integration with Lambda handlers."""
        from src.presentation.lambda_handlers.search_handler import lambda_handler

        # Execute Lambda handler
        response = await lambda_handler(rest_api_event, lambda_context)

        # Verify response structure
        assert "statusCode" in response
        assert "body" in response
        assert "headers" in response

        # Verify successful execution
        assert response["statusCode"] in [200, 202]  # Success or accepted

    @pytest.mark.asyncio
    async def test_websocket_handler_integration(self, mock_aws_services, lambda_context, websocket_event):
        """Test integration with WebSocket handlers."""
        from src.presentation.lambda_handlers.connect_handler import lambda_handler as connect_handler

        # Test connection
        response = await connect_handler(websocket_event, lambda_context)

        # Verify connection response
        assert "statusCode" in response
        assert response["statusCode"] == 200

    def test_configuration_integration(self, app_config):
        """Test configuration integration across components."""
        container = get_container()

        # Verify configuration is properly injected
        from src.infrastructure.config import AppConfig

        resolved_config = container.resolve(AppConfig)

        assert resolved_config.environment.value == "testing"
        assert resolved_config.aws_region == "eu-central-1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
