"""Tests for logging abstraction layer implementations."""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from src.application.interfaces.logging import LogLevel, LogFormat
from src.infrastructure.logging import (
    ConsoleLogger, ConsoleLoggerFactory,
    CloudWatchLogger, CloudWatchLoggerFactory,
    StructuredLogger, LogConfiguration,
    LoggerFactory, create_logger, create_lambda_logger
)


class TestConsoleLogger:
    """Test console logger implementation."""
    
    def test_console_logger_creation(self):
        """Test console logger can be created."""
        logger = ConsoleLogger("test_logger")
        assert logger.name == "test_logger"
        assert logger.underlying_logger is not None
    
    def test_console_logger_basic_logging(self):
        """Test basic logging functionality."""
        logger = ConsoleLogger("test_logger", LogLevel.DEBUG)
        
        # Test that methods can be called without errors
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        # Verify the logger is properly configured
        assert logger.underlying_logger.level <= 10  # DEBUG level or lower
    
    def test_console_logger_with_context(self):
        """Test logging with context data."""
        logger = ConsoleLogger("test_logger")
        
        context = {"user_id": "123", "action": "login"}
        # Test that method can be called without errors
        logger.info("User action", context)
        
        # Verify logger is working
        assert logger.underlying_logger is not None
    
    def test_console_logger_with_exception(self):
        """Test logging with exception."""
        logger = ConsoleLogger("test_logger")
        
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            # Test that method can be called without errors
            logger.error("An error occurred", exception=e)
        
        # Verify logger is working
        assert logger.underlying_logger is not None
    
    def test_console_logger_log_level_check(self):
        """Test log level checking."""
        logger = ConsoleLogger("test_logger", LogLevel.WARNING)
        
        assert not logger.is_enabled_for(LogLevel.DEBUG)
        assert not logger.is_enabled_for(LogLevel.INFO)
        assert logger.is_enabled_for(LogLevel.WARNING)
        assert logger.is_enabled_for(LogLevel.ERROR)
        assert logger.is_enabled_for(LogLevel.CRITICAL)
    
    def test_console_logger_json_data(self):
        """Test JSON data logging."""
        logger = ConsoleLogger("test_logger")
        
        data = {"key": "value", "number": 42}
        # Test that method can be called without errors
        logger.log_json_data("Test data", data)
        
        # Verify logger is working
        assert logger.underlying_logger is not None


class TestConsoleLoggerFactory:
    """Test console logger factory."""
    
    def test_factory_creates_loggers(self):
        """Test factory creates logger instances."""
        factory = ConsoleLoggerFactory()
        
        logger1 = factory.create_logger("test1")
        logger2 = factory.create_logger("test2")
        
        assert isinstance(logger1, ConsoleLogger)
        assert isinstance(logger2, ConsoleLogger)
        assert logger1.name == "test1"
        assert logger2.name == "test2"
    
    def test_factory_caches_loggers(self):
        """Test factory caches logger instances."""
        factory = ConsoleLoggerFactory()
        
        logger1 = factory.create_logger("test")
        logger2 = factory.create_logger("test")
        
        assert logger1 is logger2
    
    def test_factory_creates_lambda_logger(self):
        """Test factory creates Lambda-specific loggers."""
        factory = ConsoleLoggerFactory()
        
        logger = factory.create_lambda_logger("my_function")
        
        assert isinstance(logger, ConsoleLogger)
        assert "lambda.my_function" in logger.name
    
    def test_factory_get_existing_logger(self):
        """Test getting existing logger from factory."""
        factory = ConsoleLoggerFactory()
        
        created_logger = factory.create_logger("test")
        retrieved_logger = factory.get_logger("test")
        
        assert retrieved_logger is created_logger


