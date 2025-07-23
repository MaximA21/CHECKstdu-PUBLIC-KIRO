import json
import sys
import os

# Add src to path for imports
sys.path.append("/opt/python")
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

try:
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.address_normalizer_handler import AddressNormalizerHandler
    from src.application.use_cases.address_normalization_use_case import AddressNormalizationUseCase
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.address_normalizer_handler import AddressNormalizerHandler
    from src.application.use_cases.address_normalization_use_case import AddressNormalizationUseCase


def lambda_handler(event, context):
    """Lambda entry point for address normalization using dependency injection."""
    try:
        # Handle warmer requests efficiently
        if event.get("warmer"):
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Lambda warmed successfully", "function": "address_normalizer"}),
            }

        # Get DI container
        container = get_container()

        # Create handler with dependencies
        handler = AddressNormalizerHandler(
            address_normalization_use_case=container.get(AddressNormalizationUseCase),
            logger=container.get_logger("address_normalizer"),
        )

        # Handle request
        import asyncio

        return asyncio.run(handler.handle_request(event))

    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in address normalizer: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Internal server error", "message": "Address normalization failed"}),
        }
