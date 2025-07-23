#!/usr/bin/env python3
"""
Example demonstrating logging abstraction integration with dependency injection.

This example shows how the logging abstraction layer can be integrated
with the dependency injection system for enterprise applications.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.infrastructure.logging import LoggerFactory
from src.application.interfaces.logging import ILogger, ILoggerFactory, LogLevel
from src.shared.dependency_injection.container import DIContainer


class UserService:
    """Example service that uses injected logger."""

    def __init__(self, logger: ILogger):
        self._logger = logger

    def create_user(self, user_data: dict) -> str:
        """Create a new user."""
        self._logger.info("Creating new user", {"email": user_data.get("email")})

        try:
            # Simulate user creation logic
            user_id = f"user_{hash(user_data['email']) % 10000}"

            self._logger.info("User created successfully", {"user_id": user_id, "email": user_data.get("email")})

            return user_id

        except Exception as e:
            self._logger.error("Failed to create user", {"email": user_data.get("email")}, exception=e)
            raise

    def get_user(self, user_id: str) -> dict:
        """Get user by ID."""
        self._logger.debug("Fetching user", {"user_id": user_id})

        # Simulate database lookup
        user_data = {"id": user_id, "email": f"user{user_id}@example.com", "name": f"User {user_id}"}

        self._logger.debug("User fetched successfully", {"user_id": user_id})
        return user_data


class OrderService:
    """Example service that uses structured logger."""

    def __init__(self, logger: ILogger):
        self._logger = logger

    def process_order(self, order_data: dict) -> str:
        """Process a new order."""
        # If logger supports structured logging, use it
        if hasattr(self._logger, "log_event"):
            self._logger.log_event(
                "order_processing_started",
                {
                    "order_id": order_data.get("id"),
                    "customer_id": order_data.get("customer_id"),
                    "total_amount": order_data.get("total"),
                },
            )
        else:
            self._logger.info("Processing order", order_data)

        try:
            # Simulate order processing
            order_id = order_data.get("id", f"order_{hash(str(order_data)) % 10000}")

            # Log performance metrics if supported
            if hasattr(self._logger, "log_performance"):
                self._logger.log_performance("order_validation", 25.3, True, {"order_id": order_id, "validation_rules": 5})

            # Log external API call if supported
            if hasattr(self._logger, "log_external_api_call"):
                self._logger.log_external_api_call("payment_service", "/api/charge", "POST", 150.2, 200, True)

            if hasattr(self._logger, "log_event"):
                self._logger.log_event(
                    "order_processing_completed", {"order_id": order_id, "processing_time_ms": 175.5, "status": "success"}
                )
            else:
                self._logger.info("Order processed successfully", {"order_id": order_id})

            return order_id

        except Exception as e:
            self._logger.error("Failed to process order", {"order_data": order_data}, exception=e)
            raise


def configure_logging_di_container() -> DIContainer:
    """Configure dependency injection container with logging services."""
    container = DIContainer()

    # Register logger factory as singleton
    logger_factory = LoggerFactory("auto")  # Auto-detect environment
    container.register_singleton(ILoggerFactory, lambda: logger_factory)

    # Register specific loggers
    container.register("user_service_logger", lambda: logger_factory.create_logger("services.user", LogLevel.DEBUG))

    container.register(
        "order_service_logger", lambda: logger_factory.create_structured_logger("services.order", LogLevel.INFO)
    )

    # Register services with logger dependencies
    container.register(UserService, lambda: UserService(container.resolve("user_service_logger")))

    container.register(OrderService, lambda: OrderService(container.resolve("order_service_logger")))

    return container


def demonstrate_di_integration():
    """Demonstrate dependency injection integration."""
    print("=== Dependency Injection Integration Demo ===")

    # Configure container
    container = configure_logging_di_container()

    # Resolve services (loggers are automatically injected)
    user_service = container.resolve(UserService)
    order_service = container.resolve(OrderService)

    # Use services - logging happens automatically
    print("\n--- User Service Operations ---")
    user_id = user_service.create_user({"email": "john.doe@example.com", "name": "John Doe"})

    user_data = user_service.get_user(user_id)
    print(f"Retrieved user: {user_data}")

    print("\n--- Order Service Operations ---")
    order_id = order_service.process_order(
        {"id": "order_123", "customer_id": user_id, "total": 99.99, "items": ["item1", "item2"]}
    )

    print(f"Processed order: {order_id}")

    print()


def demonstrate_lambda_handler_pattern():
    """Demonstrate Lambda handler pattern with DI and logging."""
    print("=== Lambda Handler Pattern Demo ===")

    def lambda_handler(event, context):
        """Example Lambda handler using DI container."""
        # Create container for this Lambda execution
        container = configure_logging_di_container()

        # Get Lambda-specific logger
        factory = container.resolve(ILoggerFactory)
        lambda_logger = factory.create_lambda_logger("user_management_lambda")

        lambda_logger.info(
            "Lambda execution started",
            {"event_type": event.get("eventType"), "request_id": getattr(context, "aws_request_id", "local-test")},
        )

        try:
            # Resolve service with injected logger
            user_service = container.resolve(UserService)

            # Process the event
            if event.get("action") == "create_user":
                result = user_service.create_user(event.get("userData", {}))
                lambda_logger.info("Lambda execution completed successfully", {"result": result})
                return {"statusCode": 200, "body": {"user_id": result}}

            elif event.get("action") == "get_user":
                result = user_service.get_user(event.get("userId"))
                lambda_logger.info("Lambda execution completed successfully")
                return {"statusCode": 200, "body": result}

            else:
                lambda_logger.warning("Unknown action requested", {"action": event.get("action")})
                return {"statusCode": 400, "body": {"error": "Unknown action"}}

        except Exception as e:
            lambda_logger.error("Lambda execution failed", {"event": event}, exception=e)
            return {"statusCode": 500, "body": {"error": str(e)}}

    # Simulate Lambda events
    class MockContext:
        aws_request_id = "test-request-123"

    # Test create user
    create_event = {
        "eventType": "user_management",
        "action": "create_user",
        "userData": {"email": "lambda.user@example.com", "name": "Lambda User"},
    }

    result = lambda_handler(create_event, MockContext())
    print(f"Create user result: {result}")

    # Test get user
    get_event = {"eventType": "user_management", "action": "get_user", "userId": "user_1234"}

    result = lambda_handler(get_event, MockContext())
    print(f"Get user result: {result}")

    print()


def demonstrate_environment_specific_logging():
    """Demonstrate environment-specific logging configuration."""
    print("=== Environment-Specific Logging Demo ===")

    # Simulate different environments
    environments = ["development", "staging", "production"]

    for env in environments:
        print(f"\n--- {env.upper()} Environment ---")

        # Configure environment-specific settings
        os.environ["ENVIRONMENT"] = env
        if env == "development":
            os.environ["LOG_LEVEL"] = "DEBUG"
            provider = "console"
        elif env == "staging":
            os.environ["LOG_LEVEL"] = "INFO"
            provider = "console"  # Would be "cloudwatch" in real AWS staging
        else:  # production
            os.environ["LOG_LEVEL"] = "WARNING"
            provider = "console"  # Would be "cloudwatch" in real AWS production

        # Create environment-specific factory
        factory = LoggerFactory(provider)
        logger = factory.create_logger(f"app.{env}")

        # Log at different levels to show filtering
        logger.debug(f"Debug message in {env}")
        logger.info(f"Info message in {env}")
        logger.warning(f"Warning message in {env}")
        logger.error(f"Error message in {env}")

    print()


def main():
    """Run all demonstrations."""
    print("Logging Abstraction + Dependency Injection Integration")
    print("=" * 60)
    print()

    demonstrate_di_integration()
    demonstrate_lambda_handler_pattern()
    demonstrate_environment_specific_logging()

    print("Integration demo completed successfully!")


if __name__ == "__main__":
    main()
