"""Infrastructure messaging layer."""

# Import mock implementations (always available)
from .mock_connection_manager import MockConnectionManager, MockConnectionNotifier, MockTopicManager
from .mock_messaging import MockEventBus, MockMessageQueue, MockWorkflowOrchestrator

# Import AWS implementations (optional, requires boto3)
try:
    from .aws_sqs_adapter import AWSSQSMessageQueue
    from .aws_step_functions_adapter import AWSStepFunctionsOrchestrator
    from .aws_websocket_adapter import AWSAPIGatewayWebSocketManager, AWSWebSocketNotifier, AWSWebSocketTopicManager

    _aws_available = True
except ImportError:
    _aws_available = False

__all__ = [
    "MockMessageQueue",
    "MockWorkflowOrchestrator",
    "MockEventBus",
    "MockConnectionManager",
    "MockTopicManager",
    "MockConnectionNotifier",
]

if _aws_available:
    __all__.extend(
        [
            "AWSSQSMessageQueue",
            "AWSStepFunctionsOrchestrator",
            "AWSAPIGatewayWebSocketManager",
            "AWSWebSocketTopicManager",
            "AWSWebSocketNotifier",
        ]
    )
