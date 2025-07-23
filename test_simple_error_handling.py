#!/usr/bin/env python3
"""Simple test for core error handling functionality."""

import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test the core exception functionality
from src.shared.exceptions.base import (
    BaseApplicationException,
    ValidationException,
    ExternalServiceException,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
)
from src.shared.exceptions.domain import InvalidAddressException, ProviderUnavailableException


def test_base_exceptions():
    """Test base exception functionality."""
    print("=== Testing Base Exceptions ===")

    # Test BaseApplicationException
    context = ErrorContext(request_id="test_req_123", operation="test_operation", component="test_component")

    error = BaseApplicationException(
        "Test error message", severity=ErrorSeverity.HIGH, category=ErrorCategory.SYSTEM, context=context, recoverable=True
    )

    print(f"Error Code: {error.error_code}")
    print(f"Severity: {error.severity.value}")
    print(f"Category: {error.category.value}")
    print(f"Recoverable: {error.recoverable}")
    print(f"User Message: {error.user_message}")

    # Test serialization
    error_dict = error.to_dict()
    print(f"Serialized keys: {list(error_dict.keys())}")

    print("✅ Base exceptions test passed\n")


def test_validation_exception():
    """Test validation exception with field errors."""
    print("=== Testing Validation Exception ===")

    error = ValidationException(
        "Validation failed", field_errors={"email": ["Invalid email format"], "age": ["Must be between 18 and 100"]}
    )

    print(f"Error Code: {error.error_code}")
    print(f"Has Field Errors: {error.has_field_errors()}")
    print(f"Field Errors: {error.field_errors}")

    # Test adding field error
    error.add_field_error("phone", "Invalid phone number")
    print(f"Updated Field Errors: {error.field_errors}")

    print("✅ Validation exception test passed\n")


def test_domain_exceptions():
    """Test domain-specific exceptions."""
    print("=== Testing Domain Exceptions ===")

    # Test InvalidAddressException
    addr_error = InvalidAddressException("Invalid address format", address="123 Invalid Street")

    print(f"Address Error - Code: {addr_error.error_code}")
    print(f"Address Error - Severity: {addr_error.severity.value}")
    print(f"Address Error - Category: {addr_error.category.value}")
    print(f"Address Error - Address: {addr_error.address}")

    # Test ProviderUnavailableException
    provider_error = ProviderUnavailableException("Provider service is down", provider_name="test_provider")

    print(f"Provider Error - Code: {provider_error.error_code}")
    print(f"Provider Error - Severity: {provider_error.severity.value}")
    print(f"Provider Error - Category: {provider_error.category.value}")
    print(f"Provider Error - Provider: {provider_error.provider_name}")
    print(f"Provider Error - Recoverable: {provider_error.recoverable}")

    print("✅ Domain exceptions test passed\n")


def test_error_context():
    """Test error context functionality."""
    print("=== Testing Error Context ===")

    context = ErrorContext(
        request_id="req_456",
        user_id="user_789",
        session_id="session_abc",
        operation="search_offers",
        component="provider_service",
        additional_data={"provider": "test_provider", "retry_count": 2},
    )

    error = BaseApplicationException("Test error with context", context=context)

    error_dict = error.to_dict()
    print(f"Request ID: {error_dict['request_id']}")
    print(f"User ID: {error_dict['user_id']}")
    print(f"Session ID: {error_dict['session_id']}")
    print(f"Operation: {error_dict['operation']}")
    print(f"Component: {error_dict['component']}")
    print(f"Additional Data: {error_dict['additional_data']}")

    print("✅ Error context test passed\n")


def test_lambda_response_format():
    """Test Lambda-compatible error response format."""
    print("=== Testing Lambda Response Format ===")

    # Simulate a Lambda error handler response
    error = ProviderUnavailableException("Provider temporarily unavailable", provider_name="test_provider")

    # Create Lambda-style response
    status_code = 502  # Bad Gateway for external service errors
    response_body = {
        "error": True,
        "error_code": error.error_code,
        "message": error.user_message,
        "timestamp": error.context.timestamp.isoformat(),
        "request_id": error.context.request_id,
        "retryable": error.recoverable,
    }

    lambda_response = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Error-Code": error.error_code,
            "X-Request-ID": error.context.request_id or "unknown",
        },
        "body": json.dumps(response_body),
    }

    print(f"Status Code: {lambda_response['statusCode']}")
    print(f"Headers: {lambda_response['headers']}")
    print(f"Body: {lambda_response['body']}")

    # Verify JSON is valid
    parsed_body = json.loads(lambda_response["body"])
    assert parsed_body["error"] == True
    assert "error_code" in parsed_body
    assert "message" in parsed_body

    print("✅ Lambda response format test passed\n")


def main():
    """Run all tests."""
    print("Starting simple error handling tests...\n")

    try:
        test_base_exceptions()
        test_validation_exception()
        test_domain_exceptions()
        test_error_context()
        test_lambda_response_format()

        print("🎉 All simple error handling tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