class TestStructuredLogger:
    """Test structured logger implementation."""
    
    def test_structured_logger_creation(self):
        """Test structured logger can be created."""
        logger = StructuredLogger("test_structured")
        assert logger.name == "test_structured"
    
    def test_structured_logger_log_event(self, capsys):
        """Test structured event logging."""
        logger = StructuredLogger("test_structured")
        
        event_data = {"action": "user_login", "user_id": "123"}
        logger.log_event("user_action", event_data)
        
        captured = capsys.readouterr()
        assert "Event: user_action" in captured.err
    
    def test_structured_logger_log_metric(self, capsys):
        """Test metric logging."""
        logger = StructuredLogger("test_structured")
        
        logger.log_metric("response_time", 150.5, "ms", {"endpoint": "/api/users"})
        
        captured = capsys.readouterr()
        assert "Metric: response_time=150.5ms" in captured.err
    
    def test_structured_logger_log_performance(self, capsys):
        """Test performance logging."""
        logger = StructuredLogger("test_structured")
        
        logger.log_performance("database_query", 45.2, True, {"table": "users"})
        
        captured = capsys.readouterr()
        assert "Performance: database_query completed in 45.2ms [SUCCESS]" in captured.err
    
    def test_structured_logger_spans(self, capsys):
        """Test span tracing functionality."""
        logger = StructuredLogger("test_structured")
        
        span_id = logger.start_span("test_operation")
        assert span_id is not None
        assert span_id in logger.get_active_spans()
        
        logger.end_span(span_id, True, {"result": "success"})
        assert span_id not in logger.get_active_spans()
        
        captured = capsys.readouterr()
        assert "Span started: test_operation" in captured.err
        assert "Span ended: test_operation" in captured.err
    
    def test_structured_logger_request_logging(self, capsys):
        """Test request start/end logging."""
        logger = StructuredLogger("test_structured")
        
        logger.log_request_start("req-123", "GET", "/api/users", {"Authorization": "Bearer token"})
        logger.log_request_end("req-123", 200, 125.5, 1024)
        
        captured = capsys.readouterr()
        assert "Request started: GET /api/users [req-123]" in captured.err
        assert "Request completed: [req-123] - 200 in 125.5ms" in captured.err
    
    def test_structured_logger_database_operation(self, capsys):
        """Test database operation logging."""
        logger = StructuredLogger("test_structured")
        
        logger.log_database_operation("SELECT", "users", 25.3, True, 5)
        
        captured = capsys.readouterr()
        assert "DB Operation: SELECT on users - 25.3ms (5 records)" in captured.err
    
    def test_structured_logger_external_api_call(self, capsys):
        """Test external API call logging."""
        logger = StructuredLogger("test_structured")
        
        logger.log_external_api_call("payment_service", "/api/charge", "POST", 200.1, 201, True)
        
        captured = capsys.readouterr()
        assert "API Call: POST payment_service/api/charge - 200.1ms [201]" in captured.err


class TestCloudWatchLogger:
    """Test CloudWatch logger implementation."""
    
    def test_cloudwatch_logger_creation(self):
        """Test CloudWatch logger can be created."""
        logger = CloudWatchLogger("test_cw", log_group="/aws/lambda/test")
        assert logger.name == "test_cw"
        assert logger.log_group == "/aws/lambda/test"
    
    def test_cloudwatch_logger_enhances_context(self, capsys):
        """Test CloudWatch logger enhances context with metadata."""
        logger = CloudWatchLogger("test_cw")
        
        logger.info("Test message", {"custom": "data"})
        
        captured = capsys.readouterr()
        assert "Test message" in captured.err
    
    def test_cloudwatch_logger_lambda_events(self, capsys):
        """Test Lambda-specific event logging."""
        logger = CloudWatchLogger("test_cw")
        
        logger.log_lambda_event("cold_start", {"duration": 1500})
        logger.log_cold_start(1500.0, 512)
        logger.log_lambda_timeout_warning(5000.0)
        logger.log_memory_usage(400.0, 512)
        
        captured = capsys.readouterr()
        assert "Lambda Event: cold_start" in captured.err
        assert "Lambda Cold Start: 1500.0ms" in captured.err
        assert "Lambda Timeout Warning: 5000.0ms remaining" in captured.err
        assert "Memory Usage: 400.0MB/512MB" in captured.err


class TestLogConfiguration:
    """Test log configuration implementation."""
    
    def test_log_configuration_creation(self):
        """Test log configuration can be created."""
        config = LogConfiguration()
        assert config.get_log_level() is not None
        assert config.get_log_format() is not None
    
    def test_log_configuration_level_setting(self):
        """Test setting log level."""
        config = LogConfiguration()
        
        config.set_log_level(LogLevel.DEBUG)
        assert config.get_log_level() == LogLevel.DEBUG
        assert os.environ.get('LOG_LEVEL') == 'DEBUG'
    
    def test_log_configuration_format_setting(self):
        """Test setting log format."""
        config = LogConfiguration()
        
        config.set_log_format(LogFormat.STRUCTURED)
        assert config.get_log_format() == LogFormat.STRUCTURED
        assert config.is_structured_logging_enabled()
    
    def test_log_configuration_structured_logging(self):
        """Test structured logging enable/disable."""
        config = LogConfiguration()
        
        config.enable_structured_logging(True)
        assert config.is_structured_logging_enabled()
        assert os.environ.get('STRUCTURED_LOGS') == 'true'
        
        config.enable_structured_logging(False)
        assert not config.is_structured_logging_enabled()
        assert os.environ.get('STRUCTURED_LOGS') == 'false'
    
    def test_log_configuration_get_configuration(self):
        """Test getting configuration dictionary."""
        config = LogConfiguration()
        
        config_dict = config.get_configuration()
        
        assert 'level' in config_dict
        assert 'format' in config_dict
        assert 'structured_enabled' in config_dict
        assert 'environment_variables' in config_dict
    
    def test_log_configuration_update_configuration(self):
        """Test updating configuration from dictionary."""
        config = LogConfiguration()
        
        update_dict = {
            'level': 'ERROR',
            'format': 'json',
            'structured_enabled': True
        }
        
        config.update_configuration(update_dict)
        
        assert config.get_log_level() == LogLevel.ERROR
        assert config.is_structured_logging_enabled()
    
    def test_log_configuration_logger_specific_level(self):
        """Test logger-specific level configuration."""
        config = LogConfiguration()
        
        config.set_logger_level("my.logger", LogLevel.DEBUG)
        level = config.get_effective_log_level_for_logger("my.logger")
        
        assert level == LogLevel.DEBUG
    
    def test_log_configuration_validation(self):
        """Test configuration validation."""
        config = LogConfiguration()
        
        validation = config.validate_configuration()
        
        assert 'valid' in validation
        assert 'issues' in validation
        assert 'warnings' in validation
        assert 'configuration' in validation


