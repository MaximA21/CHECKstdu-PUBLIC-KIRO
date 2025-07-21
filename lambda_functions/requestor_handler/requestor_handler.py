import json
import sys
import os

# Add src to path for imports
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.lambda_handlers.requestor_handler import RequestorHandler
from src.application.use_cases.requestor_use_case import RequestorUseCase


def lambda_handler(event, context):
    """Lambda entry point for requestor handler using dependency injection."""
    try:
        # Get DI container
        container = get_container()
        
        # Create handler with dependencies
        handler = RequestorHandler(
            requestor_use_case=container.get(RequestorUseCase),
            logger=container.get_logger("requestor_handler")
        )
        
        # Handle SQS records
        for record in event.get('Records', []):
            try:
                # Parse SQS message body
                message_body = json.loads(record.get('body', '{}'))
                
                # Handle request using DI
                import asyncio
                asyncio.run(handler.handle_request({
                    'body': json.dumps(message_body)
                }))
                
            except Exception as e:
                # Log error but continue processing other records
                print(f"Error processing record: {e}")
                continue
        
        return {"statusCode": 200, "body": "Requests processed successfully"}
        
    except Exception as e:
        # Fallback error handling if DI fails
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }