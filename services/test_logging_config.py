"""
Comprehensive tests for the centralized logging configuration module.

This test suite covers:
- Unit tests for the centralized logging configuration module
- Log level filtering behavior with different environment variables
- Verification that log messages appear at correct levels across all functions
- Performance impact testing of different logging levels
"""

import json
import logging
import os
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from io import StringIO
from unittest.mock import MagicMock, patch

# Add both src and root directory to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(root_dir, "src")
sys.path.insert(0, root_dir)
sys.path.insert(0, src_dir)

from src.application.interfaces.logging import LogLevel
from src.infrastructure.logging.logger_factory import LoggerFactory


class TestLoggingConfig(unittest.TestCase):
    """Test cases for logging configuration."""

    def setUp(self):
        """Set up test environment."""
        # Clear any existing loggers
        logging.getLogger().handlers.clear()

    def tearDown(self):
        """Clean up after tests."""
        # Clear environment variables
        for key in ["LOG_LEVEL", "STRUCTURED_LOGS"]:
            if key in os.environ:
                del os.environ[key]

    def test_log_config_from_environment_default(self):
        """Test LogConfig creation with default values."""
        config = LogConfig.from_environment()
        self.assertEqual(config.level, "INFO")
        self.assertFalse(config.enable_structured)

    def test_log_config_from_environment_custom(self):
        """Test LogConfig creation with custom environment values."""
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["STRUCTURED_LOGS"] = "true"

        config = LogConfig.from_environment()
        self.assertEqual(config.level, "DEBUG")
        self.assertTrue(config.enable_structured)

    def test_get_log_level_default(self):
        """Test get_log_level with default INFO level."""
        level = get_log_level()
        self.assertEqual(level, logging.INFO)

    def test_get_log_level_debug(self):
        """Test get_log_level with DEBUG level."""
        os.environ["LOG_LEVEL"] = "DEBUG"
        level = get_log_level()
        self.assertEqual(level, logging.DEBUG)

    def test_get_log_level_invalid(self):
        """Test get_log_level with invalid level falls back to INFO."""
        os.environ["LOG_LEVEL"] = "INVALID"
        level = get_log_level()
        self.assertEqual(level, logging.INFO)

    def test_configure_logger_basic(self):
        """Test basic logger configuration."""
        logger = configure_logger("test_logger")
        self.assertEqual(logger.name, "test_logger")
        self.assertEqual(logger.level, logging.INFO)
        self.assertEqual(len(logger.handlers), 1)

    def test_configure_logger_debug_level(self):
        """Test logger configuration with DEBUG level."""
        os.environ["LOG_LEVEL"] = "DEBUG"
        logger = configure_logger("debug_logger")
        self.assertEqual(logger.level, logging.DEBUG)

    def test_create_lambda_logger(self):
        """Test Lambda-specific logger creation."""
        logger = create_lambda_logger("test_function")
        self.assertEqual(logger.name, "lambda.test_function")
        self.assertIsInstance(logger, logging.Logger)

    def test_structured_formatter(self):
        """Test structured JSON formatter."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=1, msg="Test message", args=(), exc_info=None
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["message"], "Test message")
        self.assertEqual(parsed["logger"], "test")
        self.assertIn("timestamp", parsed)

    def test_safe_json_log_success(self):
        """Test safe JSON logging with valid data."""
        # Create a logger with a string handler for testing
        logger = logging.getLogger("json_test")
        logger.setLevel(logging.INFO)

        # Clear any existing handlers
        logger.handlers.clear()

        # Add a string handler to capture output
        string_handler = logging.StreamHandler(StringIO())
        string_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        string_handler.setFormatter(formatter)
        logger.addHandler(string_handler)

        safe_json_log(logger, logging.INFO, "Test data", {"key": "value"})

        # Get the captured output
        output = string_handler.stream.getvalue()
        self.assertIn("Test data", output)
        self.assertIn('{"key": "value"}', output)

    def test_safe_json_log_serialization_error(self):
        """Test safe JSON logging with non-serializable data."""
        # Create a logger with a string handler for testing
        logger = logging.getLogger("json_error_test")
        logger.setLevel(logging.INFO)

        # Clear any existing handlers
        logger.handlers.clear()

        # Add a string handler to capture output
        string_handler = logging.StreamHandler(StringIO())
        string_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        string_handler.setFormatter(formatter)
        logger.addHandler(string_handler)

        # Create non-serializable object
        class NonSerializable:
            def __init__(self):
                self.circular_ref = self

        safe_json_log(logger, logging.INFO, "Test data", NonSerializable())

        # Get the captured output
        output = string_handler.stream.getvalue()
        self.assertIn("Test data", output)
        # Should handle serialization error gracefully

    def test_get_lambda_logger_convenience(self):
        """Test convenience function for Lambda logger setup."""
        logger = get_lambda_logger("convenience_test")
        self.assertEqual(logger.name, "lambda.convenience_test")
        self.assertIsInstance(logger, logging.Logger)


class TestLogLevelFiltering(unittest.TestCase):
    """Test log level filtering behavior with different environment variables."""

    def setUp(self):
        """Set up test environment."""
        # Clear any existing loggers
        logging.getLogger().handlers.clear()
        self.test_stream = StringIO()

    def tearDown(self):
        """Clean up after tests."""
        # Clear environment variables
        for key in ["LOG_LEVEL", "STRUCTURED_LOGS"]:
            if key in os.environ:
                del os.environ[key]
        # Clear all loggers
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.startswith("test_"):
                logger = logging.getLogger(name)
                logger.handlers.clear()

    @contextmanager
    def capture_logs(self, logger_name, log_level_env=None):
        """Context manager to capture log output for testing."""
        if log_level_env:
            os.environ["LOG_LEVEL"] = log_level_env

        logger = configure_logger(logger_name)

        # Replace handler with our test handler
        logger.handlers.clear()
        test_handler = logging.StreamHandler(self.test_stream)
        test_handler.setLevel(get_log_level())
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        test_handler.setFormatter(formatter)
        logger.addHandler(test_handler)

        yield logger

        if log_level_env and "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

    def test_debug_level_filtering(self):
        """Test that DEBUG level shows all messages."""
        with self.capture_logs("test_debug", "DEBUG") as logger:
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            output = self.test_stream.getvalue()
            self.assertIn("DEBUG - Debug message", output)
            self.assertIn("INFO - Info message", output)
            self.assertIn("WARNING - Warning message", output)
            self.assertIn("ERROR - Error message", output)

    def test_info_level_filtering(self):
        """Test that INFO level filters out DEBUG messages."""
        with self.capture_logs("test_info", "INFO") as logger:
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            output = self.test_stream.getvalue()
            self.assertNotIn("DEBUG - Debug message", output)
            self.assertIn("INFO - Info message", output)
            self.assertIn("WARNING - Warning message", output)
            self.assertIn("ERROR - Error message", output)

    def test_warning_level_filtering(self):
        """Test that WARNING level filters out DEBUG and INFO messages."""
        with self.capture_logs("test_warning", "WARNING") as logger:
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            output = self.test_stream.getvalue()
            self.assertNotIn("DEBUG - Debug message", output)
            self.assertNotIn("INFO - Info message", output)
            self.assertIn("WARNING - Warning message", output)
            self.assertIn("ERROR - Error message", output)

    def test_error_level_filtering(self):
        """Test that ERROR level only shows ERROR messages."""
        with self.capture_logs("test_error", "ERROR") as logger:
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")

            output = self.test_stream.getvalue()
            self.assertNotIn("DEBUG - Debug message", output)
            self.assertNotIn("INFO - Info message", output)
            self.assertNotIn("WARNING - Warning message", output)
            self.assertIn("ERROR - Error message", output)

    def test_case_insensitive_log_levels(self):
        """Test that log level environment variables are case insensitive."""
        test_cases = ["debug", "DEBUG", "Debug", "DeBuG"]

        for case in test_cases:
            with self.subTest(case=case):
                os.environ["LOG_LEVEL"] = case
                level = get_log_level()
                self.assertEqual(level, logging.DEBUG)
                del os.environ["LOG_LEVEL"]

    def test_invalid_log_level_fallback(self):
        """Test that invalid log levels fall back to INFO."""
        invalid_levels = ["TRACE", "VERBOSE", "CRITICAL", "INVALID", "123", ""]

        for invalid_level in invalid_levels:
            with self.subTest(level=invalid_level):
                os.environ["LOG_LEVEL"] = invalid_level
                level = get_log_level()
                self.assertEqual(level, logging.INFO)
                del os.environ["LOG_LEVEL"]


class TestLogMessageLevels(unittest.TestCase):
    """Test that log messages appear at correct levels across different scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.test_stream = StringIO()

    def tearDown(self):
        """Clean up after tests."""
        # Clear environment variables
        for key in ["LOG_LEVEL", "STRUCTURED_LOGS"]:
            if key in os.environ:
                del os.environ[key]
        # Clear all loggers
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.startswith("test_"):
                logger = logging.getLogger(name)
                logger.handlers.clear()

    def create_test_logger(self, name, level="DEBUG"):
        """Create a test logger with captured output."""
        os.environ["LOG_LEVEL"] = level
        logger = configure_logger(name)

        # Replace handler with our test handler
        logger.handlers.clear()
        test_handler = logging.StreamHandler(self.test_stream)
        test_handler.setLevel(get_log_level())
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        test_handler.setFormatter(formatter)
        logger.addHandler(test_handler)

        return logger

    def test_lambda_function_startup_logging(self):
        """Test that Lambda function startup uses INFO level."""
        logger = self.create_test_logger("test_lambda_startup")

        # Simulate Lambda function startup pattern
        logger.info("Lambda function started")
        logger.debug("Event received: {...}")

        output = self.test_stream.getvalue()
        self.assertIn("INFO - Lambda function started", output)
        self.assertIn("DEBUG - Event received", output)

    def test_error_handling_logging(self):
        """Test that errors are logged at ERROR level with context."""
        logger = self.create_test_logger("test_error_handling")

        # Simulate error handling pattern
        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.error(f"Operation failed: {str(e)}")
            logger.debug("Detailed error context")

        output = self.test_stream.getvalue()
        self.assertIn("ERROR - Operation failed: Test error", output)
        self.assertIn("DEBUG - Detailed error context", output)

    def test_performance_logging_levels(self):
        """Test that performance metrics use appropriate levels."""
        logger = self.create_test_logger("test_performance")

        # Simulate performance logging pattern
        execution_time = 150.5
        logger.info(f"Processing completed in {execution_time:.1f}ms")
        logger.debug("Detailed timing breakdown: query=50ms, processing=100ms")

        output = self.test_stream.getvalue()
        self.assertIn("INFO - Processing completed in 150.5ms", output)
        self.assertIn("DEBUG - Detailed timing breakdown", output)

    def test_business_logic_logging_levels(self):
        """Test that business logic uses appropriate levels."""
        logger = self.create_test_logger("test_business")

        # Simulate business logic logging
        logger.info("API request successful")
        logger.debug("Request details: method=GET, path=/api/test")
        logger.info("Found 5 results")
        logger.debug("Result details: {...}")

        output = self.test_stream.getvalue()
        self.assertIn("INFO - API request successful", output)
        self.assertIn("DEBUG - Request details", output)
        self.assertIn("INFO - Found 5 results", output)
        self.assertIn("DEBUG - Result details", output)

    def test_structured_logging_with_context(self):
        """Test structured logging with context information."""
        os.environ["STRUCTURED_LOGS"] = "true"

        # Create logger with structured formatter
        logger = configure_logger("test_structured")

        # Replace handler with structured formatter
        logger.handlers.clear()
        test_handler = logging.StreamHandler(self.test_stream)
        test_handler.setLevel(logging.INFO)
        structured_formatter = StructuredFormatter()
        test_handler.setFormatter(structured_formatter)
        logger.addHandler(test_handler)

        # Test log_with_context function
        log_with_context(logger, logging.INFO, "Operation completed", {"duration_ms": 100, "items_processed": 5})

        output = self.test_stream.getvalue()
        # Should contain JSON structure
        self.assertIn('"message": "Operation completed"', output)
        self.assertIn('"level": "INFO"', output)
        self.assertIn('"duration_ms": 100', output)
        self.assertIn('"items_processed": 5', output)

    def test_safe_json_logging_truncation(self):
        """Test that safe JSON logging handles large data appropriately."""
        logger = self.create_test_logger("test_json_truncation")

        # Create large data that should be truncated
        large_data = {"key": "x" * 2000}  # Large string
        safe_json_log(logger, logging.DEBUG, "Large data", large_data, max_length=100)

        output = self.test_stream.getvalue()
        self.assertIn("DEBUG - Large data", output)
        self.assertIn("[truncated]", output)


