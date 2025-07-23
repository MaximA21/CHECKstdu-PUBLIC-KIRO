"""Example demonstrating dependency injection usage."""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.shared.dependency_injection import initialize_application, get_container, get_config


def main():
    """Demonstrate DI container usage."""
    # Set environment for testing
    os.environ["APP_ENVIRONMENT"] = "testing"

    # Initialize the application
    print("Initializing application...")
    container = initialize_application()

    # Get configuration
    config = get_config()
    print(f"Environment: {config.environment.value}")
    print(f"Database provider: {config.database.provider.value}")
    print(f"Messaging provider: {config.messaging.provider.value}")
    print(f"Logging provider: {config.logging.provider.value}")
    print(f"Debug mode: {config.debug}")

    # Demonstrate environment variable overrides
    print("\n--- Testing environment variable overrides ---")
    os.environ["DB_PROVIDER"] = "aws_dynamodb"
    os.environ["LOG_LEVEL"] = "DEBUG"

    # Reinitialize to pick up changes
    container = initialize_application()
    config = get_config()

    print(f"Database provider (after override): {config.database.provider.value}")
    print(f"Log level (after override): {config.logging.level}")

    print("\nDependency injection system initialized successfully!")


if __name__ == "__main__":
    main()
