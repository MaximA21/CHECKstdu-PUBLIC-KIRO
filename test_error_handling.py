#!/usr/bin/env python3
"""Simple test for error handling system."""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.shared.exceptions import ErrorCategory, ErrorSeverity, InvalidAddressException, ProviderUnavailableException


def test_exception_hierarchy():
    """Test the exception hierarchy."""
    print("Testing exception hierarchy...")

    # Test InvalidAddressException
    try:
        raise InvalidAddressException("Test address error", address="123 Test St")
    except InvalidAddressException as e:
        print(f"✅ InvalidAddressException: {e.error_code}")
        print(f"   Severity: {e.severity.value}")
        print(f"   Category: {e.category.value}")
        print(f"   Address: {e.address}")
        print(f"   User Message: {e.user_message}")
        print()

    # Test ProviderUnavailableException
    try:
        raise ProviderUnavailableException("Test provider error", provider_name="test_provider")
    except ProviderUnavailableException as e:
        print(f"✅ ProviderUnavailableException: {e.error_code}")
        print(f"   Severity: {e.severity.value}")
        print(f"   Category: {e.category.value}")
        print(f"   Provider: {e.provider_name}")
        print(f"   Recoverable: {e.recoverable}")
        print()

    print("Exception hierarchy test completed!")


if __name__ == "__main__":
    test_exception_hierarchy()
