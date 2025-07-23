import json
import sys
import os

# Add src to path for imports
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.lambda_handlers.connection_limit_enforcer_handler import ConnectionLimitEnforcerHandler
from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase


def lambda_handler(event, context):
    """Lambda entry point for connection limit enforcer using dependency injection."""
    try:
        # Handle warmer requests efficiently - exit early
        if event.get('warmer'):
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Lambda warmed successfully",
                    "timestamp": "2024-01-01T00:00:00Z"
                })
            }
        
        # Get DI container
        container = get_container()
        
        # Create handler with dependencies
        handler = ConnectionLimitEnforcerHandler(
            connection_management_use_case=container.get(ConnectionManagementUseCase),
            logger=container.get_logger("connection_limit_enforcer")
        )
        
        # Handle request using DI
        import asyncio
        result = asyncio.run(handler.handle_request(event))
        
        return result
        
    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in connection limit enforcer: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }