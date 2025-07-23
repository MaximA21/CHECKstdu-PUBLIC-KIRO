"""CloudWatch logger implementation for AWS environments."""

import json
import time
from typing import Any, Dict, List, Optional

from ...application.interfaces.logging import ILogger, ILoggerFactory, LogLevel
from .console_logger import ConsoleLogger


class CloudWatchLogger(ConsoleLogger):
    """CloudWatch logger implementation that extends console logging."""

    def __init__(
        self, name: str, level: Optional[LogLevel] = None, log_group: Optional[str] = None, log_stream: Optional[str] = None
    ):
        """
        Initialize CloudWatch logger.

        Args:
            name: Logger name
            level: Optional log level override
            log_group: CloudWatch log group name
            log_stream: CloudWatch log stream name
        """
        super().__init__(name, level)
        self._log_group = log_group or f"/aws/lambda/{name}"
        self._log_stream = log_stream or f"{int(time.time())}"
        self._log_buffer: List[Dict[str, Any]] = []
        self._buffer_size = 100  # Buffer size before auto-flush

        # In Lambda environment, CloudWatch logging is handled automatically
        # by the Lambda runtime, so we primarily enhance the console output
        # with CloudWatch-specific metadata

    def _enhance_with_cloudwatch_metadata(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Enhance log entry with CloudWatch metadata."""
        enhanced_context = context.copy() if context else {}
        enhanced_context.update(
            {
                "log_group": self._log_group,
                "log_stream": self._log_stream,
                "logger_name": self._name,
                "timestamp": int(time.time() * 1000),  # CloudWatch expects milliseconds
                "aws_request_id": self._get_aws_request_id(),
            }
        )
        return enhanced_context

    def _get_aws_request_id(self) -> Optional[str]:
        """Get AWS request ID from Lambda context if available."""
        import os

        return os.environ.get("AWS_REQUEST_ID")

    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a debug message with CloudWatch metadata."""
        enhanced_context = self._enhance_with_cloudwatch_metadata(message, context)
        super().debug(message, enhanced_context)

    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log an info message with CloudWatch metadata."""
        enhanced_context = self._enhance_with_cloudwatch_metadata(message, context)
        super().info(message, enhanced_context)

    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log a warning message with CloudWatch metadata."""
        enhanced_context = self._enhance_with_cloudwatch_metadata(message, context)
        super().warning(message, enhanced_context)

    def error(self, message: str, context: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None) -> None:
        """Log an error message with CloudWatch metadata."""
        enhanced_context = self._enhance_with_cloudwatch_metadata(message, context)
        if exception:
            enhanced_context["exception_type"] = type(exception).__name__
            enhanced_context["exception_message"] = str(exception)
        super().error(message, enhanced_context, exception)

    def critical(self, message: str, context: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None) -> None:
        """Log a critical message with CloudWatch metadata."""
        enhanced_context = self._enhance_with_cloudwatch_metadata(message, context)
        if exception:
            enhanced_context["exception_type"] = type(exception).__name__
            enhanced_context["exception_message"] = str(exception)
        super().critical(message, enhanced_context, exception)

    def log_lambda_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log Lambda-specific events."""
        context = {"event_type": "lambda_event", "lambda_event_type": event_type, "event_data": event_data}
        message = f"Lambda Event: {event_type}"
        self.info(message, context)

    def log_cold_start(self, duration_ms: float, memory_mb: int) -> None:
        """Log Lambda cold start information."""
        context = {
            "event_type": "lambda_cold_start",
            "cold_start_duration_ms": duration_ms,
            "memory_allocated_mb": memory_mb,
            "function_name": self._name,
        }
        message = f"Lambda Cold Start: {duration_ms:.2f}ms (Memory: {memory_mb}MB)"
        self.info(message, context)

    def log_lambda_timeout_warning(self, remaining_time_ms: float) -> None:
        """Log Lambda timeout warning."""
        context = {"event_type": "lambda_timeout_warning", "remaining_time_ms": remaining_time_ms, "function_name": self._name}
        message = f"Lambda Timeout Warning: {remaining_time_ms:.2f}ms remaining"
        self.warning(message, context)

    def log_memory_usage(self, used_mb: float, allocated_mb: int) -> None:
        """Log memory usage information."""
        usage_percent = (used_mb / allocated_mb) * 100
        context = {
            "event_type": "memory_usage",
            "memory_used_mb": used_mb,
            "memory_allocated_mb": allocated_mb,
            "memory_usage_percent": usage_percent,
        }
        message = f"Memory Usage: {used_mb:.1f}MB/{allocated_mb}MB ({usage_percent:.1f}%)"

        # Log as warning if memory usage is high
        if usage_percent > 80:
            self.warning(message, context)
        else:
            self.info(message, context)

    @property
    def log_group(self) -> str:
        """Get the CloudWatch log group name."""
        return self._log_group

    @property
    def log_stream(self) -> str:
        """Get the CloudWatch log stream name."""
        return self._log_stream


class CloudWatchLoggerFactory(ILoggerFactory):
    """Factory for creating CloudWatch loggers."""

    def __init__(self, default_log_group: Optional[str] = None):
        """
        Initialize the CloudWatch logger factory.

        Args:
            default_log_group: Default log group for all loggers
        """
        self._loggers: Dict[str, CloudWatchLogger] = {}
        self._default_log_group = default_log_group

    def create_logger(self, name: str, level: Optional[LogLevel] = None) -> ILogger:
        """Create a CloudWatch logger instance."""
        if name not in self._loggers:
            log_group = self._default_log_group or f"/aws/lambda/{name}"
            self._loggers[name] = CloudWatchLogger(name, level, log_group)
        return self._loggers[name]

    def create_structured_logger(self, name: str, level: Optional[LogLevel] = None) -> ILogger:
        """Create a structured CloudWatch logger."""
        from .structured_logger import StructuredLogger

        # Create a CloudWatch-enhanced structured logger
        base_logger = self.create_logger(name, level)
        if isinstance(base_logger, CloudWatchLogger):
            # Create structured logger that uses CloudWatch as base
            structured = StructuredLogger(name, level, use_console=False)
            structured._logger = base_logger._logger
            return structured
        return base_logger

    def create_lambda_logger(self, function_name: str) -> ILogger:
        """Create a logger specifically configured for Lambda functions."""
        logger_name = f"lambda.{function_name}"
        if logger_name not in self._loggers:
            log_group = f"/aws/lambda/{function_name}"
            self._loggers[logger_name] = CloudWatchLogger(logger_name, log_group=log_group)
        return self._loggers[logger_name]

    def get_logger(self, name: str) -> Optional[ILogger]:
        """Get an existing logger by name."""
        return self._loggers.get(name)

    def clear_loggers(self) -> None:
        """Clear all cached loggers."""
        self._loggers.clear()

    def set_default_log_group(self, log_group: str) -> None:
        """Set the default log group for new loggers."""
        self._default_log_group = log_group
