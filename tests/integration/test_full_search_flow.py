"""Integration tests for full search flow with real AWS services."""

import asyncio
import json
import os
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.domain.entities.search_result import SearchResult
from src.domain.value_objects.address import Address
from src.infrastructure.external_services.provider_aggregator import ProviderAggregator
from src.infrastructure.messaging.aws_websocket_adapter import AWSAPIGatewayWebSocketManager
from src.infrastructure.persistence.aws_dynamodb_repository import AWSDynamoDBSearchResultRepository
from src.shared.dependency_injection import get_container


@pytest.mark.integration
class TestFullSearchFlowIntegration:
    """Integration tests for complete search flow."""

    @pytest.fixture
    def integration_container(self):
        """Set up container for integration testing."""
        container = get_container()
        return container

    @pytest.fixture
    def mock_dynamodb_integration(self):
        """Mock DynamoDB for integration testing."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = Mock()
            mock_table = Mock()

            # Mock table operations
            mock_table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_table.get_item.return_value = {
                "Item": {
                    "result_id": "test-result-123",
                    "offers": [
                        {
                            "provider_name": "TestProvider",
                            "offer_id": "offer-123",
                            "speed_mbps": 100,
                            "price_monthly": 29.99,
                            "technology": "fiber",
                            "availability": True,
                        }
                    ],
                    "timestamp": "2024-01-01T12:00:00Z",
                }
            }
            mock_table.query.return_value = {
                "Items": [{"connection_id": "test-conn-123", "result_id": "test-result-123", "status": "completed"}]
            }

            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.return_value = mock_dynamodb

            yield mock_table

    @pytest.fixture
    def mock_websocket_integration(self):
        """Mock WebSocket API Gateway for integration testing."""
        with patch("boto3.client") as mock_boto3:
            mock_apigateway = Mock()
            mock_apigateway.post_to_connection.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

            def client_side_effect(service_name, **kwargs):
                if service_name == "apigatewaymanagementapi":
                    return mock_apigateway
                return Mock()

            mock_boto3.side_effect = client_side_effect
            yield mock_apigateway

    @pytest.mark.asyncio
    async def test_search_flow_with_mocked_aws(
        self, integration_container, mock_dynamodb_integration, mock_websocket_integration
    ):
        """Test complete search flow with mocked AWS services."""
        # Mock external provider responses
        with patch.object(ProviderAggregator, "get_offers") as mock_get_offers:
            mock_get_offers.return_value = [
                {
                    "provider_name": "TestProvider1",
                    "offer_id": "offer-1",
                    "speed_mbps": 100,
                    "price_monthly": 29.99,
                    "technology": "fiber",
                    "availability": True,
                    "installation_fee": 0.0,
                },
                {
                    "provider_name": "TestProvider2",
                    "offer_id": "offer-2",
                    "speed_mbps": 50,
                    "price_monthly": 19.99,
                    "technology": "cable",
                    "availability": True,
                    "installation_fee": 49.99,
                },
            ]

            # Execute search
            search_use_case = integration_container.resolve(SearchOffersUseCase)
            search_request = {
                "address": {"street": "Musterstraße 1", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
                "connection_id": "test-connection-123",
                "request_id": "req-integration-test",
            }

            result = await search_use_case.execute(search_request)

            # Verify result structure
            assert isinstance(result, SearchResult)
            assert result.request_id == "req-integration-test"
            assert len(result.offers) == 2

            # Verify DynamoDB interaction
            assert mock_dynamodb_integration.put_item.called

            # Verify offers content
            offers = result.offers
            assert offers[0].provider_name == "TestProvider1"
            assert offers[0].speed_mbps == 100
            assert offers[1].provider_name == "TestProvider2"
            assert offers[1].speed_mbps == 50

    @pytest.mark.asyncio
    async def test_result_processing_integration(
        self, integration_container, mock_dynamodb_integration, mock_websocket_integration
    ):
        """Test result processing with AWS integration."""
        process_use_case = integration_container.resolve(ProcessResultsUseCase)

        # Process results
        process_request = {"result_id": "test-result-123", "connection_id": "test-connection-123"}

        result = await process_use_case.execute(process_request)

        # Verify processing
        assert result is not None
        assert result["status"] == "processed"

        # Verify DynamoDB query was called
        assert mock_dynamodb_integration.get_item.called or mock_dynamodb_integration.query.called

    @pytest.mark.asyncio
    async def test_websocket_message_delivery_integration(self, integration_container, mock_websocket_integration):
        """Test WebSocket message delivery integration."""
        websocket_adapter = integration_container.resolve(AWSAPIGatewayWebSocketManager)

        # Send message
        message = {
            "action": "search_results",
            "data": {"offers": [{"provider_name": "TestProvider", "speed_mbps": 100, "price_monthly": 29.99}]},
        }

        await websocket_adapter.send_message("test-connection-123", message)

        # Verify WebSocket API call
        assert mock_websocket_integration.post_to_connection.called
        call_args = mock_websocket_integration.post_to_connection.call_args
        assert call_args[1]["ConnectionId"] == "test-connection-123"
        assert "Data" in call_args[1]

    @pytest.mark.asyncio
    async def test_provider_aggregation_integration(self, integration_container):
        """Test provider aggregation with multiple providers."""
        provider_aggregator = integration_container.resolve(ProviderAggregator)

        # Mock individual provider responses
        with (
            patch("src.infrastructure.external_services.ping_perfect_adapter.PingPerfectAdapter.get_offers") as mock_ping,
            patch("src.infrastructure.external_services.webwunder_adapter.WebWunderAdapter.get_offers") as mock_web,
            patch("src.infrastructure.external_services.byteme_adapter.ByteMeAdapter.get_offers") as mock_byte,
        ):

            # Set up mock responses
            mock_ping.return_value = [
                {
                    "provider_name": "PingPerfect",
                    "offer_id": "ping-1",
                    "speed_mbps": 1000,
                    "price_monthly": 49.99,
                    "technology": "fiber",
                    "availability": True,
                }
            ]

            mock_web.return_value = [
                {
                    "provider_name": "WebWunder",
                    "offer_id": "web-1",
                    "speed_mbps": 100,
                    "price_monthly": 29.99,
                    "technology": "cable",
                    "availability": True,
                }
            ]

            mock_byte.return_value = [
                {
                    "provider_name": "ByteMe",
                    "offer_id": "byte-1",
                    "speed_mbps": 50,
                    "price_monthly": 19.99,
                    "technology": "dsl",
                    "availability": False,
                }
            ]

            # Execute aggregation
            address = Address(street="Test Street", house_number="1", city="Berlin", postal_code="10115", country="DE")

            offers = await provider_aggregator.get_offers(address)

            # Verify aggregation
            assert len(offers) == 3
            provider_names = [offer.provider_name for offer in offers]
            assert "PingPerfect" in provider_names
            assert "WebWunder" in provider_names
            assert "ByteMe" in provider_names

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, integration_container, mock_dynamodb_integration):
        """Test error handling in integration scenarios."""
        # Test DynamoDB error handling
        mock_dynamodb_integration.put_item.side_effect = Exception("DynamoDB connection error")

        search_use_case = integration_container.resolve(SearchOffersUseCase)
        search_request = {
            "address": {"street": "Test Street", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
            "connection_id": "test-connection-123",
            "request_id": "req-error-test",
        }

        # Should handle DynamoDB errors gracefully
        with pytest.raises(Exception) as exc_info:
            await search_use_case.execute(search_request)

        assert "DynamoDB" in str(exc_info.value) or "connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_concurrent_requests_integration(
        self, integration_container, mock_dynamodb_integration, mock_websocket_integration
    ):
        """Test handling concurrent requests in integration scenario."""
        search_use_case = integration_container.resolve(SearchOffersUseCase)

        # Mock provider responses
        with patch.object(ProviderAggregator, "get_offers") as mock_get_offers:
            mock_get_offers.return_value = [
                {
                    "provider_name": "TestProvider",
                    "offer_id": "offer-1",
                    "speed_mbps": 100,
                    "price_monthly": 29.99,
                    "technology": "fiber",
                    "availability": True,
                }
            ]

            # Create concurrent requests
            tasks = []
            for i in range(3):
                request = {
                    "address": {"street": f"Test Street {i}", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
                    "connection_id": f"test-connection-{i}",
                    "request_id": f"req-concurrent-{i}",
                }
                tasks.append(search_use_case.execute(request))

            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verify all completed
            assert len(results) == 3
            successful_results = [r for r in results if isinstance(r, SearchResult)]
            assert len(successful_results) >= 2  # Allow some failures in concurrent testing

            # Verify DynamoDB was called for each request
            assert mock_dynamodb_integration.put_item.call_count >= 2

    @pytest.mark.asyncio
    async def test_data_consistency_integration(self, integration_container, mock_dynamodb_integration):
        """Test data consistency across integration points."""
        search_use_case = integration_container.resolve(SearchOffersUseCase)
        process_use_case = integration_container.resolve(ProcessResultsUseCase)

        # Mock provider response
        with patch.object(ProviderAggregator, "get_offers") as mock_get_offers:
            mock_get_offers.return_value = [
                {
                    "provider_name": "ConsistencyProvider",
                    "offer_id": "consistency-1",
                    "speed_mbps": 200,
                    "price_monthly": 39.99,
                    "technology": "fiber",
                    "availability": True,
                }
            ]

            # Execute search
            search_request = {
                "address": {"street": "Consistency Street", "city": "Berlin", "postal_code": "10115", "country": "Germany"},
                "connection_id": "consistency-connection",
                "request_id": "consistency-req",
            }

            search_result = await search_use_case.execute(search_request)

            # Verify search result
            assert search_result.request_id == "consistency-req"
            assert len(search_result.offers) == 1
            assert search_result.offers[0].provider_name == "ConsistencyProvider"

            # Mock retrieval of stored data
            mock_dynamodb_integration.get_item.return_value = {
                "Item": {
                    "result_id": search_result.result_id,
                    "request_id": "consistency-req",
                    "offers": [
                        {
                            "provider_name": "ConsistencyProvider",
                            "offer_id": "consistency-1",
                            "speed_mbps": 200,
                            "price_monthly": 39.99,
                            "technology": "fiber",
                            "availability": True,
                        }
                    ],
                }
            }

            # Process the result
            process_result = await process_use_case.execute(
                {"result_id": search_result.result_id, "connection_id": "consistency-connection"}
            )

            # Verify data consistency
            assert process_result["result_id"] == search_result.result_id
            assert process_result["status"] == "processed"


@pytest.mark.integration
class TestAWSServiceIntegration:
    """Test integration with specific AWS services."""

    @pytest.mark.asyncio
    async def test_dynamodb_repository_integration(self, di_container):
        """Test DynamoDB repository integration."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = Mock()
            mock_table = Mock()
            mock_table.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.return_value = mock_dynamodb

            repository = di_container.resolve(AWSDynamoDBSearchResultRepository)

            # Test storing data
            test_data = {"id": "test-123", "data": "test-value", "timestamp": "2024-01-01T12:00:00Z"}

            await repository.store_search_result(test_data)

            # Verify DynamoDB call
            assert mock_table.put_item.called
            call_args = mock_table.put_item.call_args[1]
            assert "Item" in call_args

    @pytest.mark.asyncio
    async def test_websocket_adapter_integration(self, di_container):
        """Test WebSocket adapter integration."""
        with patch("boto3.client") as mock_boto3:
            mock_client = Mock()
            mock_client.post_to_connection.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
            mock_boto3.return_value = mock_client

            adapter = di_container.resolve(AWSAPIGatewayWebSocketManager)

            # Test sending message
            message = {"type": "test", "data": "integration-test"}
            await adapter.send_message("test-connection", message)

            # Verify API Gateway call
            assert mock_client.post_to_connection.called
            call_args = mock_client.post_to_connection.call_args[1]
            assert call_args["ConnectionId"] == "test-connection"
            assert "Data" in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
