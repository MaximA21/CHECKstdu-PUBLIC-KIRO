"""Infrastructure logging implementations."""

from .cloudwatch_logger import CloudWatchLogger, CloudWatchLoggerFactory
from .console_logger import ConsoleLogger, ConsoleLoggerFactory
from .log_configuration import LogConfiguration
from .log_destinations import CloudWatchDestination, ConsoleDestination, FileDestination
from .logger_factory import LoggerFactory, create_lambda_logger, create_logger
from .structured_logger import StructuredLogger

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
