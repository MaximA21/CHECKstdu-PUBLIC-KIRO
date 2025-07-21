"""Test AWS adapter structure and imports without requiring boto3."""

import sys
import os
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

def test_adapter_imports():
    """Test that all adapter classes can be imported."""
    
    # Mock boto3 and related modules to avoid import errors
    mock_boto3 = Mock()
    mock_botocore = Mock()
    mock_exceptions = Mock()
    mock_conditions = Mock()
    
    with patch.dict('sys.modules', {
        'boto3': mock_boto3,
        'botocore': mock_botocore,
        'botocore.exceptions': mock_exceptions,
        'boto3.dynamodb': Mock(),
        'boto3.dynamodb.conditions': mock_conditions
    }):
        # Test DynamoDB repository imports
        try:
            from src.infrastructure.persistence.aws_dynamodb_repository import (
                AWSDynamoDBSearchResultRepository,
                AWSDynamoDBConnectionRepository,
                AWSDynamoDBProviderOfferRepository,
                DynamoDBTypeConverter
            )
            print("✅ DynamoDB repository classes imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import DynamoDB repository classes: {e}")
            return False
        
        # Test SQS adapter imports
        try:
            from src.infrastructure.messaging.aws_sqs_adapter import AWSSQSMessageQueue
            print("✅ SQS message queue class imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import SQS adapter: {e}")
            return False
        
        # Test Step Functions adapter imports
        try:
            from src.infrastructure.messaging.aws_step_functions_adapter import AWSStepFunctionsOrchestrator
            print("✅ Step Functions orchestrator class imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import Step Functions adapter: {e}")
            return False
        
        # Test WebSocket adapter imports
        try:
            from src.infrastructure.messaging.aws_websocket_adapter import (
                AWSAPIGatewayWebSocketManager,
                AWSWebSocketTopicManager,
                AWSWebSocketNotifier
            )
            print("✅ WebSocket adapter classes imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import WebSocket adapter classes: {e}")
            return False
        
        # Test interface imports
        try:
            from src.application.interfaces.repositories import (
                ISearchResultRepository,
                IConnectionRepository,
                IProviderOfferRepository
            )
            from src.application.interfaces.messaging import (
                IMessageQueue,
                IWorkflowOrchestrator,
                MessagePriority,
                WorkflowStatus
            )
            from src.application.interfaces.connections import (
                IConnectionManager,
                ITopicManager,
                IConnectionNotifier
            )
            print("✅ All interface classes imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import interface classes: {e}")
            return False
        
        return True

def test_class_inheritance():
    """Test that adapter classes properly inherit from interfaces."""
    
    with patch.dict('sys.modules', {
        'boto3': Mock(),
        'botocore': Mock(),
        'botocore.exceptions': Mock()
    }):
        try:
            from src.infrastructure.persistence.aws_dynamodb_repository import AWSDynamoDBSearchResultRepository
            from src.application.interfaces.repositories import ISearchResultRepository
            
            # Check inheritance
            assert issubclass(AWSDynamoDBSearchResultRepository, ISearchResultRepository)
            print("✅ DynamoDB repository properly inherits from interface")
            
            from src.infrastructure.messaging.aws_sqs_adapter import AWSSQSMessageQueue
            from src.application.interfaces.messaging import IMessageQueue
            
            assert issubclass(AWSSQSMessageQueue, IMessageQueue)
            print("✅ SQS adapter properly inherits from interface")
            
            from src.infrastructure.messaging.aws_step_functions_adapter import AWSStepFunctionsOrchestrator
            from src.application.interfaces.messaging import IWorkflowOrchestrator
            
            assert issubclass(AWSStepFunctionsOrchestrator, IWorkflowOrchestrator)
            print("✅ Step Functions adapter properly inherits from interface")
            
            from src.infrastructure.messaging.aws_websocket_adapter import AWSAPIGatewayWebSocketManager
            from src.application.interfaces.connections import IConnectionManager
            
            assert issubclass(AWSAPIGatewayWebSocketManager, IConnectionManager)
            print("✅ WebSocket manager properly inherits from interface")
            
            return True
            
        except Exception as e:
            print(f"❌ Inheritance test failed: {e}")
            return False

def test_method_signatures():
    """Test that adapter classes have required methods."""
    
    with patch.dict('sys.modules', {
        'boto3': Mock(),
        'botocore': Mock(),
        'botocore.exceptions': Mock()
    }):
        try:
            from src.infrastructure.persistence.aws_dynamodb_repository import AWSDynamoDBSearchResultRepository
            
            # Check required methods exist
            repo_methods = [
                'save_result', 'get_result_by_share_token', 'get_result_by_request_id',
                'update_result', 'delete_result', 'get_results_by_address'
            ]
            
            for method_name in repo_methods:
                assert hasattr(AWSDynamoDBSearchResultRepository, method_name)
            
            print("✅ DynamoDB repository has all required methods")
            
            from src.infrastructure.messaging.aws_sqs_adapter import AWSSQSMessageQueue
            
            queue_methods = [
                'send_message', 'receive_messages', 'delete_message',
                'get_queue_attributes', 'purge_queue'
            ]
            
            for method_name in queue_methods:
                assert hasattr(AWSSQSMessageQueue, method_name)
            
            print("✅ SQS adapter has all required methods")
            
            return True
            
        except Exception as e:
            print(f"❌ Method signature test failed: {e}")
            return False

if __name__ == '__main__':
    print("Testing AWS adapter structure...")
    print("=" * 50)
    
    success = True
    
    success &= test_adapter_imports()
    print()
    
    success &= test_class_inheritance()
    print()
    
    success &= test_method_signatures()
    print()
    
    if success:
        print("🎉 All AWS adapter structure tests passed!")
    else:
        print("💥 Some tests failed!")
        sys.exit(1)