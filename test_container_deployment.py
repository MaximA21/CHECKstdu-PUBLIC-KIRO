#!/usr/bin/env python3
"""Test script for container deployment functionality."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.infrastructure.config.loader import ConfigLoader
from src.shared.dependency_injection.bootstrap import get_container
from src.presentation.http_controllers.search_controller import SearchController
from src.presentation.http_controllers.share_controller import ShareController


async def test_container_configuration():
    """Test container configuration loading."""
    print("Testing container configuration...")

    try:
        # Load container configuration
        config_loader = ConfigLoader("config")
        config = config_loader.load_config()

        print(f"✓ Configuration loaded successfully")
        print(f"  Environment: {config.environment.value}")
        print(f"  HTTP Port: {config.container.http_port}")
        print(f"  WebSocket Port: {config.container.websocket_port}")
        print(f"  Database Provider: {config.database.provider.value}")
        print(f"  Messaging Provider: {config.messaging.provider.value}")
        print(f"  Logging Provider: {config.logging.provider.value}")

        return True

    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return False


async def test_dependency_injection():
    """Test dependency injection container."""
    print("\nTesting dependency injection...")

    try:
        # Load configuration
        config_loader = ConfigLoader("config")
        config = config_loader.load_config()

        # Get container
        container = get_container()

        print(f"✓ DI container bootstrapped successfully")

        # Test controller resolution
        search_controller = container.resolve(SearchController)
        share_controller = container.resolve(ShareController)

        print(f"✓ Controllers resolved successfully")
        print(f"  Search Controller: {type(search_controller).__name__}")
        print(f"  Share Controller: {type(share_controller).__name__}")

        return True

    except Exception as e:
        print(f"✗ Dependency injection failed: {e}")
        return False


async def test_mock_request():
    """Test mock request handling."""
    print("\nTesting mock request handling...")

    try:
        # Load configuration
        config_loader = ConfigLoader("config")
        config = config_loader.load_config()

        # Get container
        container = get_container()

        # Get controllers
        search_controller = container.resolve(SearchController)
        share_controller = container.resolve(ShareController)

        # Test search request
        search_request = {
            "method": "POST",
            "path": "/api/search",
            "body": {
                "address": {
                    "street": "Musterstraße",
                    "house_number": "123",
                    "city": "Berlin",
                    "postal_code": "10115",
                    "country": "DE",
                }
            },
        }

        search_result = await search_controller.handle_request(search_request)
        print(f"✓ Search request handled")
        print(f"  Status: {search_result.get('status', 'unknown')}")

        # Test share request (will fail without valid token, but should handle gracefully)
        share_request = {"method": "GET", "path": "/api/share/test-token", "path_params": {"share_token": "test-token"}}

        share_result = await share_controller.handle_request(share_request)
        print(f"✓ Share request handled")
        print(f"  Status: {share_result.get('status', 'unknown')}")

        return True

    except Exception as e:
        print(f"✗ Mock request handling failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("Container Deployment Test Suite")
    print("=" * 40)

    tests = [test_container_configuration, test_dependency_injection, test_mock_request]

    results = []
    for test in tests:
        result = await test()
        results.append(result)

    print("\n" + "=" * 40)
    print("Test Results:")
    print(f"Passed: {sum(results)}/{len(results)}")

    if all(results):
        print("✓ All tests passed! Container deployment is ready.")
        return 0
    else:
        print("✗ Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
