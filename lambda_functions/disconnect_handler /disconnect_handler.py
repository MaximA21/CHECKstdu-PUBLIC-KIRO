import json
import sys
import os

# Add src to path for imports
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.disconnect_handler import DisconnectHandler
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.disconnect_handler import DisconnectHandler
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase


def lambda_handler(event, context):
    """Lambda entry point for WebSocket disconnection using dependency injection."""
    try:
        # Handle warmer requests efficiently
        if event.get('warmer'):
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Lambda warmed successfully",
                    "function": "disconnect_handler"
                })
            }
        
        # Get DI container
        container = get_container()
        
        # Create handler with dependencies
        handler = DisconnectHandler(
            connection_management_use_case=container.get(ConnectionManagementUseCase),
            logger=container.get_logger("disconnect_handler")
        )
        
        # Handle request
        import asyncio
        return asyncio.run(handler.handle_request(event))
        
    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in disconnect handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': 'Disconnection failed'
            })
        }