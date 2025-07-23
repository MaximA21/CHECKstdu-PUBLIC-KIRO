"""End-to-end tests for complete application workflows."""

import pytest
import pytest_asyncio
import asyncio
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.lambda_handlers.search_handler import SearchHandler
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
from src.presentation.lambda_handlers.connect_handler import ConnectHandler
from src.presentation.lambda_handlers.disconnect_handler import DisconnectHandler
from src.presentation.lambda_handlers.results_handler import ResultsHandler


class TestCompleteWorkflows:
    """End-to-end tests for complete application workflows."""
    
    @pytest.fixture
    def mock_lambda_context(self):
        """Create a mock AWS Lambda context."""
        context = MagicMock()
        context.function_name = "e2e-test-function"
        context.function_version = "$LATEST"
        context.memory_limit_in_mb = "512"
        context.remaining_time_in_millis = lambda: 30000
        context.aws_request_id = f"e2e-request-{datetime.now().timestamp()}"
        context.log_group_name = "/aws/lambda/e2e-test-function"
        context.log_stream_name = f"2023/01/01/[$LATEST]e2e-stream-{datetime.now().timestamp()}"
        return context
    
    @pytest.fixture
    def test_environment(self):
        """Set up test environment variables."""
        return {
            'ENVIRONMENT': 'test',
            'USE_MOCK_SERVICES': 'true',
            'AWS_REGION': 'us-east-1',
            'LOG_LEVEL': 'DEBUG'
        }
    
    @pytest.fixture
    def websocket_connect_event(self):
        """Create a WebSocket connect event."""
        return {
            'requestContext': {
                'connectionId': 'e2e-connection-123',
                'eventType': 'CONNECT',
                'requestId': 'e2e-connect-request',
                'stage': 'test',
                'identity': {
                    'sourceIp': '127.0.0.1'
                }
            },
            'headers': {
                'Host': 'test-api.execute-api.us-east-1.amazonaws.com',
                'User-Agent': 'E2E-Test-Client'
            }
        }
    
    @pytest.fixture
    def websocket_disconnect_event(self):
        """Create a WebSocket disconnect event."""
        return {
            'requestContext': {
                'connectionId': 'e2e-connection-123',
                'eventType': 'DISCONNECT',
                'requestId': 'e2e-disconnect-request',
                'stage': 'test'
            }
        }
    
    @pytest.fixture
    def search_event(self):
        """Create a search request event."""
        return {
            'body': json.dumps({
                'address': {
                    'street': 'E2E Test Street',
                    'house_number': '42',
                    'city': 'Berlin',
                    'postal_code': '10115',
                    'country': 'DE'
                },
                'connection_id': 'e2e-connection-123'
            }),
            'httpMethod': 'POST',
            'path': '/search',
            'headers': {
                'Content-Type': 'application/json',
                'User-Agent': 'E2E-Test-Client'
            },
            'requestContext': {
                'requestId': 'e2e-search-request',
                'identity': {
                    'sourceIp': '127.0.0.1'
                }
            }
        }
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_websocket_search_workflow(
        self, 
        test_environment, 
        websocket_connect_event, 
        websocket_disconnect_event,
        search_event,
        mock_lambda_context
    ):
        """Test complete WebSocket search workflow from connect to disconnect."""
        
        with patch.dict('os.environ', test_environment):
            # Initialize handlers with DI container
            container = get_container()
            
            connect_handler = ConnectHandler(container)
            search_handler = SearchHandler(container)
            results_handler = ResultsHandler(container)
            disconnect_handler = DisconnectHandler(container)
            
            # Step 1: WebSocket Connect
            connect_response = await connect_handler.handle(websocket_connect_event, mock_lambda_context)
            
            assert connect_response['statusCode'] == 200
            connect_body = json.loads(connect_response['body'])
            assert connect_body['status'] == 'connected'
            assert connect_body['connection_id'] == 'e2e-connection-123'
            
            # Step 2: Initiate Search
            search_response = await search_handler.handle(search_event, mock_lambda_context)
            
            assert search_response['statusCode'] == 200
            search_body = json.loads(search_response['body'])
            assert search_body['status'] == 'initiated'
            assert 'request_id' in search_body
            assert 'share_token' in search_body
            
            request_id = search_body['request_id']
            share_token = search_body['share_token']
            
            # Step 3: Process Results (simulate provider responses)
            results_event = {
                'Records': [{
                    'body': json.dumps({
                        'request_id': request_id,
                        'connection_id': 'e2e-connection-123',
                        'provider_name': 'E2ETestProvider',
                        'status': 'success',
                        'raw_response': {
                            'offers': [
                                {
                                    'product_id': 'E2E-001',
                                    'speed_download': 100,
                                    'speed_upload': 50,
                                    'monthly_cost': 39.99,
                                    'connection_type': 'fiber'
                                }
                            ]
                        },
                        'share_token': share_token,
                        'address_data': {
                            'street': 'E2E Test Street',
                            'house_number': '42',
                            'city': 'Berlin',
                            'postal_code': '10115',
                            'country': 'DE'
                        }
                    })
                }]
            }
            
            results_response = await results_handler.handle(results_event, mock_lambda_context)
            
            assert results_response['statusCode'] == 200
            results_body = json.loads(results_response['body'])
            assert results_body['processed_records'] == 1
            assert results_body['successful_records'] == 1
            
            # Step 4: WebSocket Disconnect
            disconnect_response = await disconnect_handler.handle(websocket_disconnect_event, mock_lambda_context)
            
            assert disconnect_response['statusCode'] == 200
            disconnect_body = json.loads(disconnect_response['body'])
            assert disconnect_body['status'] == 'disconnected'
            assert disconnect_body['connection_id'] == 'e2e-connection-123'
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_http_search_and_share_workflow(
        self,
        test_environment,
        search_event,
        mock_lambda_context
    ):
        """Test complete HTTP search and share workflow."""
        
        with patch.dict('os.environ', test_environment):
            # Initialize handlers
            container = get_container()
            search_handler = SearchHandler(container)
            share_handler = ShareApiHandler(container)
            
            # Step 1: HTTP Search Request
            search_response = await search_handler.handle(search_event, mock_lambda_context)
            
            assert search_response['statusCode'] == 200
            search_body = json.loads(search_response['body'])
            assert search_body['status'] == 'initiated'
            assert 'share_token' in search_body
            
            share_token = search_body['share_token']
            
            # Step 2: Share Results Request
            share_event = {
                'pathParameters': {
                    'share_token': share_token
                },
                'httpMethod': 'GET',
                'path': f'/share/{share_token}',
                'headers': {
                    'Accept': 'application/json'
                },
                'requestContext': {
                    'requestId': 'e2e-share-request'
                }
            }
            
            share_response = await share_handler.handle(share_event, mock_lambda_context)
            
            assert share_response['statusCode'] == 200
            share_body = json.loads(share_response['body'])
            assert share_body['share_token'] == share_token
            assert 'offers' in share_body
            assert 'total_offers' in share_body
            assert isinstance(share_body['offers'], list)
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_concurrent_user_workflows(
        self,
        test_environment,
        mock_lambda_context
    ):
        """Test multiple concurrent user workflows."""
        
        with patch.dict('os.environ', test_environment):
            container = get_container()
            
            # Create multiple concurrent workflows
            num_users = 5
            workflows = []
            
            for i in range(num_users):
                workflow = self._create_user_workflow(
                    container,
                    user_id=f"user-{i}",
                    connection_id=f"conn-{i}",
                    mock_lambda_context=mock_lambda_context
                )
                workflows.append(workflow)
            
            # Execute all workflows concurrently
            results = await asyncio.gather(*workflows, return_exceptions=True)
            
            # Verify all workflows completed successfully
            successful_workflows = 0
            for result in results:
                if isinstance(result, dict) and result.get('status') == 'completed':
                    successful_workflows += 1
                elif isinstance(result, Exception):
                    print(f"Workflow failed with exception: {result}")
            
            assert successful_workflows == num_users
    
    async def _create_user_workflow(self, container, user_id, connection_id, mock_lambda_context):
        """Create a complete user workflow for concurrent testing."""
        try:
            # Initialize handlers
            connect_handler = ConnectHandler(container)
            search_handler = SearchHandler(container)
            share_handler = ShareApiHandler(container)
            disconnect_handler = DisconnectHandler(container)
            
            # Connect
            connect_event = {
                'requestContext': {
                    'connectionId': connection_id,
                    'eventType': 'CONNECT',
                    'requestId': f'{user_id}-connect'
                }
            }
            
            connect_response = await connect_handler.handle(connect_event, mock_lambda_context)
            if connect_response['statusCode'] != 200:
                return {'status': 'failed', 'step': 'connect', 'user_id': user_id}
            
            # Search
            search_event = {
                'body': json.dumps({
                    'address': {
                        'street': f'{user_id} Street',
                        'house_number': str(42 + int(user_id.split('-')[1])),
                        'city': 'Berlin',
                        'postal_code': '10115',
                        'country': 'DE'
                    },
                    'connection_id': connection_id
                }),
                'httpMethod': 'POST',
                'path': '/search'
            }
            
            search_response = await search_handler.handle(search_event, mock_lambda_context)
            if search_response['statusCode'] != 200:
                return {'status': 'failed', 'step': 'search', 'user_id': user_id}
            
            search_body = json.loads(search_response['body'])
            share_token = search_body['share_token']
            
            # Share
            share_event = {
                'pathParameters': {'share_token': share_token},
                'httpMethod': 'GET',
                'path': f'/share/{share_token}'
            }
            
            share_response = await share_handler.handle(share_event, mock_lambda_context)
            if share_response['statusCode'] != 200:
                return {'status': 'failed', 'step': 'share', 'user_id': user_id}
            
            # Disconnect
            disconnect_event = {
                'requestContext': {
                    'connectionId': connection_id,
                    'eventType': 'DISCONNECT',
                    'requestId': f'{user_id}-disconnect'
                }
            }
            
            disconnect_response = await disconnect_handler.handle(disconnect_event, mock_lambda_context)
            if disconnect_response['statusCode'] != 200:
                return {'status': 'failed', 'step': 'disconnect', 'user_id': user_id}
            
            return {
                'status': 'completed',
                'user_id': user_id,
                'share_token': share_token
            }
            
        except Exception as e:
            return {'status': 'failed', 'error': str(e), 'user_id': user_id}
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_error_recovery_workflow(
        self,
        test_environment,
        mock_lambda_context
    ):
        """Test error recovery in complete workflows."""
        
        with patch.dict('os.environ', test_environment):
            container = get_container()
            search_handler = SearchHandler(container)
            share_handler = ShareApiHandler(container)
            
            # Test 1: Invalid search request
            invalid_search_event = {
                'body': json.dumps({
                    'invalid_field': 'invalid_value'
                }),
                'httpMethod': 'POST',
                'path': '/search'
            }
            
            search_response = await search_handler.handle(invalid_search_event, mock_lambda_context)
            assert search_response['statusCode'] == 400
            
            # Test 2: Invalid share token
            invalid_share_event = {
                'pathParameters': {'share_token': 'invalid-token'},
                'httpMethod': 'GET',
                'path': '/share/invalid-token'
            }
            
            share_response = await share_handler.handle(invalid_share_event, mock_lambda_context)
            assert share_response['statusCode'] == 404
            
            # Test 3: Valid workflow after errors
            valid_search_event = {
                'body': json.dumps({
                    'address': {
                        'street': 'Recovery Test Street',
                        'house_number': '1',
                        'city': 'Berlin',
                        'postal_code': '10115',
                        'country': 'DE'
                    },
                    'connection_id': 'recovery-connection'
                }),
                'httpMethod': 'POST',
                'path': '/search'
            }
            
            recovery_response = await search_handler.handle(valid_search_event, mock_lambda_context)
            assert recovery_response['statusCode'] == 200
            
            recovery_body = json.loads(recovery_response['body'])
            assert recovery_body['status'] == 'initiated'
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_performance_under_load(
        self,
        test_environment,
        mock_lambda_context
    ):
        """Test system performance under load."""
        
        with patch.dict('os.environ', test_environment):
            container = get_container()
            search_handler = SearchHandler(container)
            
            # Create load test events
            load_events = []
            for i in range(20):  # 20 concurrent requests
                event = {
                    'body': json.dumps({
                        'address': {
                            'street': f'Load Test Street {i}',
                            'house_number': str(i),
                            'city': 'Berlin',
                            'postal_code': '10115',
                            'country': 'DE'
                        },
                        'connection_id': f'load-conn-{i}'
                    }),
                    'httpMethod': 'POST',
                    'path': '/search'
                }
                load_events.append(event)
            
            # Execute load test
            start_time = asyncio.get_event_loop().time()
            
            tasks = [
                search_handler.handle(event, mock_lambda_context)
                for event in load_events
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time
            
            # Analyze results
            successful_responses = 0
            failed_responses = 0
            
            for response in responses:
                if isinstance(response, dict) and response.get('statusCode') == 200:
                    successful_responses += 1
                else:
                    failed_responses += 1
            
            # Performance assertions
            assert successful_responses >= 18  # At least 90% success rate
            assert total_time < 10.0  # Should complete within 10 seconds
            
            throughput = len(load_events) / total_time
            assert throughput >= 2.0  # At least 2 requests per second
            
            print(f"Load test results:")
            print(f"  Total requests: {len(load_events)}")
            print(f"  Successful: {successful_responses}")
            print(f"  Failed: {failed_responses}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Throughput: {throughput:.2f} req/s")
    
    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_data_consistency_across_handlers(
        self,
        test_environment,
        mock_lambda_context
    ):
        """Test data consistency across different handlers."""
        
        with patch.dict('os.environ', test_environment):
            container = get_container()
            
            search_handler = SearchHandler(container)
            share_handler = ShareApiHandler(container)
            results_handler = ResultsHandler(container)
            
            # Step 1: Create search
            search_event = {
                'body': json.dumps({
                    'address': {
                        'street': 'Consistency Test Street',
                        'house_number': '99',
                        'city': 'Berlin',
                        'postal_code': '10115',
                        'country': 'DE'
                    },
                    'connection_id': 'consistency-conn'
                }),
                'httpMethod': 'POST',
                'path': '/search'
            }
            
            search_response = await search_handler.handle(search_event, mock_lambda_context)
            search_body = json.loads(search_response['body'])
            
            request_id = search_body['request_id']
            share_token = search_body['share_token']
            
            # Step 2: Process results
            results_event = {
                'Records': [{
                    'body': json.dumps({
                        'request_id': request_id,
                        'connection_id': 'consistency-conn',
                        'provider_name': 'ConsistencyProvider',
                        'status': 'success',
                        'raw_response': {
                            'offers': [{
                                'product_id': 'CONSISTENCY-001',
                                'speed_download': 200,
                                'speed_upload': 100,
                                'monthly_cost': 49.99
                            }]
                        },
                        'share_token': share_token,
                        'address_data': {
                            'street': 'Consistency Test Street',
                            'house_number': '99',
                            'city': 'Berlin',
                            'postal_code': '10115',
                            'country': 'DE'
                        }
                    })
                }]
            }
            
            results_response = await results_handler.handle(results_event, mock_lambda_context)
            results_body = json.loads(results_response['body'])
            
            assert results_body['successful_records'] == 1
            
            # Step 3: Verify data consistency in share
            share_event = {
                'pathParameters': {'share_token': share_token},
                'httpMethod': 'GET',
                'path': f'/share/{share_token}'
            }
            
            share_response = await share_handler.handle(share_event, mock_lambda_context)
            share_body = json.loads(share_response['body'])
            
            # Verify data consistency
            assert share_body['share_token'] == share_token
            assert len(share_body['offers']) > 0
            
            # Check that the offer data matches what was processed
            found_offer = False
            for offer in share_body['offers']:
                if offer['product_id'] == 'CONSISTENCY-001':
                    found_offer = True
                    assert offer['speed_download_mbps'] == 200
                    assert offer['speed_upload_mbps'] == 100
                    break
            
            assert found_offer, "Processed offer not found in share results"


if __name__ == "__main__":
    pytest.main([__file__])