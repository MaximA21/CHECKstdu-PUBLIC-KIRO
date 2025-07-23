import json
import sys
import os

# Add src to path for imports
sys.path.append("/opt/python")
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

try:
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.authorizer_handler import AuthorizerHandler
    from src.application.use_cases.authorization_use_case import AuthorizationUseCase
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.shared.dependency_injection.bootstrap import get_container
    from src.presentation.lambda_handlers.authorizer_handler import AuthorizerHandler
    from src.application.use_cases.authorization_use_case import AuthorizationUseCase


def lambda_handler(event, context):
    """Lambda entry point for API Gateway authorizer using dependency injection."""
    try:
        # Handle warmer requests efficiently
        if event.get("warmer"):
            return {"statusCode": 200, "body": json.dumps({"message": "Lambda warmed successfully", "function": "authorizer"})}

        # Get DI container
        container = get_container()

        # Create handler with dependencies
        handler = AuthorizerHandler(
            authorization_use_case=container.get(AuthorizationUseCase), logger=container.get_logger("authorizer")
        )

        # Handle request
        import asyncio

        return asyncio.run(handler.handle_request(event))

    except Exception as e:
        # Fallback error handling if DI fails
        print(f"Error in authorizer: {e}")
        # Return deny policy for security
        return {
            "principalId": "unknown",
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [{"Action": "execute-api:Invoke", "Effect": "Deny", "Resource": "*"}],
            },
        }
