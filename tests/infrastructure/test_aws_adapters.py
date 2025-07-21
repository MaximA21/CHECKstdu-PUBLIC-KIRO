"""Tests for AWS infrastructure adapters."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timedelta

from src.domain.entities.search_result import SearchResult
from src.domain.entities.connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType
from src.domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from src.domain.value_objects.address import Address

from src.infrastructure.persistence.aws_dynamodb_repository import (
    AWSDynamoDBSearchResultRepository,
    AWSDynamoDBConnectionRepository,
    DynamoDBTypeConverter
)
from src.infrastructure.messaging.aws_sqs_adapter import AWSSQSMessageQueue
from src.infrastructure.messaging.aws_step_functions_adapter import AWSStepFunctionsOrchestrator
from src.infrastructure.messaging.aws_websocket_adapter import AWSAPIGatewayWebSocketManager


class TestDynamoDBTypeConverter:
    """Test DynamoDB type converter utility."""
    
    def test_to_dynamodb_item_basic_types(self):
        """Test conversion of basic Python types to DynamoDB format."""
        # Test float to Decimal conversion
        result = DynamoDBTypeConverter.to_dynamodb_item(3.14)
        assert isinstance(result, Decimal)
        assert float(result) == 3.14
        
        # Test datetime to ISO string conversion
        dt = datetime(2023, 1, 1, 12, 0, 0)
        result = DynamoDBTypeConverter.to_dynamodb_item(dt)
        assert result == "2023-01-01T12:00:00"
        
        # Test dict conversion
        data = {"price": 29.99, "timestamp": dt}
        result = DynamoDBTypeConverter.to_dynamodb_item(data)
        assert isinstance(result["price"], Decimal)
        assert result["timestamp"] == "2023-01-01T12:00:00"
    
    def test_from_dynamodb_item_basic_types(self):
        """Test conversion from DynamoDB format to Python types."""
        # Test Decimal to float conversion
        result = DynamoDBTypeConverter.from_dynamodb_item(Decimal('3.14'))
        assert isinstance(result, float)
        assert result == 3.14
        
        # Test dict conversion
        data = {"price": Decimal('29.99'), "name": "Test"}
        result = DynamoDBTypeConverter.from_dynamodb_item(data)
        assert isinstance(result["price"], float)
        assert result["price"] == 29.99
        assert result["name"] == "Test"


class TestAWSDynamoDBSearchResultRepository:
    """Test AWS DynamoDB search result repository."""
    
    @pytest.fixture
    def mock_table(self):
        """Mock DynamoDB table."""
        with patch('boto3.resource') as mock_resource:
            mock_table = Mock()
            mock_resource.return_value.Table.return_value = mock_table
            yield mock_table
    
    @pytest.fixture
    def repository(self, mock_table):
        """Create repository instance with mocked table."""
        return AWSDynamoDBSearchResultRepository('test-table')
    
    @pytest.fixture
    def sample_search_result(self):
        """Create sample search result for testing."""
        address = Address(
            street="Teststraße",
            house_number="123",
            city="Berlin",
            postal_code="10115"
        )
        
        offer = ProviderOffer(
            provider_name="TestProvider",
            product_id="test-123",
            speed_download_mbps=100,
            speed_upload_mbps=10,
            monthly_cost_euros=Decimal('29.99'),
            connection_type=ConnectionType.FIBER,
            contract_duration_months=24
        )
        
        result = SearchResult.create_new(address)
        result.add_offer(offer)
        return result
    
    @pytest.mark.asyncio
    async def test_save_result(self, repository, mock_table, sample_search_result):
        """Test saving a search result."""
        mock_table.put_item.return_value = None
        
        share_token = await repository.save_result(sample_search_result)
        
        assert share_token == sample_search_result.share_token
        mock_table.put_item.assert_called_once()
        
        # Verify the item structure
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        assert item['request_id'] == sample_search_result.request_id
        assert item['share_token'] == sample_search_result.share_token
        assert 'address' in item
        assert 'offers' in item
    
    @pytest.mark.asyncio
    async def test_get_result_by_share_token_not_found(self, repository, mock_table):
        """Test getting result by share token when not found."""
        mock_table.query.return_value = {'Items': []}
        
        result = await repository.get_result_by_share_token('nonexistent')
        
        assert result is None
        mock_table.query.assert_called_once()


class TestAWSSQSMessageQueue:
    """Test AWS SQS message queue adapter."""
    
    @pytest.fixture
    def mock_sqs(self):
        """Mock SQS client."""
        with patch('boto3.client') as mock_client:
            mock_sqs = Mock()
            mock_client.return_value = mock_sqs
            yield mock_sqs
    
    @pytest.fixture
    def message_queue(self, mock_sqs):
        """Create message queue instance with mocked SQS."""
        return AWSSQSMessageQueue()
    
    @pytest.mark.asyncio
    async def test_send_message(self, message_queue, mock_sqs):
        """Test sending a message to SQS."""
        mock_sqs.get_queue_url.return_value = {'QueueUrl': 'https://sqs.test.com/test-queue'}
        mock_sqs.send_message.return_value = {'MessageId': 'test-message-id'}
        
        message = {'test': 'data', 'number': 42}
        message_id = await message_queue.send_message('test-queue', message)
        
        assert message_id == 'test-message-id'
        mock_sqs.send_message.assert_called_once()
        
        # Verify message structure
        call_args = mock_sqs.send_message.call_args
        assert call_args[1]['QueueUrl'] == 'https://sqs.test.com/test-queue'
        assert 'MessageBody' in call_args[1]
        assert 'MessageAttributes' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_receive_messages(self, message_queue, mock_sqs):
        """Test receiving messages from SQS."""
        mock_sqs.get_queue_url.return_value = {'QueueUrl': 'https://sqs.test.com/test-queue'}
        mock_sqs.receive_message.return_value = {
            'Messages': [
                {
                    'MessageId': 'msg-1',
                    'ReceiptHandle': 'receipt-1',
                    'Body': '{"test": "data"}',
                    'MessageAttributes': {
                        'Priority': {'StringValue': 'normal'}
                    },
                    'Attributes': {
                        'ApproximateReceiveCount': '1'
                    }
                }
            ]
        }
        
        messages = await message_queue.receive_messages('test-queue')
        
        assert len(messages) == 1
        assert messages[0]['message_id'] == 'msg-1'
        assert messages[0]['body'] == {'test': 'data'}
        assert messages[0]['attributes']['Priority'] == 'normal'


class TestAWSStepFunctionsOrchestrator:
    """Test AWS Step Functions orchestrator."""
    
    @pytest.fixture
    def mock_stepfunctions(self):
        """Mock Step Functions client."""
        with patch('boto3.client') as mock_client:
            mock_sf = Mock()
            mock_client.return_value = mock_sf
            yield mock_sf
    
    @pytest.fixture
    def orchestrator(self, mock_stepfunctions):
        """Create orchestrator instance with mocked Step Functions."""
        return AWSStepFunctionsOrchestrator()
    
    @pytest.mark.asyncio
    async def test_start_workflow(self, orchestrator, mock_stepfunctions):
        """Test starting a workflow execution."""
        mock_stepfunctions.list_state_machines.return_value = {
            'stateMachines': [
                {
                    'name': 'test-workflow',
                    'stateMachineArn': 'arn:aws:states:us-east-1:123456789012:stateMachine:test-workflow'
                }
            ]
        }
        mock_stepfunctions.start_execution.return_value = {
            'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test-workflow:test-execution'
        }
        
        input_data = {'test': 'data', 'number': 42}
        execution_arn = await orchestrator.start_workflow('test-workflow', input_data)
        
        assert 'test-execution' in execution_arn
        mock_stepfunctions.start_execution.assert_called_once()
        
        # Verify execution parameters
        call_args = mock_stepfunctions.start_execution.call_args
        assert 'stateMachineArn' in call_args[1]
        assert 'input' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_get_workflow_status(self, orchestrator, mock_stepfunctions):
        """Test getting workflow execution status."""
        mock_stepfunctions.describe_execution.return_value = {
            'status': 'SUCCEEDED'
        }
        
        from src.application.interfaces.messaging import WorkflowStatus
        
        status = await orchestrator.get_workflow_status('test-execution-arn')
        
        assert status == WorkflowStatus.SUCCEEDED
        mock_stepfunctions.describe_execution.assert_called_once()


class TestAWSAPIGatewayWebSocketManager:
    """Test AWS API Gateway WebSocket manager."""
    
    @pytest.fixture
    def mock_apigw(self):
        """Mock API Gateway Management API client."""
        with patch('boto3.client') as mock_client:
            mock_apigw = Mock()
            mock_client.return_value = mock_apigw
            yield mock_apigw
    
    @pytest.fixture
    def connection_manager(self, mock_apigw):
        """Create connection manager instance with mocked API Gateway."""
        return AWSAPIGatewayWebSocketManager('test-api-id.execute-api.us-east-1.amazonaws.com')
    
    @pytest.mark.asyncio
    async def test_send_to_connection_success(self, connection_manager, mock_apigw):
        """Test successfully sending message to connection."""
        mock_apigw.post_to_connection.return_value = None
        
        message = {'type': 'test', 'data': 'hello'}
        result = await connection_manager.send_to_connection('test-connection-id', message)
        
        assert result is True
        mock_apigw.post_to_connection.assert_called_once()
        
        # Verify message structure
        call_args = mock_apigw.post_to_connection.call_args
        assert call_args[1]['ConnectionId'] == 'test-connection-id'
        assert 'Data' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_send_to_connection_gone(self, connection_manager, mock_apigw):
        """Test sending message to gone connection."""
        from botocore.exceptions import ClientError
        
        mock_apigw.post_to_connection.side_effect = ClientError(
            {'Error': {'Code': 'GoneException'}}, 
            'PostToConnection'
        )
        
        message = {'type': 'test', 'data': 'hello'}
        result = await connection_manager.send_to_connection('test-connection-id', message)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_multiple_connections(self, connection_manager, mock_apigw):
        """Test sending message to multiple connections."""
        mock_apigw.post_to_connection.return_value = None
        
        connection_ids = ['conn-1', 'conn-2', 'conn-3']
        message = {'type': 'broadcast', 'data': 'hello all'}
        
        results = await connection_manager.send_to_multiple_connections(connection_ids, message)
        
        assert len(results) == 3
        assert all(results.values())  # All should be True
        assert mock_apigw.post_to_connection.call_count == 3


if __name__ == '__main__':
    pytest.main([__file__])