import json
import sys
import os

# Add src to path for imports
sys.path.append("/opt/python")
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

try:
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.results_handler import ResultsHandler
    from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.results_handler import ResultsHandler
    from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase


def lambda_handler(event, context):
    """Lambda entry point for results handler using dependency injection."""
    try:
        # Handle warmer requests efficiently - exit early
        if event.get("warmer"):
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Lambda warmed successfully", "function": "results_handler"}),
            }

        # Get DI container
        container = get_container()

        # Get process results use case and inject connection management
        process_results_use_case = container.get(ProcessResultsUseCase)
        connection_management_use_case = container.get(ConnectionManagementUseCase)

        # Inject connection management use case
        process_results_use_case._connection_management_use_case = connection_management_use_case

        # Create handler with dependencies
        handler = ResultsHandler(
            process_results_use_case=process_results_use_case, logger=container.get_logger("results_handler")
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
                    "message": "Results processed successfully",
                    "processed_count": processed_count,
                    "total_records": len(event.get("Records", [])),
                }
            ),
        }

    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in results handler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error", "message": "Results processing failed"}),
        }
