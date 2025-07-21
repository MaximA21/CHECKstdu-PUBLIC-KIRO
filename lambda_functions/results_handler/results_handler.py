import json
import sys
import os

# Add src to path for imports
sys.path.append('/opt/python')
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.lambda_handlers.results_handler import ResultsHandler
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase


def lambda_handler(event, context):
    """Lambda entry point for results handler using dependency injection."""
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
        handler = ResultsHandler(
            process_results_use_case=container.get(ProcessResultsUseCase),
            logger=container.get_logger("results_handler")
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
        
        return {"statusCode": 200, "body": "Results processed successfully"}
        
    except Exception as e:
        # Fallback error handling if DI fails
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }