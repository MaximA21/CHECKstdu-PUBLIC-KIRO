"""Unit tests for AWS service adapters."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from moto import mock_dynamodb, mock_sqs, mock_apigateway
import boto3
from src.infrastructure.persistence.aws_dynamodb_repository import AWSDynamoDBRepository
from src.infrastructure.messaging.aws_sqs_adapter import AWSSQSAdapter
from src.infrastructure.messaging.aws_websocket_adapter import AWSWebSocketAdapter


@mock_dynamodb
class TestAWSDynamoDBRepository:
    """Test AWS DynamoDB repository."""

    def setup_method(self):
        """Set up test fixtures."""
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        
        # Create test table
        self.table = self.dynamodb.create_table(
            TableName='test-table',
            KeySchema=[
                {'AttributeName': 'pk', 'KeyType': 'HASH'},
                {'AttributeName': 'sk', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'sk', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        self.repository = AWSDynamoDBRepository(
            table_name='test-table',
            region='us-east-1'
        )

    @pytest.mark.asyncio
    async def test_save_search_result_success(self):
        """Test saving search result to DynamoDB."""
        from src.domain.entities.search_result import SearchResult
        from src.domain.value_objects.address import Address
        
        result = SearchResult(
            request_id="req-123",
            address=Address(
                street="Test Street",
                city="Berlin",
                postal_code="10115",
                country="Germany"
            ),
            offers=[],
            search_timestamp="2024-01-01T12:00:00Z"
        )
        
        # Should not raise exception
        await self.repository.save_search_result(result)
        
        # Verify item was saved
        response = self.table.get_item(
            Key={'pk': 'SEARCH_RESULT', 'sk': 'req-123'}
        )
        assert 'Item' in response

    @pytest.mark.asyncio
    async def test_get_search_result_success(self):
        """Test retrieving search result from DynamoDB."""
        # First save a result
        self.table.put_item(
            Item={
                'pk': 'SEARCH_RESULT',
                'sk': 'req-123',
                'request_id': 'req-123',
                'address': {
                    'street': 'Test Street',
                    'city': 'Berlin',
                    'postal_code': '10115',
                    'country': 'Germany'
                },
                'offers': [],
                'search_timestamp': '2024-01-01T12:00:00Z'
            }
        )
        
        result = await self.repository.get_search_result('req-123')
        
        assert result is not None
        assert result.request_id == 'req-123'

    @pytest.mark.asyncio
    async def test_get_search_result_not_found(self):
        """Test retrieving non-existent search result."""
        result = await self.repository.get_search_result('nonexistent')
        assert result is None

    @pytest.mark.asyncio
    async def test_save_connection_success(self):
        """Test saving connection session."""
        from src.domain.entities.connection_session import ConnectionSession
        
        session = ConnectionSession(
            connection_id="conn-123",
            user_id="user-456",
            connected_at="2024-01-01T12:00:00Z",
            last_activity="2024-01-01T12:05:00Z",
            status="active"
        )
        
        await self.repository.save_connection(session)
        
        # Verify item was saved
        response = self.table.get_item(
            Key={'pk': 'CONNECTION', 'sk': 'conn-123'}
        )
        assert 'Item' in response

    @pytest.mark.asyncio
    async def test_get_connection_success(self):
        """Test retrieving connection session."""
        # First save a connection
        self.table.put_item(
            Item={
                'pk': 'CONNECTION',
                'sk': 'conn-123',
                'connection_id': 'conn-123',
                'user_id': 'user-456',
                'connected_at': '2024-01-01T12:00:00Z',
                'last_activity': '2024-01-01T12:05:00Z',
                'status': 'active'
            }
        )
        
        session = await self.repository.get_connection('conn-123')
        
        assert session is not None
        assert session.connection_id == 'conn-123'
        assert session.user_id == 'user-456'

    @pytest.mark.asyncio
    async def test_get_active_connections(self):
        """Test retrieving active connections."""
        # Save multiple connections
        connections = [
            {
                'pk': 'CONNECTION',
                'sk': 'conn-1',
                'connection_id': 'conn-1',
                'user_id': 'user-1',
                'status': 'active'
            },
            {
                'pk': 'CONNECTION',
                'sk': 'conn-2',
                'connection_id': 'conn-2',
                'user_id': 'user-2',
                'status': 'active'
            },
            {
                'pk': 'CONNECTION',
                'sk': 'conn-3',
                'connection_id': 'conn-3',
                'user_id': 'user-3',
                'status': 'disconnected'
            }
        ]
        
        for conn in connections:
            self.table.put_item(Item=conn)
        
        active_sessions = await self.repository.get_active_connections()
        
        # Should only return active connections
        assert len(active_sessions) == 2
        assert all(session.status == 'active' for session in active_sessions)


@mock_sqs
class TestAWSSQSAdapter:
    """Test AWS SQS adapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sqs = boto3.client('sqs', region_name='us-east-1')
        
        # Create test queue
        response = self.sqs.create_queue(QueueName='test-queue')
        self.queue_url = response['QueueUrl']
        
        self.adapter = AWSSQSAdapter(
            queue_url=self.queue_url,
            region='us-east-1'
        )

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test sending message to SQS."""
        message = {
            "type": "search_request",
            "request_id": "req-123",
            "data": {"test": "data"}
        }
        
        message_id = await self.adapter.send_message(message)
        
        assert message_id is not None
        
        # Verify message was sent
        response = self.sqs.receive_message(QueueUrl=self.queue_url)
        assert 'Messages' in response
        assert len(response['Messages']) == 1

    @pytest.mark.asyncio
    async def test_send_message_with_delay(self):
        """Test sending message with delay."""
        message = {"type": "delayed_message"}
        
        message_id = await self.adapter.send_message(message, delay_seconds=30)
        
        assert message_id is not None

    @pytest.mark.asyncio
    async def test_receive_messages_success(self):
        """Test receiving messages from SQS."""
        # Send a test message first
        test_message = {"type": "test", "data": "value"}
        await self.adapter.send_message(test_message)
        
        messages = await self.adapter.receive_messages(max_messages=1)
        
        assert len(messages) == 1
        assert messages[0]['type'] == 'test'

    @pytest.mark.asyncio
    async def test_receive_messages_empty_queue(self):
        """Test receiving messages from empty queue."""
        messages = await self.adapter.receive_messages(max_messages=5)
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_delete_message_success(self):
        """Test deleting message from SQS."""
        # Send and receive a message
        await self.adapter.send_message({"type": "test"})
        
        # Receive message to get receipt handle
        response = self.sqs.receive_message(QueueUrl=self.queue_url)
        receipt_handle = response['Messages'][0]['ReceiptHandle']
        
        # Delete message
        success = await self.adapter.delete_message(receipt_handle)
        assert success is True

    @pytest.mark.asyncio
    async def test_get_queue_attributes(self):
        """Test getting queue attributes."""
        attributes = await self.adapter.get_queue_attributes()
        
        assert 'ApproximateNumberOfMessages' in attributes
        assert 'QueueArn' in attributes


class TestAWSWebSocketAdapter:
    """Test AWS WebSocket adapter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = AWSWebSocketAdapter(
            api_endpoint="https://test.execute-api.us-east-1.amazonaws.com/test",
            region="us-east-1"
        )

    @patch('boto3.client')
    @pytest.mark.asyncio
    async def test_send_message_to_connection_success(self, mock_boto3):
        """Test sending message to WebSocket connection."""
        mock_client = Mock()
        mock_client.post_to_connection.return_value = {}
        mock_boto3.return_value = mock_client
        
        message = {"type": "search_results", "data": []}
        
        success = await self.adapter.send_message_to_connection(
            connection_id="conn-123",
            message=message
        )
        
        assert success is True
        mock_client.post_to_connection.assert_called_once()

    @patch('boto3.client')
    @pytest.mark.asyncio
    async def test_send_message_connection_gone(self, mock_boto3):
        """Test sending message to disconnected connection."""
        mock_client = Mock()
        mock_client.post_to_connection.side_effect = Exception("GoneException")
        mock_boto3.return_value = mock_client
        
        message = {"type": "test"}
        
        success = await self.adapter.send_message_to_connection(
            connection_id="conn-gone",
            message=message
        )
        
        assert success is False

    @patch('boto3.client')
    @pytest.mark.asyncio
    async def test_broadcast_message_success(self, mock_boto3):
        """Test broadcasting message to multiple connections."""
        mock_client = Mock()
        mock_client.post_to_connection.return_value = {}
        mock_boto3.return_value = mock_client
        
        connection_ids = ["conn-1", "conn-2", "conn-3"]
        message = {"type": "broadcast", "data": "test"}
        
        results = await self.adapter.broadcast_message(connection_ids, message)
        
        assert len(results) == 3
        assert all(result is True for result in results)
        assert mock_client.post_to_connection.call_count == 3

    @patch('boto3.client')
    @pytest.mark.asyncio
    async def test_broadcast_message_partial_failure(self, mock_boto3):
        """Test broadcasting with some connection failures."""
        mock_client = Mock()
        
        def side_effect(*args, **kwargs):
            connection_id = kwargs.get('ConnectionId')
            if connection_id == 'conn-2':
                raise Exception("GoneException")
            return {}
        
        mock_client.post_to_connection.side_effect = side_effect
        mock_boto3.return_value = mock_client
        
        connection_ids = ["conn-1", "conn-2", "conn-3"]
        message = {"type": "broadcast"}
        
        results = await self.adapter.broadcast_message(connection_ids, message)
        
        assert len(results) == 3
        assert results[0] is True   # conn-1 success
        assert results[1] is False  # conn-2 failed
        assert results[2] is True   # conn-3 success

    @pytest.mark.asyncio
    async def test_validate_connection_id(self):
        """Test connection ID validation."""
        # Valid connection ID
        assert self.adapter.validate_connection_id("valid-conn-123") is True
        
        # Invalid connection IDs
        assert self.adapter.validate_connection_id("") is False
        assert self.adapter.validate_connection_id(None) is False
        assert self.adapter.validate_connection_id("invalid chars!") is False

    @pytest.mark.asyncio
    async def test_get_connection_info(self):
        """Test getting connection information."""
        # This would typically call API Gateway Management API
        # For now, test the method exists and handles errors gracefully
        info = await self.adapter.get_connection_info("conn-123")
        
        # Should return None or connection info without crashing
        assert info is None or isinstance(info, dict)