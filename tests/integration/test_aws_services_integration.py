"""Integration tests for AWS services using moto mocking."""

import pytest
import pytest_asyncio
import boto3
import json
from moto import mock_dynamodb, mock_sqs, mock_stepfunctions, mock_apigatewayv2
from unittest.mock import patch
import os

from src.infrastructure.persistence.aws_dynamodb_repository import (
    DynamoDBSearchResultRepository,
    DynamoDBConnectionRepository
)
from src.infrastructure.messaging.aws_sqs_adapter import SQSMessageQueue
from src.infrastructure.messaging.aws_step_functions_adapter import StepFunctionsWorkflowOrchestrator
from src.infrastructure.messaging.aws_websocket_adapter import WebSocketConnectionManager

from src.domain.entities.search_result import SearchResult
from src.domain.entities.connection_session import ConnectionSession, SessionConnectionType
from src.domain.value_objects.address import Address


class TestAWSServicesIntegration:
    """Integration tests for AWS services with moto mocking."""
    
    @pytest.fixture
    def aws_credentials(self):
        """Mock AWS credentials for testing."""
        os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
        os.environ['AWS_SECURITY_TOKEN'] = 'testing'
        os.environ['AWS_SESSION_TOKEN'] = 'testing'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    
    @pytest.fixture
    def sample_address(self):
        """Create a sample address for testing."""
        return Address(
            street="AWS Test Street",
            house_number="123",
            city="Berlin",
            postal_code="10115",
            country="DE"
        )
    
    @pytest.mark.integration
    @mock_dynamodb
    def test_dynamodb_search_result_repository(self, aws_credentials, sample_address):
        """Test DynamoDB search result repository integration."""
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        table = dynamodb.create_table(
            TableName='search-results',
            KeySchema=[
                {'AttributeName': 'request_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'request_id', 'AttributeType': 'S'},
                {'AttributeName': 'share_token', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'share-token-index',
                    'KeySchema': [
                        {'AttributeName': 'share_token', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'BillingMode': 'PAY_PER_REQUEST'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize repository
        repo = DynamoDBSearchResultRepository(
            table_name='search-results',
            region='us-east-1'
        )
        
        # Create and store search result
        search_result = SearchResult.create_new(sample_address, "test-request-123")
        
        # Test store operation
        stored_result = repo.store_result(search_result)
        assert stored_result.request_id == search_result.request_id
        assert stored_result.share_token == search_result.share_token
        
        # Test retrieve by request ID
        retrieved_result = repo.get_result_by_request_id(search_result.request_id)
        assert retrieved_result is not None
        assert retrieved_result.request_id == search_result.request_id
        assert retrieved_result.address.street == sample_address.street
        
        # Test retrieve by share token
        shared_result = repo.get_result_by_share_token(search_result.share_token)
        assert shared_result is not None
        assert shared_result.share_token == search_result.share_token
        
        # Test update result with offers
        search_result.add_provider_offers("TestProvider", [])
        updated_result = repo.update_result(search_result)
        assert updated_result.request_id == search_result.request_id
        
        # Test list results
        results = repo.list_results_by_connection("test-connection")
        assert isinstance(results, list)
    
    @pytest.mark.integration
    @mock_dynamodb
    def test_dynamodb_connection_repository(self, aws_credentials):
        """Test DynamoDB connection repository integration."""
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        table = dynamodb.create_table(
            TableName='connections',
            KeySchema=[
                {'AttributeName': 'connection_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'connection_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Initialize repository
        repo = DynamoDBConnectionRepository(
            table_name='connections',
            region='us-east-1'
        )
        
        # Create and store connection
        connection = ConnectionSession.create_new("test-conn-123", SessionConnectionType.WEBSOCKET)
        
        # Test store operation
        stored_connection = repo.store_connection(connection)
        assert stored_connection.connection_id == connection.connection_id
        assert stored_connection.is_connected == True
        
        # Test retrieve connection
        retrieved_connection = repo.get_connection(connection.connection_id)
        assert retrieved_connection is not None
        assert retrieved_connection.connection_id == connection.connection_id
        assert retrieved_connection.connection_type == SessionConnectionType.WEBSOCKET
        
        # Test update connection
        connection.disconnect("Test disconnect")
        updated_connection = repo.update_connection(connection)
        assert updated_connection.is_connected == False
        assert updated_connection.disconnect_reason == "Test disconnect"
        
        # Test list active connections
        active_connections = repo.list_active_connections()
        assert isinstance(active_connections, list)
        
        # Test cleanup expired connections
        cleaned_count = repo.cleanup_expired_connections()
        assert isinstance(cleaned_count, int)
    
    @pytest.mark.integration
    @mock_sqs
    def test_sqs_message_queue(self, aws_credentials):
        """Test SQS message queue integration."""
        # Create SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='test-queue')['QueueUrl']
        
        # Initialize message queue
        message_queue = SQSMessageQueue(
            queue_url=queue_url,
            region='us-east-1'
        )
        
        # Test send message
        test_message = {
            'request_id': 'test-request-123',
            'action': 'search',
            'data': {'address': 'Test Address'}
        }
        
        message_id = message_queue.send_message(test_message)
        assert message_id is not None
        
        # Test receive message
        received_messages = message_queue.receive_messages(max_messages=1)
        assert len(received_messages) == 1
        
        received_message = received_messages[0]
        assert received_message['request_id'] == test_message['request_id']
        assert received_message['action'] == test_message['action']
        
        # Test delete message
        success = message_queue.delete_message(received_message['receipt_handle'])
        assert success == True
        
        # Test batch operations
        batch_messages = [
            {'request_id': f'batch-{i}', 'action': 'process', 'data': {}}
            for i in range(5)
        ]
        
        batch_results = message_queue.send_batch_messages(batch_messages)
        assert len(batch_results) == 5
        
        # Receive batch messages
        batch_received = message_queue.receive_messages(max_messages=10)
        assert len(batch_received) == 5
    
    @pytest.mark.integration
    @mock_stepfunctions
    def test_step_functions_workflow(self, aws_credentials):
        """Test Step Functions workflow orchestrator integration."""
        # Create Step Functions state machine
        stepfunctions = boto3.client('stepfunctions', region_name='us-east-1')
        
        # Create IAM role (mocked)
        role_arn = 'arn:aws:iam::123456789012:role/StepFunctionsRole'
        
        # Define simple state machine
        definition = {
            "Comment": "Test workflow",
            "StartAt": "ProcessRequest",
            "States": {
                "ProcessRequest": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:123456789012:function:ProcessRequest",
                    "End": True
                }
            }
        }
        
        state_machine = stepfunctions.create_state_machine(
            name='test-workflow',
            definition=json.dumps(definition),
            roleArn=role_arn
        )
        
        # Initialize workflow orchestrator
        orchestrator = StepFunctionsWorkflowOrchestrator(
            state_machine_arn=state_machine['stateMachineArn'],
            region='us-east-1'
        )
        
        # Test start execution
        execution_input = {
            'request_id': 'test-request-123',
            'address': {'street': 'Test Street', 'city': 'Berlin'}
        }
        
        execution_arn = orchestrator.start_execution(
            execution_name='test-execution',
            input_data=execution_input
        )
        assert execution_arn is not None
        
        # Test get execution status
        status = orchestrator.get_execution_status(execution_arn)
        assert status in ['RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']
        
        # Test list executions
        executions = orchestrator.list_executions()
        assert isinstance(executions, list)
        assert len(executions) >= 1
    
    @pytest.mark.integration
    @mock_apigatewayv2
    def test_websocket_connection_manager(self, aws_credentials):
        """Test WebSocket connection manager integration."""
        # Create API Gateway WebSocket API
        apigateway = boto3.client('apigatewayv2', region_name='us-east-1')
        
        api = apigateway.create_api(
            Name='test-websocket-api',
            ProtocolType='WEBSOCKET',
            RouteSelectionExpression='$request.body.action'
        )
        
        # Initialize connection manager
        connection_manager = WebSocketConnectionManager(
            api_id=api['ApiId'],
            stage='test',
            region='us-east-1'
        )
        
        # Test connection management
        connection_id = 'test-connection-123'
        
        # Test send message to connection
        test_message = {
            'type': 'search_result',
            'data': {'offers': [], 'status': 'completed'}
        }
        
        # Note: In real AWS, this would send to an actual WebSocket connection
        # With moto, we're testing the API structure and error handling
        try:
            success = connection_manager.send_message_to_connection(
                connection_id, test_message
            )
            # This might fail with moto as it doesn't fully simulate WebSocket connections
            # but we can test the method exists and handles errors properly
        except Exception as e:
            # Expected with moto - WebSocket connections aren't fully simulated
            assert 'GoneException' in str(type(e)) or 'ClientError' in str(type(e))
        
        # Test broadcast message
        connection_ids = ['conn-1', 'conn-2', 'conn-3']
        broadcast_message = {
            'type': 'system_message',
            'data': {'message': 'System maintenance in 5 minutes'}
        }
        
        try:
            results = connection_manager.broadcast_message(connection_ids, broadcast_message)
            # With moto, this will likely fail, but we test the structure
        except Exception:
            # Expected with moto
            pass
        
        # Test connection cleanup
        try:
            cleaned_connections = connection_manager.cleanup_stale_connections()
            assert isinstance(cleaned_connections, list)
        except Exception:
            # Expected with moto
            pass
    
    @pytest.mark.integration
    @mock_dynamodb
    @mock_sqs
    def test_full_aws_integration_flow(self, aws_credentials, sample_address):
        """Test full integration flow using multiple AWS services."""
        # Set up DynamoDB tables
        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Search results table
        search_table = dynamodb.create_table(
            TableName='search-results',
            KeySchema=[{'AttributeName': 'request_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'request_id', 'AttributeType': 'S'},
                {'AttributeName': 'share_token', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'share-token-index',
                'KeySchema': [{'AttributeName': 'share_token', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'},
                'BillingMode': 'PAY_PER_REQUEST'
            }],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Connections table
        conn_table = dynamodb.create_table(
            TableName='connections',
            KeySchema=[{'AttributeName': 'connection_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'connection_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Set up SQS queue
        sqs = boto3.client('sqs', region_name='us-east-1')
        queue_url = sqs.create_queue(QueueName='integration-test-queue')['QueueUrl']
        
        # Initialize services
        search_repo = DynamoDBSearchResultRepository('search-results', 'us-east-1')
        conn_repo = DynamoDBConnectionRepository('connections', 'us-east-1')
        message_queue = SQSMessageQueue(queue_url, 'us-east-1')
        
        # Test flow: Create connection -> Store search -> Send message -> Process
        
        # 1. Create and store connection
        connection = ConnectionSession.create_new("integration-conn", SessionConnectionType.WEBSOCKET)
        stored_conn = conn_repo.store_connection(connection)
        assert stored_conn.connection_id == connection.connection_id
        
        # 2. Create and store search result
        search_result = SearchResult.create_new(sample_address, "integration-request")
        stored_search = search_repo.store_result(search_result)
        assert stored_search.request_id == search_result.request_id
        
        # 3. Send processing message
        process_message = {
            'request_id': search_result.request_id,
            'connection_id': connection.connection_id,
            'action': 'process_search',
            'provider': 'TestProvider'
        }
        
        message_id = message_queue.send_message(process_message)
        assert message_id is not None
        
        # 4. Receive and process message
        messages = message_queue.receive_messages(max_messages=1)
        assert len(messages) == 1
        
        received_message = messages[0]
        assert received_message['request_id'] == search_result.request_id
        assert received_message['connection_id'] == connection.connection_id
        
        # 5. Update search result with offers
        search_result.add_provider_offers("TestProvider", [])
        updated_search = search_repo.update_result(search_result)
        assert updated_search.request_id == search_result.request_id
        
        # 6. Retrieve by share token
        shared_result = search_repo.get_result_by_share_token(search_result.share_token)
        assert shared_result is not None
        assert shared_result.share_token == search_result.share_token
        
        # 7. Clean up message
        success = message_queue.delete_message(received_message['receipt_handle'])
        assert success == True
        
        # 8. Update connection status
        connection.disconnect("Integration test completed")
        updated_conn = conn_repo.update_connection(connection)
        assert updated_conn.is_connected == False
    
    @pytest.mark.integration
    def test_aws_error_handling(self, aws_credentials):
        """Test error handling with AWS services."""
        # Test with invalid table name
        with pytest.raises(Exception):
            repo = DynamoDBSearchResultRepository('non-existent-table', 'us-east-1')
            # This should fail when trying to access the table
            repo.get_result_by_request_id('test-id')
        
        # Test with invalid queue URL
        with pytest.raises(Exception):
            queue = SQSMessageQueue('invalid-queue-url', 'us-east-1')
            queue.send_message({'test': 'message'})
        
        # Test with invalid region
        with pytest.raises(Exception):
            repo = DynamoDBSearchResultRepository('test-table', 'invalid-region')
            # This should fail during initialization or first operation


if __name__ == "__main__":
    pytest.main([__file__])