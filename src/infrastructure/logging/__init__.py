"""Infrastructure logging implementations."""

from .console_logger import ConsoleLogger, ConsoleLoggerFactory
from .cloudwatch_logger import CloudWatchLogger, CloudWatchLoggerFactory
from .structured_logger import StructuredLogger
from .log_configuration import LogConfiguration
from .log_destinations import ConsoleDestination, CloudWatchDestination, FileDestination
from .logger_factory import LoggerFactory, create_logger, create_lambda_logger

# Legacy logging configuration removed - use logger_factory instead

__all__ = [
    "ConsoleLogger",
    "ConsoleLoggerFactory",
    "CloudWatchLogger",
    "CloudWatchLoggerFactory",
    "StructuredLogger",
    "LogConfiguration",
    "ConsoleDestination",
    "CloudWatchDestination",
    "FileDestination",
    "LoggerFactory",
    "create_logger",
    "create_lambda_logger",
    "legacy_logging_config",
]
