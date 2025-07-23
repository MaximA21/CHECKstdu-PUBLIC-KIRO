#!/usr/bin/env python3
"""
Example demonstrating the logging abstraction layer usage.

This example shows how to use the new logging abstraction layer
that wraps the existing logging_config functionality.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.infrastructure.logging import LoggerFactory, create_logger, create_lambda_logger, LogConfiguration
from src.application.interfaces.logging import LogLevel, LogFormat


def demonstrate_console_logging():
    """Demonstrate console logging functionality."""
    print("=== Console Logging Demo ===")

    # Create a logger using the factory
    factory = LoggerFactory("console")
    logger = factory.create_logger("demo_app", LogLevel.DEBUG)

    # Basic logging
    logger.debug("This is a debug message")
    logger.info("Application started successfully")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Logging with context
    context = {"user_id": "12345", "action": "login", "ip": "192.168.1.1"}
    logger.info("User login attempt", context)

    # Logging with exception
    try:
        raise ValueError("Something went wrong!")
    except ValueError as e:
        logger.error("An error occurred during processing", exception=e)

    print()


def demonstrate_structured_logging():
    """Demonstrate structured logging functionality."""
    print("=== Structured Logging Demo ===")

    factory = LoggerFactory("console")
    logger = factory.create_structured_logger("structured_demo")

    # Log structured events
    logger.log_event("user_registration", {"user_id": "user_123", "email": "user@example.com", "registration_source": "web"})

    # Log metrics
    logger.log_metric("response_time", 145.2, "ms", {"endpoint": "/api/users"})
    logger.log_metric("memory_usage", 512.8, "MB")

    # Log performance data
    logger.log_performance("database_query", 23.5, True, {"table": "users", "rows": 150})

    # Demonstrate span tracing
    span_id = logger.start_span("user_processing")
    logger.info("Processing user data...")
    logger.end_span(span_id, True, {"processed_records": 10})

    # Log request/response
    logger.log_request_start("req-456", "POST", "/api/users", {"Content-Type": "application/json"})
    logger.log_request_end("req-456", 201, 89.3, 1024)

    # Log database operations
    logger.log_database_operation("INSERT", "users", 15.2, True, 1)

    # Log external API calls
    logger.log_external_api_call("payment_service", "/api/charge", "POST", 234.1, 200, True)

    print()


def demonstrate_lambda_logging():
    """Demonstrate Lambda-specific logging."""
    print("=== Lambda Logging Demo ===")

    # Create Lambda logger using convenience function
    logger = create_lambda_logger("my_lambda_function")

    logger.info("Lambda function started")
    logger.info("Processing event", {"event_type": "S3", "bucket": "my-bucket"})

    # If using CloudWatch logger, it would add Lambda-specific metadata
    if hasattr(logger, "log_cold_start"):
        logger.log_cold_start(1500.0, 512)
        logger.log_memory_usage(400.0, 512)
        logger.log_lambda_timeout_warning(5000.0)

    logger.info("Lambda function completed successfully")

    print()


def demonstrate_configuration():
    """Demonstrate logging configuration management."""
    print("=== Configuration Demo ===")

    config = LogConfiguration()

    print(f"Current log level: {config.get_log_level()}")
    print(f"Current log format: {config.get_log_format()}")
    print(f"Structured logging enabled: {config.is_structured_logging_enabled()}")

    # Change configuration
    config.set_log_level(LogLevel.DEBUG)
    config.enable_structured_logging(True)

    print(f"Updated log level: {config.get_log_level()}")
    print(f"Structured logging enabled: {config.is_structured_logging_enabled()}")

    # Get full configuration
    full_config = config.get_configuration()
    print("Full configuration:")
    for key, value in full_config.items():
        print(f"  {key}: {value}")

    print()


def demonstrate_factory_features():
    """Demonstrate advanced factory features."""
    print("=== Factory Features Demo ===")

    factory = LoggerFactory("auto")  # Auto-detect environment

    print(f"Current provider: {factory.get_provider()}")
    print(f"Effective provider: {factory.get_effective_provider()}")

    # Create loggers for different purposes
    app_logger = factory.create_logger("myapp.main")
    db_logger = factory.create_logger("myapp.database", LogLevel.WARNING)
    api_logger = factory.create_structured_logger("myapp.api")

    # Demonstrate logger for class
    class UserService:
        pass

    service_logger = factory.create_logger_for_class(UserService)

    app_logger.info("Application logger message")
    db_logger.warning("Database logger message")
    api_logger.log_event("api_call", {"endpoint": "/users", "method": "GET"})
    service_logger.info("Service logger message")

    # Show factory configuration
    factory_config = factory.get_configuration()
    print("Factory configuration:")
    for key, value in factory_config.items():
        if key != "config":  # Skip detailed config for brevity
            print(f"  {key}: {value}")

    print()


def demonstrate_convenience_functions():
    """Demonstrate convenience functions."""
    print("=== Convenience Functions Demo ===")

    # Quick logger creation
    quick_logger = create_logger("quick_demo", "console", LogLevel.INFO)
    quick_logger.info("Created with convenience function")

    # Quick Lambda logger
    lambda_logger = create_lambda_logger("demo_function", "console")
    lambda_logger.info("Lambda logger created with convenience function")

    print()


def main():
    """Run all demonstrations."""
    print("Logging Abstraction Layer Demonstration")
    print("=" * 50)
    print()

    demonstrate_console_logging()
    demonstrate_structured_logging()
    demonstrate_lambda_logging()
    demonstrate_configuration()
    demonstrate_factory_features()
    demonstrate_convenience_functions()

    print("Demo completed successfully!")


if __name__ == "__main__":
    main()
