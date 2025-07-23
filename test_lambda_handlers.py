#!/usr/bin/env python3
"""Test script for Lambda handlers with dependency injection."""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_connect_handler():
    """Test the connect handler."""
    print("Testing connect handler...")

    # Mock event
    event = {
        "requestContext": {"connectionId": "test-connection-123"},
        "queryStringParameters": {"street": "Teststraße", "houseNumber": "1", "city": "Berlin", "postalCode": "10115"},
    }

    try:
        # Import and test the original Lambda function
        sys.path.append("lambda_functions/connect_handler")
        from lambda_functions.connect_handler.connect_handler import lambda_handler

        result = lambda_handler(event, None)
        print(f"Connect handler result: {json.dumps(result, indent=2)}")
        print("✅ Connect handler test passed")
        return True

    except Exception as e:
        print(f"❌ Connect handler test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_disconnect_handler():
    """Test the disconnect handler."""
    print("\nTesting disconnect handler...")

    # Mock event
    event = {"requestContext": {"connectionId": "test-connection-123"}}

    try:
        # Import and test the original Lambda function
        sys.path.append("lambda_functions/disconnect_handler ")
        from lambda_functions.disconnect_handler.disconnect_handler import lambda_handler

        result = lambda_handler(event, None)
        print(f"Disconnect handler result: {json.dumps(result, indent=2)}")
        print("✅ Disconnect handler test passed")
        return True

    except Exception as e:
        print(f"❌ Disconnect handler test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_authorizer_handler():
    """Test the authorizer handler."""
    print("\nTesting authorizer handler...")

    # Mock event
    event = {
        "methodArn": "arn:aws:execute-api:us-east-1:123456789012:abcdef123/test/GET/resource",
        "queryStringParameters": {
            "token": "test-token-123",
            "street": "Teststraße",
            "houseNumber": "1",
            "city": "Berlin",
            "postalCode": "10115",
        },
    }

    try:
        # Import and test the original Lambda function
        sys.path.append("lambda_functions/authorizer")
        from lambda_functions.authorizer.authorizer import lambda_handler

        result = lambda_handler(event, None)
        print(f"Authorizer handler result: {json.dumps(result, indent=2)}")
        print("✅ Authorizer handler test passed")
        return True

    except Exception as e:
        print(f"❌ Authorizer handler test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_address_normalizer_handler():
    """Test the address normalizer handler."""
    print("\nTesting address normalizer handler...")

    # Mock event
    event = {"address": {"street": "Müllerstraße", "house_number": "1", "city": "München", "postal_code": "80331"}}

    try:
        # Import and test the original Lambda function
        sys.path.append("lambda_functions/address_normalizer")
        from lambda_functions.address_normalizer.address_normalizer import lambda_handler

        result = lambda_handler(event, None)
        print(f"Address normalizer result: {json.dumps(result, indent=2)}")
        print("✅ Address normalizer handler test passed")
        return True

    except Exception as e:
        print(f"❌ Address normalizer handler test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 Testing Lambda handlers with dependency injection...")

    tests = [test_connect_handler, test_disconnect_handler, test_authorizer_handler, test_address_normalizer_handler]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
