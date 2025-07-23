#!/usr/bin/env python3
"""
Simple test runner for logging configuration tests.

This script runs the comprehensive logging tests with minimal output,
suitable for CI/CD or quick validation.
"""

import unittest
import sys
import os
from io import StringIO

# Add the services directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the test module
import test_logging_config


def run_tests_quietly():
    """Run tests with minimal output."""
    # Capture stdout to reduce noise from performance tests
    old_stdout = sys.stdout
    sys.stdout = StringIO()

    try:
        # Create test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_logging_config)

        # Run tests
        runner = unittest.TextTestRunner(verbosity=1, stream=old_stdout)
        result = runner.run(suite)

        # Restore stdout
        sys.stdout = old_stdout

        # Print summary
        print(f"\nTest Results:")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")

        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")

        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")

        if result.wasSuccessful():
            print("\n✅ All tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1

    except Exception as e:
        sys.stdout = old_stdout
        print(f"Error running tests: {e}")
        return 1


if __name__ == "__main__":
    exit_code = run_tests_quietly()
    sys.exit(exit_code)
