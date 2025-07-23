import json
import os
import sys

# Add src to path for imports
sys.path.append("/opt/python")
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

try:
    from src.application.use_cases.requestor_use_case import RequestorUseCase
    from src.presentation.lambda_handlers.requestor_handler import RequestorHandler
    from src.shared.dependency_injection.bootstrap import get_container
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.application.use_cases.requestor_use_case import RequestorUseCase
    from src.presentation.lambda_handlers.requestor_handler import RequestorHandler
    from src.shared.dependency_injection.bootstrap import get_container


def lambda_handler(event, context):
    """Lambda entry point for requestor handler using dependency injection."""
    try:
        # Handle warmer requests efficiently
        if event.get("warmer"):
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Lambda warmed successfully", "function": "requestor_handler"}),
            }

        # Get DI container
        container = get_container()

        # Create handler with dependencies
        handler = RequestorHandler(
            requestor_use_case=container.get(RequestorUseCase), logger=container.get_logger("requestor_handler")
        )

        # Handle SQS records
        processed_count = 0
        for record in event.get("Records", []):
            try:
                # Parse SQS message body
                message_body = json.loads(record.get("body", "{}"))

                # Handle request using DI
                import asyncio

                result = asyncio.run(handler.handle_request({"body": json.dumps(message_body)}))

                if result.get("statusCode") == 200:
                    processed_count += 1

            except Exception as e:
                # Log error but continue processing other records
                print(f"Error processing record: {e}")
                continue

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Requests processed successfully",
                    "processed_count": processed_count,
                    "total_records": len(event.get("Records", [])),
                }
            ),
        }

    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in requestor handler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error", "message": "Request processing failed"}),
        }