class TestPerformanceImpact(unittest.TestCase):
    """Test performance impact of different logging levels."""

    def setUp(self):
        """Set up test environment."""
        self.test_iterations = 1000

    def tearDown(self):
        """Clean up after tests."""
        # Clear environment variables
        for key in ["LOG_LEVEL", "STRUCTURED_LOGS"]:
            if key in os.environ:
                del os.environ[key]
        # Clear all loggers
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.startswith("perf_test_"):
                logger = logging.getLogger(name)
                logger.handlers.clear()

    def measure_logging_performance(self, log_level, enable_structured=False):
        """Measure logging performance for a given configuration."""
        os.environ["LOG_LEVEL"] = log_level
        if enable_structured:
            os.environ["STRUCTURED_LOGS"] = "true"

        logger = configure_logger(f"perf_test_{log_level.lower()}")

        # Measure time for multiple log operations
        start_time = time.time()

        for i in range(self.test_iterations):
            logger.debug(f"Debug message {i}")
            logger.info(f"Info message {i}")
            logger.warning(f"Warning message {i}")
            logger.error(f"Error message {i}")

        end_time = time.time()
        return (end_time - start_time) * 1000  # Return milliseconds

    def test_debug_level_performance(self):
        """Test performance impact of DEBUG level logging."""
        debug_time = self.measure_logging_performance("DEBUG")
        info_time = self.measure_logging_performance("INFO")

        # DEBUG level should be slower due to more messages being processed
        self.assertGreater(debug_time, info_time * 0.5)  # Allow some variance

        # But should still be reasonable (less than 1 second for 1000 iterations)
        self.assertLess(debug_time, 1000)

    def test_info_level_performance(self):
        """Test performance impact of INFO level logging."""
        info_time = self.measure_logging_performance("INFO")
        warning_time = self.measure_logging_performance("WARNING")

        # INFO level should be slower than WARNING due to more messages
        self.assertGreater(info_time, warning_time * 0.5)

        # Should be reasonable performance
        self.assertLess(info_time, 500)

    def test_structured_logging_performance(self):
        """Test performance impact of structured logging."""
        regular_time = self.measure_logging_performance("DEBUG", enable_structured=False)
        structured_time = self.measure_logging_performance("DEBUG", enable_structured=True)

        # Structured logging should be slower due to JSON formatting
        # But not excessively so (less than 3x slower)
        self.assertLess(structured_time, regular_time * 3)

    def test_safe_json_logging_performance(self):
        """Test performance impact of safe JSON logging."""
        logger = configure_logger("perf_test_json")

        # Test data
        test_data = {"key": "value", "number": 123, "list": [1, 2, 3]}

        # Measure safe_json_log performance
        start_time = time.time()

        for i in range(100):  # Fewer iterations for JSON operations
            safe_json_log(logger, logging.DEBUG, f"Test data {i}", test_data)

        end_time = time.time()
        json_time = (end_time - start_time) * 1000

        # Should complete in reasonable time (less than 100ms for 100 operations)
        self.assertLess(json_time, 100)

    def test_concurrent_logging_performance(self):
        """Test logging performance under concurrent access."""
        logger = configure_logger("perf_test_concurrent")
        results = []

        def log_worker():
            start_time = time.time()
            for i in range(100):
                logger.info(f"Concurrent message {i}")
            end_time = time.time()
            results.append((end_time - start_time) * 1000)

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=log_worker)
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        total_time = (time.time() - start_time) * 1000

        # Concurrent logging should complete in reasonable time
        self.assertLess(total_time, 1000)  # Less than 1 second

        # All threads should have completed
        self.assertEqual(len(results), 5)

        # Individual thread times should be reasonable
        for thread_time in results:
            self.assertLess(thread_time, 500)


class TestLoggerIntegration(unittest.TestCase):
    """Test logger integration across different Lambda function patterns."""

    def setUp(self):
        """Set up test environment."""
        self.test_stream = StringIO()

    def tearDown(self):
        """Clean up after tests."""
        # Clear environment variables
        for key in ["LOG_LEVEL", "STRUCTURED_LOGS"]:
            if key in os.environ:
                del os.environ[key]
        # Clear all loggers
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.startswith("integration_test_"):
                logger = logging.getLogger(name)
                logger.handlers.clear()

    def create_integration_logger(self, function_name, level="INFO"):
        """Create a logger for integration testing."""
        os.environ["LOG_LEVEL"] = level
        logger = get_lambda_logger(function_name)

        # Replace handler with our test handler
        logger.handlers.clear()
        test_handler = logging.StreamHandler(self.test_stream)
        test_handler.setLevel(get_log_level())
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        test_handler.setFormatter(formatter)
        logger.addHandler(test_handler)

        return logger

    def test_lambda_handler_pattern(self):
        """Test typical Lambda handler logging pattern."""
        logger = self.create_integration_logger("integration_test_handler")

        # Simulate Lambda handler execution
        logger.info("Lambda function started")
        safe_json_log(logger, logging.DEBUG, "Event received", {"test": "data"})

        try:
            # Simulate business logic
            logger.debug("Processing request")
            logger.info("Operation completed successfully")
        except Exception as e:
            logger.error(f"Operation failed: {str(e)}")

        output = self.test_stream.getvalue()
        self.assertIn("lambda.integration_test_handler - INFO - Lambda function started", output)
        self.assertIn("lambda.integration_test_handler - INFO - Operation completed successfully", output)

    def test_api_gateway_pattern(self):
        """Test API Gateway Lambda logging pattern."""
        logger = self.create_integration_logger("integration_test_api")

        # Simulate API Gateway Lambda
        start_time = time.time()
        logger.info("API request started")

        # Simulate request processing
        logger.debug("Validating request parameters")
        logger.debug("Querying database")

        # Simulate response
        execution_time = (time.time() - start_time) * 1000
        log_with_context(
            logger, logging.INFO, "API request completed", {"status_code": 200, "execution_time_ms": round(execution_time, 1)}
        )

        output = self.test_stream.getvalue()
        self.assertIn("lambda.integration_test_api - INFO - API request started", output)
        self.assertIn("lambda.integration_test_api - INFO - API request completed", output)

    def test_event_driven_pattern(self):
        """Test event-driven Lambda logging pattern."""
        logger = self.create_integration_logger("integration_test_event", "DEBUG")

        # Simulate event processing
        logger.info("Event processing started")
        safe_json_log(logger, logging.DEBUG, "Event details", {"eventName": "test-event", "records": [{"id": "123"}]})

        # Process each record
        for i in range(3):
            logger.debug(f"Processing record {i+1}")
            logger.info(f"Record {i+1} processed successfully")

        logger.info("Event processing completed")

        output = self.test_stream.getvalue()
        self.assertIn("Event processing started", output)
        self.assertIn("Event processing completed", output)
        self.assertIn("Record 1 processed successfully", output)
        self.assertIn("Record 2 processed successfully", output)
        self.assertIn("Record 3 processed successfully", output)

    def test_multiple_logger_isolation(self):
        """Test that multiple loggers don't interfere with each other."""
        logger1 = self.create_integration_logger("integration_test_1")

        # Create second logger with different stream
        stream2 = StringIO()
        logger2 = get_lambda_logger("integration_test_2")
        logger2.handlers.clear()
        handler2 = logging.StreamHandler(stream2)
        handler2.setLevel(logging.INFO)
        formatter2 = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        handler2.setFormatter(formatter2)
        logger2.addHandler(handler2)

        # Log to both loggers
        logger1.info("Message from logger 1")
        logger2.info("Message from logger 2")

        output1 = self.test_stream.getvalue()
        output2 = stream2.getvalue()

        # Each logger should only contain its own messages
        self.assertIn("Message from logger 1", output1)
        self.assertNotIn("Message from logger 2", output1)

        self.assertIn("Message from logger 2", output2)
        self.assertNotIn("Message from logger 1", output2)


if __name__ == "__main__":
    # Run all test classes
    unittest.main(verbosity=2)