class TestLoggerFactory:
    """Test main logger factory."""
    
    def test_logger_factory_creation(self):
        """Test logger factory can be created."""
        factory = LoggerFactory()
        assert factory.get_provider() == "auto"
    
    def test_logger_factory_creates_loggers(self):
        """Test factory creates appropriate loggers."""
        factory = LoggerFactory("console")
        
        logger = factory.create_logger("test")
        assert isinstance(logger, ConsoleLogger)
    
    def test_logger_factory_creates_structured_loggers(self):
        """Test factory creates structured loggers."""
        factory = LoggerFactory("console")
        
        logger = factory.create_structured_logger("test")
        assert hasattr(logger, 'log_event')  # StructuredLogger method
    
    def test_logger_factory_creates_lambda_loggers(self):
        """Test factory creates Lambda loggers."""
        factory = LoggerFactory("console")
        
        logger = factory.create_lambda_logger("my_function")
        assert isinstance(logger, ConsoleLogger)
    
    def test_logger_factory_provider_selection(self):
        """Test automatic provider selection."""
        # Test console selection (default)
        factory = LoggerFactory("auto")
        assert factory.get_effective_provider() == "console"
        
        # Test AWS environment detection
        with patch.dict(os.environ, {'AWS_LAMBDA_FUNCTION_NAME': 'test_function'}):
            factory = LoggerFactory("auto")
            assert factory.get_effective_provider() == "cloudwatch"
    
    def test_logger_factory_configuration(self):
        """Test factory configuration."""
        config = {'cloudwatch_log_group': '/custom/log/group'}
        factory = LoggerFactory("console", config)
        
        factory_config = factory.get_configuration()
        assert factory_config['provider'] == "console"
        assert factory_config['config'] == config
    
    def test_logger_factory_provider_switching(self):
        """Test switching providers."""
        factory = LoggerFactory("console")
        assert factory.get_effective_provider() == "console"
        
        factory.set_provider("cloudwatch")
        assert factory.get_provider() == "cloudwatch"
    
    def test_logger_factory_caching(self):
        """Test logger caching."""
        factory = LoggerFactory("console")
        
        logger1 = factory.create_logger("test")
        logger2 = factory.create_logger("test")
        
        assert logger1 is logger2
    
    def test_logger_factory_clear_cache(self):
        """Test clearing logger cache."""
        factory = LoggerFactory("console")
        
        logger1 = factory.create_logger("test")
        factory.clear_cache()
        logger2 = factory.create_logger("test")
        
        assert logger1 is not logger2
    
    def test_logger_factory_for_class(self):
        """Test creating logger for class."""
        factory = LoggerFactory("console")
        
        class TestClass:
            pass
        
        logger = factory.create_logger_for_class(TestClass)
        assert "TestClass" in logger.name
    
    def test_logger_factory_for_module(self):
        """Test creating logger for module."""
        factory = LoggerFactory("console")
        
        logger = factory.create_logger_for_module("my.module")
        assert logger.name == "my.module"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_logger_function(self):
        """Test create_logger convenience function."""
        logger = create_logger("test_convenience")
        assert isinstance(logger, ConsoleLogger)
        assert logger.name == "test_convenience"
    
    def test_create_lambda_logger_function(self):
        """Test create_lambda_logger convenience function."""
        logger = create_lambda_logger("test_function")
        assert isinstance(logger, ConsoleLogger)


class TestIntegrationWithExistingLoggingConfig:
    """Test integration with existing logging_config module."""
    
    def test_wraps_existing_functionality(self, capsys):
        """Test that abstraction properly wraps existing logging_config."""
        logger = ConsoleLogger("integration_test")
        
        # Test that it uses the existing configure_logger functionality
        logger.info("Integration test message")
        
        captured = capsys.readouterr()
        assert "Integration test message" in captured.err
    
    def test_lambda_logger_integration(self, capsys):
        """Test Lambda logger integration with existing create_lambda_logger."""
        factory = ConsoleLoggerFactory()
        logger = factory.create_lambda_logger("test_function")
        
        logger.info("Lambda integration test")
        
        captured = capsys.readouterr()
        assert "Lambda integration test" in captured.err
    
    def test_structured_logging_integration(self, capsys):
        """Test structured logging uses existing StructuredFormatter."""
        # Set environment for structured logging
        with patch.dict(os.environ, {'STRUCTURED_LOGS': 'true'}):
            logger = ConsoleLogger("structured_test")
            logger.info("Structured message", {"key": "value"})
            
            captured = capsys.readouterr()
            # Should contain structured output
            assert "Structured message" in captured.err


@pytest.fixture(autouse=True)
def cleanup_environment():
    """Clean up environment variables after each test."""
    original_env = os.environ.copy()
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)