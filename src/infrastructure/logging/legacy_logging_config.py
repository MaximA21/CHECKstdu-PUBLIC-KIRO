"""
Legacy logging configuration module for backward compatibility.

This module provides the same interface as the original services/logging_config.py
while using the new logging infrastructure internally.
"""

import logging
import os
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from ...application.interfaces.logging import LogLevel as NewLogLevel
from .logger_factory import LoggerFactory
from .log_configuration import LogConfiguration


class LogLevel(Enum):
    """Supported log levels (legacy enum for backward compatibility)."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogConfig:
    """Configuration for logging setup (legacy class for backward compatibility)."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enable_structured: bool = False
    
    @classmethod
    def from_environment(cls) -> 'LogConfig':
        """Create LogConfig from environment variables."""
        return cls(
            level=os.environ.get('LOG_LEVEL', 'INFO').upper(),
            enable_structured=os.environ.get('STRUCTURED_LOGS', 'false').lower() == 'true'
        )


# Global logger factory instance for backward compatibility
_logger_factory = LoggerFactory()
_log_configuration = LogConfiguration()


def get_log_level() -> int:
    """
    Get log level from environment variable with fallback to INFO.
    
    Returns:
        int: Logging level constant from logging module
    """
    log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    # Map string levels to logging constants
    level_mapping = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR
    }
    
    # Return mapped level or default to INFO if invalid
    return level_mapping.get(log_level_str, logging.INFO)


def configure_logger(logger_name: Optional[str] = None) -> logging.Logger:
    """
    Configure logger with appropriate level and formatting.
    
    Args:
        logger_name: Name for the logger. If None, uses root logger.
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(logger_name)
    
    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Get configuration from environment
    config = LogConfig.from_environment()
    log_level = get_log_level()
    
    # Set log level
    logger.setLevel(log_level)
    
    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    
    # Create formatter
    if config.enable_structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(config.format)
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    return logger


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging output.
    
    Outputs logs in JSON format for better parsing and analysis.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry)


def create_lambda_logger(function_name: str) -> logging.Logger:
    """
    Create a logger specifically configured for Lambda functions.
    
    Args:
        function_name: Name of the Lambda function
        
    Returns:
        logging.Logger: Configured logger for the Lambda function
    """
    logger_name = f"lambda.{function_name}"
    return configure_logger(logger_name)


def log_with_context(logger: logging.Logger, level: int, message: str, 
                    context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a message with additional context information.
    
    Args:
        logger: Logger instance to use
        level: Logging level (e.g., logging.INFO)
        message: Log message
        context: Additional context to include in structured logs
    """
    if context and isinstance(logger.handlers[0].formatter, StructuredFormatter):
        # Create a log record with extra context
        record = logger.makeRecord(
            logger.name, level, "", 0, message, (), None
        )
        record.extra_fields = context
        logger.handle(record)
    else:
        logger.log(level, message)


def safe_json_log(logger: logging.Logger, level: int, message: str, 
                 data: Any, max_length: int = 1000) -> None:
    """
    Safely log data as JSON, handling serialization errors and length limits.
    
    Args:
        logger: Logger instance to use
        level: Logging level
        message: Log message prefix
        data: Data to serialize as JSON
        max_length: Maximum length of JSON string to log
    """
    try:
        json_str = json.dumps(data, default=str)
        if len(json_str) > max_length:
            json_str = json_str[:max_length] + "... [truncated]"
        logger.log(level, f"{message}: {json_str}")
    except (TypeError, ValueError) as e:
        logger.log(level, f"{message}: [JSON serialization failed: {str(e)}]")


# Convenience function for quick logger setup
def get_lambda_logger(function_name: str) -> logging.Logger:
    """
    Quick setup function for Lambda function logging.
    
    Args:
        function_name: Name of the Lambda function
        
    Returns:
        logging.Logger: Ready-to-use logger
    """
    return create_lambda_logger(function_name)


# New functions that bridge to the new logging infrastructure
def get_new_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a logger using the new infrastructure (for migration purposes).
    
    Args:
        name: Logger name
        level: Optional log level string
        
    Returns:
        logging.Logger: Logger instance from new infrastructure
    """
    new_level = None
    if level:
        try:
            new_level = NewLogLevel(level.upper())
        except ValueError:
            new_level = NewLogLevel.INFO
    
    new_logger = _logger_factory.create_logger(name, new_level)
    
    # Return the underlying Python logger for backward compatibility
    if hasattr(new_logger, '_logger'):
        return new_logger._logger
    else:
        # Fallback to creating a standard logger
        return configure_logger(name)


def get_new_lambda_logger(function_name: str) -> logging.Logger:
    """
    Get a Lambda logger using the new infrastructure (for migration purposes).
    
    Args:
        function_name: Lambda function name
        
    Returns:
        logging.Logger: Lambda logger instance from new infrastructure
    """
    new_logger = _logger_factory.create_lambda_logger(function_name)
    
    # Return the underlying Python logger for backward compatibility
    if hasattr(new_logger, '_logger'):
        return new_logger._logger
    else:
        # Fallback to creating a standard logger
        return create_lambda_logger(function_name)


def migrate_to_new_logging() -> None:
    """
    Helper function to migrate existing code to use the new logging infrastructure.
    
    This function can be called to switch the global logger factory to use
    the new infrastructure while maintaining backward compatibility.
    """
    global _logger_factory
    _logger_factory = LoggerFactory("auto")