import json
import os
import sys

# Add src to path for imports
sys.path.append("/opt/python")
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

try:
    from src.application.use_cases.share_results_use_case import ShareResultsUseCase
    from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
    from src.shared.dependency_injection.bootstrap import get_container
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.application.use_cases.share_results_use_case import ShareResultsUseCase
    from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
    from src.shared.dependency_injection.bootstrap import get_container


def lambda_handler(event, context):
    """Lambda entry point for share API using dependency injection."""
    try:
        # Handle warmer requests efficiently
        if event.get("warmer"):
            return {"statusCode": 200, "body": json.dumps({"message": "Lambda warmed successfully", "function": "share_api"})}

        # Get DI container
        container = get_container()

        # Create handler with dependencies
        handler = ShareApiHandler(
            share_results_use_case=container.get(ShareResultsUseCase), logger=container.get_logger("share_api")
        )

        # Handle request
        import asyncio

        return asyncio.run(handler.handle_request(event))

    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in share API: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Internal server error", "message": "Share API request failed"}),
        }
