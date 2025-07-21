import json
import sys
import os

# Add src to path for imports
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
from src.application.use_cases.share_results_use_case import ShareResultsUseCase


def lambda_handler(event, context):
    """Lambda entry point for share API using dependency injection."""
    try:
        # Get DI container
        container = get_container()
        
        # Create handler with dependencies
        handler = ShareApiHandler(
            share_results_use_case=container.get(ShareResultsUseCase),
            logger=container.get_logger("share_api")
        )
        
        # Handle request
        import asyncio
        return asyncio.run(handler.handle_request(event))
        
    except Exception as e:
        # Fallback error handling if DI fails
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }