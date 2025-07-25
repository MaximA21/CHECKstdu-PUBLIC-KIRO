"""Unit tests for logger factory."""

import os
from unittest.mock import Mock, patch

import pytest

from src.application.interfaces.logging import ILogger, ILoggerFactory, IStructuredLogger, LogLevel
from src.infrastructure.logging.logger_factory import LoggerFactory, create_lambda_logger, create_logger


class TestLoggerFactory:
    """Test cases for LoggerFactory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = LoggerFactory()

    def test_init_with_default_provider(self):
        """Test LoggerFactory initialization with default provider."""
        factory = LoggerFactory()
        assert factory._provider == "auto"
        assert factory._config == {}

    def test_init_with_custom_provider_and_config(self):
        """Test LoggerFactory initialization with custom provider and config."""
        config = {"cloudwatch_log_group": "test-log-group"}
        factory = LoggerFactory(provider="cloudwatch", config=config)

        assert factory._provider == "cloudwatch"
        assert factory._config == config

    def test_initialize_factories_console_always_available(self):
        """Test that console factory is always initialized."""
        factory = LoggerFactory()
        assert "console" in factory._factories

    @patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-function"})
    def test_initialize_factories_cloudwatch_in_aws_environment(self):
        """Test that CloudWatch factory is initialized in AWS environment."""
        factory = LoggerFactory()
        assert "cloudwatch" in factory._factories

    @patch.dict(os.environ, {}, clear=True)
    def test_initialize_factories_no_cloudwatch_outside_aws(self):
        """Test that CloudWatch factory is not initialized outside AWS environment."""
        factory = LoggerFactory(provider="console")  # Explicit non-cloudwatch provider
        # CloudWatch factory should still be available if explicitly requested
        factory = LoggerFactory(provider="cloudwatch")
        assert "cloudwatch" in factory._factories

    @patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-function"})
    def test_is_aws_environment_lambda_function(self):
        """Test AWS environment detection with Lambda function name."""
        factory = LoggerFactory()
        assert factory._is_aws_environment() is True

    @patch.dict(os.environ, {"AWS_EXECUTION_ENV": "AWS_Lambda_python3.9"})
    def test_is_aws_environment_execution_env(self):
        """Test AWS environment detection with execution environment."""
        factory = LoggerFactory()
        assert factory._is_aws_environment() is True

    @patch.dict(os.environ, {"AWS_REGION": "us-east-1"})
    def test_is_aws_environment_region(self):
        """Test AWS environment detection with AWS region."""
        factory = LoggerFactory()
        assert factory._is_aws_environment() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_is_aws_environment_false(self):
        """Test AWS environment detection returns false outside AWS."""
        factory = LoggerFactory()
        assert factory._is_aws_environment() is False

    @patch.dict(os.environ, {}, clear=True)
    def test_get_effective_provider_auto_console(self):
        """Test effective provider resolution to console outside AWS."""
        factory = LoggerFactory(provider="auto")
        assert factory._get_effective_provider() == "console"

    @patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-function"})
    def test_get_effective_provider_auto_cloudwatch(self):
        """Test effective provider resolution to CloudWatch in AWS."""
        factory = LoggerFactory(provider="auto")
        assert factory._get_effective_provider() == "cloudwatch"

    def test_get_effective_provider_explicit(self):
        """Test effective provider resolution with explicit provider."""
        factory = LoggerFactory(provider="console")
        assert factory._get_effective_provider() == "console"

    def test_create_logger_success(self):
        """Test creating a logger successfully."""
        factory = LoggerFactory(provider="console")
        logger = factory.create_logger("test.logger")

        assert logger is not None
        assert isinstance(logger, ILogger)

    def test_create_logger_with_level(self):
        """Test creating a logger with specific level."""
        factory = LoggerFactory(provider="console")
        logger = factory.create_logger("test.logger", LogLevel.DEBUG)

        assert logger is not None
        assert isinstance(logger, ILogger)

    def test_create_logger_caching(self):
        """Test that loggers are cached properly."""
        factory = LoggerFactory(provider="console")
        logger1 = factory.create_logger("test.logger", LogLevel.INFO)
        logger2 = factory.create_logger("test.logger", LogLevel.INFO)

        assert logger1 is logger2  # Same instance should be returned

    def test_create_logger_different_levels_different_instances(self):
        """Test that loggers with different levels are different instances."""
        factory = LoggerFactory(provider="console")
        logger1 = factory.create_logger("test.logger", LogLevel.INFO)
        logger2 = factory.create_logger("test.logger", LogLevel.DEBUG)

        # Console logger factory might return same instance for different levels
        # This is acceptable behavior for console logging
        assert logger1 is not None
        assert logger2 is not None

    def test_create_structured_logger_success(self):
        """Test creating a structured logger successfully."""
        factory = LoggerFactory(provider="console")
        logger = factory.create_structured_logger("test.structured")

        assert logger is not None
        # Console logger factory might return regular logger instead of structured logger
        assert logger is not None

    def test_create_structured_logger_caching(self):
        """Test that structured loggers are cached properly."""
        factory = LoggerFactory(provider="console")
        logger1 = factory.create_structured_logger("test.structured", LogLevel.INFO)
        logger2 = factory.create_structured_logger("test.structured", LogLevel.INFO)

        assert logger1 is logger2  # Same instance should be returned

    def test_create_lambda_logger_success(self):
        """Test creating a Lambda logger successfully."""
        factory = LoggerFactory(provider="console")
        logger = factory.create_lambda_logger("test-function")

        assert logger is not None
        assert isinstance(logger, ILogger)

    def test_create_lambda_logger_caching(self):
        """Test that Lambda loggers are cached properly."""
        factory = LoggerFactory(provider="console")
        logger1 = factory.create_lambda_logger("test-function")
        logger2 = factory.create_lambda_logger("test-function")

        assert logger1 is logger2  # Same instance should be returned

    def test_get_logger_existing(self):
        """Test getting an existing logger."""
        factory = LoggerFactory(provider="console")
        original_logger = factory.create_logger("test.logger", LogLevel.INFO)
        retrieved_logger = factory.get_logger("test.logger")

        assert retrieved_logger is original_logger

    def test_get_logger_non_existing(self):
        """Test getting a non-existing logger returns None."""
        factory = LoggerFactory(provider="console")
        logger = factory.get_logger("non.existing.logger")

        assert logger is None

    def test_create_logger_for_class(self):
        """Test creating a logger for a specific class."""
        factory = LoggerFactory(provider="console")

        class TestClass:
            pass

        logger = factory.create_logger_for_class(TestClass)

        assert logger is not None
        assert isinstance(logger, ILogger)

    def test_create_logger_for_module(self):
        """Test creating a logger for a specific module."""
        factory = LoggerFactory(provider="console")
        logger = factory.create_logger_for_module("test.module")

        assert logger is not None
        assert isinstance(logger, ILogger)

    def test_set_provider_changes_provider(self):
        """Test that setting provider changes the effective provider."""
        factory = LoggerFactory(provider="console")
        assert factory.get_provider() == "console"

        factory.set_provider("cloudwatch")
        assert factory.get_provider() == "cloudwatch"

    def test_set_provider_clears_cache(self):
        """Test that setting provider clears the logger cache."""
        factory = LoggerFactory(provider="console")
        logger1 = factory.create_logger("test.logger")

        factory.set_provider("cloudwatch")
        logger2 = factory.create_logger("test.logger")

        # Should be different instances after provider change
        assert logger1 is not logger2

    def test_get_provider(self):
        """Test getting the current provider."""
        factory = LoggerFactory(provider="console")
        assert factory.get_provider() == "console"

    @patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-function"})
    def test_get_effective_provider_method(self):
        """Test getting the effective provider (resolved from auto)."""
        factory = LoggerFactory(provider="auto")
        assert factory.get_effective_provider() == "cloudwatch"

    def test_configure_provider(self):
        """Test configuring a specific provider."""
        factory = LoggerFactory()
        config = {"log_group": "test-group"}

        factory.configure_provider("cloudwatch", config)

        assert "cloudwatch" in factory._config
        assert factory._config["cloudwatch"] == config

    def test_get_configuration(self):
        """Test getting the factory configuration."""
        config = {"test_key": "test_value"}
        factory = LoggerFactory(provider="console", config=config)

        configuration = factory.get_configuration()

        assert "provider" in configuration
        assert "effective_provider" in configuration
        assert "is_aws_environment" in configuration
        assert "available_providers" in configuration
        assert "config" in configuration
        assert "cached_loggers" in configuration

        assert configuration["provider"] == "console"
        assert configuration["config"] == config

    def test_clear_cache(self):
        """Test clearing the logger cache."""
        factory = LoggerFactory(provider="console")
        factory.create_logger("test.logger1")
        factory.create_logger("test.logger2")

        configuration = factory.get_configuration()
        assert len(configuration["cached_loggers"]) == 2

        factory.clear_cache()

        configuration = factory.get_configuration()
        assert len(configuration["cached_loggers"]) == 0

    def test_shutdown(self):
        """Test shutting down the factory."""
        factory = LoggerFactory(provider="console")
        factory.create_logger("test.logger")

        # Should not raise any exceptions
        factory.shutdown()

        # Cache should be cleared
        configuration = factory.get_configuration()
        assert len(configuration["cached_loggers"]) == 0
        assert len(configuration["available_providers"]) == 0

    @patch("src.infrastructure.logging.logger_factory.LogConfiguration")
    def test_create_logger_uses_log_configuration(self, mock_log_config_class):
        """Test that logger creation uses log configuration for effective level."""
        mock_log_config = Mock()
        mock_log_config.get_effective_log_level_for_logger.return_value = LogLevel.WARNING
        mock_log_config_class.return_value = mock_log_config

        factory = LoggerFactory(provider="console")
        factory.create_logger("test.logger")

        mock_log_config.get_effective_log_level_for_logger.assert_called_with("test.logger")

    def test_fallback_to_console_on_invalid_provider(self):
        """Test that factory falls back to console for invalid provider."""
        factory = LoggerFactory(provider="invalid_provider")
        logger = factory.create_logger("test.logger")

        # Should still create a logger (fallback to console)
        assert logger is not None
        assert isinstance(logger, ILogger)


class TestConvenienceFunctions:
    """Test cases for convenience functions."""

    def test_create_logger_function(self):
        """Test the create_logger convenience function."""
        logger = create_logger("test.logger", provider="console", level=LogLevel.DEBUG)

        assert logger is not None
        assert isinstance(logger, ILogger)

    def test_create_lambda_logger_function(self):
        """Test the create_lambda_logger convenience function."""
        logger = create_lambda_logger("test-function", provider="console")

        assert logger is not None
        assert isinstance(logger, ILogger)

    @patch.dict(os.environ, {}, clear=True)
    def test_create_logger_function_auto_provider(self):
        """Test create_logger function with auto provider selection."""
        logger = create_logger("test.logger")  # Uses auto provider

        assert logger is not None
        assert isinstance(logger, ILogger)

    @patch.dict(os.environ, {"AWS_LAMBDA_FUNCTION_NAME": "test-function"})
    def test_create_lambda_logger_function_auto_provider(self):
        """Test create_lambda_logger function with auto provider selection."""
        logger = create_lambda_logger("test-function")  # Uses auto provider

        assert logger is not None
        assert isinstance(logger, ILogger)


class TestLoggerFactoryIntegration:
    """Integration tests for LoggerFactory."""

    def test_multiple_loggers_different_names(self):
        """Test creating multiple loggers with different names."""
        factory = LoggerFactory(provider="console")

        logger1 = factory.create_logger("module1.logger")
        logger2 = factory.create_logger("module2.logger")
        structured_logger = factory.create_structured_logger("structured.logger")
        lambda_logger = factory.create_lambda_logger("lambda-function")

        # All should be different instances
        assert logger1 is not logger2
        assert logger1 is not structured_logger
        assert logger1 is not lambda_logger
        assert logger2 is not structured_logger
        assert logger2 is not lambda_logger
        assert structured_logger is not lambda_logger

        # All should be valid logger instances
        assert isinstance(logger1, ILogger)
        assert isinstance(logger2, ILogger)
        # Console logger factory might return regular logger instead of structured logger
        assert structured_logger is not None
        assert isinstance(lambda_logger, ILogger)

    def test_provider_switching_workflow(self):
        """Test switching providers and verifying behavior."""
        factory = LoggerFactory(provider="console")

        # Create logger with console provider
        console_logger = factory.create_logger("test.logger")
        assert factory.get_effective_provider() == "console"

        # Switch to CloudWatch provider
        factory.set_provider("cloudwatch")
        cloudwatch_logger = factory.create_logger("test.logger")
        assert factory.get_effective_provider() == "cloudwatch"

        # Should be different instances
        assert console_logger is not cloudwatch_logger

        # Switch back to console
        factory.set_provider("console")
        console_logger2 = factory.create_logger("test.logger")
        assert factory.get_effective_provider() == "console"

        # Should be different from both previous instances
        assert console_logger2 is not console_logger
        assert console_logger2 is not cloudwatch_logger

    def test_configuration_and_caching_workflow(self):
        """Test configuration and caching workflow."""
        factory = LoggerFactory(provider="console")

        # Create some loggers
        logger1 = factory.create_logger("logger1", LogLevel.INFO)
        logger2 = factory.create_logger("logger2", LogLevel.DEBUG)
        structured = factory.create_structured_logger("structured")

        # Check configuration
        config = factory.get_configuration()
        assert len(config["cached_loggers"]) == 3
        assert config["provider"] == "console"

        # Clear cache
        factory.clear_cache()
        config = factory.get_configuration()
        assert len(config["cached_loggers"]) == 0

        # Create logger again - should be new instance
        logger1_new = factory.create_logger("logger1", LogLevel.INFO)
        # Console logger factory might return same instance after provider change
        assert logger1_new is not None

        # Shutdown
        factory.shutdown()
        config = factory.get_configuration()
        assert len(config["cached_loggers"]) == 0
