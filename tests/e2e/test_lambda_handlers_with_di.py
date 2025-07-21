"""End-to-end tests for Lambda handlers with dependency injection."""

import pytest
import pytest_asyncio
import json
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.presentation.lambda_handlers.search_handler import SearchHandler
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
from src.presentation.lambda_handlers.connect_handler import ConnectHandler
from src.presentation.lambda_handlers.requestor_handler import RequestorHandler
from src.presentation.lambda_handlers.results_handler import ResultsHandler

from src.shared.dependency_injection.container import DIContainer
from src.shared.dependency_injection.bootstrap import get_container


class TestLambdaHandlersE2E:
    """End-to-end tests for Lambda handlers using dependency injection."""
    
    @pytest.fixture
    def mock_lambda_context(self):
        """Create a mock Lambda context."""
        context = MagicMock()
        context.function_name = "test-function"
        context.function_version = "$LATEST"
        context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        context.memory_limit_in_mb = "128"
        context.remaining_time_in_millis = lambda: 30000
        context.aws_request_id = "test-request-id-123"
        context.log_group_name = "/aws/lambda/test-function"
        context.log_stream_name = "2023/01/01/[$LATEST]test-stream"
        return context
    
    @pytest_asyncio.fixture
    async def setup_test_environment(self):
        """Set up test environment with mock configuration."""
        # Set environment variables for testing
        test_env = {
            'ENVIRONMENT': 'test',
            'LOG_LEVEL': 'DEBUG',
            'USE_MOCK_SERVICES': 'true',
            'AWS_REGION': 'us-east-1'
        }
        
        with patch.dict(os.environ, test_env):
            # Initialize application with test configuration
            container = get_container()
            return container
    
    @pytest.mark.asyncio
    async def test_search_handler_e2e(self, setup_test_environment, mock_lambda_context):
        """Test search handler end-to-end with dependency injection."""
        container = setup_test_environment
        handler = SearchHandler(container)
        
        # Create test event
        event = {
            'body': json.dumps({
                'address': {
                    'street': 'Teststraße',
                    'house_number': '123',
                    'city': 'Berlin',
                    'postal_code': '10115',
                    'country': 'DE'
                },
                'connection_id': 'test-connection-123'
            }),
            'headers': {
                'Content-Type': 'application/json'
            },
            'httpMethod': 'POST',
            'path': '/search'
        }
        
        # Execute handler
        response = await handler.handle(event, mock_lambda_context)
        
        # Verify response structure
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['status'] == 'initiated'
        assert 'request_id' in body
        assert 'share_token' in body
        assert 'message' in body
        
        # Verify headers
        assert 'Content-Type' in response['headers']
        assert response['headers']['Content-Type'] == 'application/json'
    
    @pytest.mark.asyncio
    async def test_share_api_handler_e2e(self, setup_test_environment, mock_lambda_context):
        """Test share API handler end-to-end with dependency injection."""
        container = setup_test_environment
        handler = ShareApiHandler(container)
        
        # First, create a search result to share
        search_handler = SearchHandler(container)
        search_event = {
            'body': json.dumps({
                'address': {
                    'street': 'Musterstraße',
                    'house_number': '456',
                    'city': 'München',
                    'postal_code': '80331',
                    'country': 'DE'
                },
                'connection_id': 'test-connection-456'
            }),
            'httpMethod': 'POST',
            'path': '/search'
        }
        
        search_response = await search_handler.handle(search_event, mock_lambda_context)
        search_body = json.loads(search_response['body'])
        share_token = search_body['share_token']
        
        # Now test sharing the results
        share_event = {
            'pathParameters': {
                'share_token': share_token
            },
            'httpMethod': 'GET',
            'path': f'/share/{share_token}'
        }
        
        # Execute share handler
        response = await handler.handle(share_event, mock_lambda_context)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['share_token'] == share_token
        assert 'offers' in body
        assert 'metadata' in body
        assert 'total_offers' in body
        assert 'generated_at' in body
    
    @pytest.mark.asyncio
    async def test_connect_handler_e2e(self, setup_test_environment, mock_lambda_context):
        """Test WebSocket connect handler end-to-end with dependency injection."""
        container = setup_test_environment
        handler = ConnectHandler(container)
        
        # Create WebSocket connect event
        event = {
            'requestContext': {
                'connectionId': 'test-websocket-connection-123',
                'eventType': 'CONNECT',
                'requestTime': '2023-01-01T12:00:00.000Z',
                'requestTimeEpoch': 1672574400000,
                'apiId': 'test-api-id',
                'stage': 'test'
            },
            'headers': {
                'Host': 'test-api-id.execute-api.us-east-1.amazonaws.com',
                'User-Agent': 'test-client/1.0'
            }
        }
        
        # Execute handler
        response = await handler.handle(event, mock_lambda_context)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['status'] == 'connected'
        assert body['connection_id'] == 'test-websocket-connection-123'
        assert 'connected_at' in body
        assert 'message' in body
    
    @pytest.mark.asyncio
    async def test_requestor_handler_e2e(self, setup_test_environment, mock_lambda_context):
        """Test requestor handler end-to-end with dependency injection."""
        container = setup_test_environment
        handler = RequestorHandler(container)
        
        # Create SQS event with search request
        event = {
            'Records': [
                {
                    'messageId': 'test-message-123',
                    'receiptHandle': 'test-receipt-handle',
                    'body': json.dumps({
                        'request_id': 'test-request-123',
                        'address': {
                            'street': 'Beispielstraße',
                            'house_number': '789',
                            'city': 'Hamburg',
                            'postal_code': '20095',
                            'country': 'DE'
                        },
                        'connection_id': 'test-connection-789'
                    }),
                    'attributes': {
                        'ApproximateReceiveCount': '1',
                        'SentTimestamp': '1672574400000',
                        'SenderId': 'test-sender',
                        'ApproximateFirstReceiveTimestamp': '1672574400000'
                    },
                    'messageAttributes': {},
                    'md5OfBody': 'test-md5',
                    'eventSource': 'aws:sqs',
                    'eventSourceARN': 'arn:aws:sqs:us-east-1:123456789012:test-queue',
                    'awsRegion': 'us-east-1'
                }
            ]
        }
        
        # Execute handler
        response = await handler.handle(event, mock_lambda_context)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['processed_records'] == 1
        assert body['successful_records'] == 1
        assert body['failed_records'] == 0
    
    @pytest.mark.asyncio
    async def test_results_handler_e2e(self, setup_test_environment, mock_lambda_context):
        """Test results handler end-to-end with dependency injection."""
        container = setup_test_environment
        handler = ResultsHandler(container)
        
        # Create Step Functions event with provider results
        event = {
            'request_id': 'test-request-456',
            'address': {
                'street': 'Teststraße',
                'house_number': '123',
                'city': 'Berlin',
                'postal_code': '10115',
                'country': 'DE'
            },
            'connection_id': 'test-connection-456',
            'provider_results': [
                {
                    'provider_name': 'TestProvider1',
                    'status': 'success',
                    'offers': [
                        {
                            'product_id': 'TEST-001',
                            'speed_download_mbps': 100,
                            'speed_upload_mbps': 50,
                            'monthly_cost_euros': 29.99,
                            'connection_type': 'fiber',
                            'contract_duration_months': 24
                        }
                    ]
                },
                {
                    'provider_name': 'TestProvider2',
                    'status': 'success',
                    'offers': [
                        {
                            'product_id': 'TEST-002',
                            'speed_download_mbps': 50,
                            'speed_upload_mbps': 10,
                            'monthly_cost_euros': 19.99,
                            'connection_type': 'dsl',
                            'contract_duration_months': 12
                        }
                    ]
                }
            ]
        }
        
        # Execute handler
        response = await handler.handle(event, mock_lambda_context)
        
        # Verify response
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['status'] == 'completed'
        assert body['request_id'] == 'test-request-456'
        assert body['offers_found'] >= 2
        assert body['providers_processed'] == 2
    
    @pytest.mark.asyncio
    async def test_error_handling_e2e(self, setup_test_environment, mock_lambda_context):
        """Test error handling across Lambda handlers."""
        container = setup_test_environment
        
        # Test search handler with invalid input
        search_handler = SearchHandler(container)
        invalid_event = {
            'body': json.dumps({
                'invalid': 'data'
            }),
            'httpMethod': 'POST',
            'path': '/search'
        }
        
        response = await search_handler.handle(invalid_event, mock_lambda_context)
        assert response['statusCode'] == 400
        
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'validation_error'
        
        # Test share handler with invalid token
        share_handler = ShareApiHandler(container)
        invalid_share_event = {
            'pathParameters': {
                'share_token': 'invalid-token-123'
            },
            'httpMethod': 'GET',
            'path': '/share/invalid-token-123'
        }
        
        response = await share_handler.handle(invalid_share_event, mock_lambda_context)
        assert response['statusCode'] == 404
        
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error'] == 'not_found'
    
    @pytest.mark.asyncio
    async def test_dependency_injection_configuration(self, setup_test_environment):
        """Test that dependency injection is properly configured for Lambda handlers."""
        container = setup_test_environment
        
        # Verify that all required services are registered
        assert container.is_registered('ISearchResultRepository')
        assert container.is_registered('IConnectionRepository')
        assert container.is_registered('IMessageQueue')
        assert container.is_registered('IConnectionManager')
        assert container.is_registered('IProviderRegistry')
        assert container.is_registered('ILoggerFactory')
        
        # Verify that services can be resolved
        search_repo = container.resolve('ISearchResultRepository')
        assert search_repo is not None
        
        connection_repo = container.resolve('IConnectionRepository')
        assert connection_repo is not None
        
        message_queue = container.resolve('IMessageQueue')
        assert message_queue is not None
        
        logger_factory = container.resolve('ILoggerFactory')
        assert logger_factory is not None
    
    @pytest.mark.asyncio
    async def test_lambda_handler_performance(self, setup_test_environment, mock_lambda_context):
        """Test Lambda handler performance with dependency injection."""
        container = setup_test_environment
        handler = SearchHandler(container)
        
        # Create test event
        event = {
            'body': json.dumps({
                'address': {
                    'street': 'Performancestraße',
                    'house_number': '999',
                    'city': 'Frankfurt',
                    'postal_code': '60311',
                    'country': 'DE'
                },
                'connection_id': 'perf-test-connection'
            }),
            'httpMethod': 'POST',
            'path': '/search'
        }
        
        # Measure execution time
        start_time = datetime.now()
        
        # Execute multiple requests to test performance
        responses = []
        for i in range(10):
            response = await handler.handle(event, mock_lambda_context)
            responses.append(response)
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        avg_duration = total_duration / 10
        
        # Verify all requests succeeded
        for response in responses:
            assert response['statusCode'] == 200
        
        # Verify reasonable performance (should be fast with mocks)
        assert avg_duration < 1.0  # Less than 1 second per request on average
        
        print(f"Average request duration: {avg_duration:.3f} seconds")
        print(f"Total duration for 10 requests: {total_duration:.3f} seconds")
    
    @pytest.mark.asyncio
    async def test_lambda_cold_start_simulation(self, mock_lambda_context):
        """Test Lambda cold start behavior with dependency injection."""
        # Simulate cold start by creating new container
        test_env = {
            'ENVIRONMENT': 'test',
            'LOG_LEVEL': 'INFO',
            'USE_MOCK_SERVICES': 'true'
        }
        
        with patch.dict(os.environ, test_env):
            # Measure cold start time
            start_time = datetime.now()
            
            # Initialize application (cold start)
            container = get_container()
            handler = SearchHandler(container)
            
            cold_start_time = (datetime.now() - start_time).total_seconds()
            
            # Execute first request (part of cold start)
            event = {
                'body': json.dumps({
                    'address': {
                        'street': 'Coldstartstraße',
                        'house_number': '1',
                        'city': 'Berlin',
                        'postal_code': '10115',
                        'country': 'DE'
                    },
                    'connection_id': 'cold-start-test'
                }),
                'httpMethod': 'POST',
                'path': '/search'
            }
            
            first_request_start = datetime.now()
            response = await handler.handle(event, mock_lambda_context)
            first_request_time = (datetime.now() - first_request_start).total_seconds()
            
            # Execute second request (warm)
            warm_request_start = datetime.now()
            response2 = await handler.handle(event, mock_lambda_context)
            warm_request_time = (datetime.now() - warm_request_start).total_seconds()
            
            # Verify both requests succeeded
            assert response['statusCode'] == 200
            assert response2['statusCode'] == 200
            
            # Log performance metrics
            print(f"Cold start initialization time: {cold_start_time:.3f} seconds")
            print(f"First request time: {first_request_time:.3f} seconds")
            print(f"Warm request time: {warm_request_time:.3f} seconds")
            
            # Warm requests should be faster
            assert warm_request_time < first_request_time


if __name__ == "__main__":
    pytest.main([__file__])