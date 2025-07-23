"""Simple console logger implementation for dependency injection."""

import json
import logging
from typing import Any, Dict, Optional

from ...application.interfaces.logging import ILogger, ILoggerFactory, LogLevel


class ConsoleLogger(ILogger):
    """Simple console logger implementation."""

    def __init__(self, name: str, level: Optional[LogLevel] = None):
        """
        Initialize console logger.

        Args:
            name: Logger name
            level: Optional log level override
        """
        self._name = name
        self._logger = logging.getLogger(name)

        # Set up basic console handler if not already configured
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

        if level:
            self._logger.setLevel(self._log_level_to_python(level))

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a debug message."""
        if context:
            message = f"{message} | Context: {json.dumps(context, default=str)}"
        self._logger.debug(message)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log an info message."""
        if context:
            message = f"{message} | Context: {json.dumps(context, default=str)}"
        self._logger.info(message)

    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning message."""
        if context:
            message = f"{message} | Context: {json.dumps(context, default=str)}"
        self._logger.warning(message)

    def error(self, message: str, context: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None) -> None:
        """Log an error message."""
        if context:
            message = f"{message} | Context: {json.dumps(context, default=str)}"
        if exception:
            self._logger.error(message, exc_info=exception)
        else:
            self._logger.error(message)

    def critical(self, message: str, context: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None) -> None:
        """Log a critical message."""
        if context:
            message = f"{message} | Context: {json.dumps(context, default=str)}"
        if exception:
            self._logger.critical(message, exc_info=exception)
        else:
            self._logger.critical(message)

    def log_with_level(self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a message with a specific level."""
        python_level = self._log_level_to_python(level)
        if context:
            message = f"{message} | Context: {json.dumps(context, default=str)}"
        self._logger.log(python_level, message)

    def is_enabled_for(self, level: LogLevel) -> bool:
        """Check if logging is enabled for a specific level."""
        python_level = self._log_level_to_python(level)
        return self._logger.isEnabledFor(python_level)

    @staticmethod
    def _log_level_to_python(level: LogLevel) -> int:
        """Convert LogLevel enum to Python logging level."""
        mapping = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        return mapping.get(level, logging.INFO)

    @property
    def name(self) -> str:
        """Get logger name."""
        return self._name


class ConsoleLoggerFactory(ILoggerFactory):
    """Factory for creating console loggers."""

    def __init__(self):
        """Initialize the console logger factory."""
        self._loggers: Dict[str, ConsoleLogger] = {}

    def create_logger(self, name: str, level: Optional[LogLevel] = None) -> ILogger:
        """Create a console logger instance."""
        if name not in self._loggers:
            self._loggers[name] = ConsoleLogger(name, level)
        return self._loggers[name]

    def create_structured_logger(self, name: str, level: Optional[LogLevel] = None) -> ILogger:
        """Create a structured console logger."""
        # For now, return regular console logger
        return self.create_logger(name, level)

    def create_lambda_logger(self, function_name: str) -> ILogger:
        """Create a logger specifically configured for Lambda functions."""
        logger_name = f"lambda.{function_name}"
        return self.create_logger(logger_name, LogLevel.INFO)

    def get_logger(self, name: str) -> Optional[ILogger]:
        """Get an existing logger by name."""
        return self._loggers.get(name)
