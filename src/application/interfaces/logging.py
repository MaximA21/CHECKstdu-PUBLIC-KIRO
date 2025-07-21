"""Logging abstraction interfaces to replace direct logging_config usage."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum


class LogLevel(Enum):
    """Log levels supported by the logging system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """Log output formats."""
    PLAIN = "plain"
    JSON = "json"
    STRUCTURED = "structured"


class ILogger(ABC):
    """Interface for logging operations."""
    
    @abstractmethod
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a debug message.
        
        Args:
            message: Log message
            context: Optional context data
        """
        pass
    
    @abstractmethod
    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an info message.
        
        Args:
            message: Log message
            context: Optional context data
        """
        pass
    
    @abstractmethod
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a warning message.
        
        Args:
            message: Log message
            context: Optional context data
        """
        pass
    
    @abstractmethod
    def error(self, message: str, context: Optional[Dict[str, Any]] = None, 
              exception: Optional[Exception] = None) -> None:
        """
        Log an error message.
        
        Args:
            message: Log message
            context: Optional context data
            exception: Optional exception to log
        """
        pass
    
    @abstractmethod
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None,
                exception: Optional[Exception] = None) -> None:
        """
        Log a critical message.
        
        Args:
            message: Log message
            context: Optional context data
            exception: Optional exception to log
        """
        pass
    
    @abstractmethod
    def log_with_level(self, level: LogLevel, message: str, 
                      context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a message with a specific level.
        
        Args:
            level: Log level
            message: Log message
            context: Optional context data
        """
        pass
    
    @abstractmethod
    def is_enabled_for(self, level: LogLevel) -> bool:
        """
        Check if logging is enabled for a specific level.
        
        Args:
            level: Log level to check
            
        Returns:
            bool: True if logging is enabled for this level
        """
        pass


class IStructuredLogger(ILogger):
    """Interface for structured logging with additional capabilities."""
    
    @abstractmethod
    def log_event(self, event_name: str, event_data: Dict[str, Any],
                 level: LogLevel = LogLevel.INFO) -> None:
        """
        Log a structured event.
        
        Args:
            event_name: Name of the event
            event_data: Event data
            level: Log level for the event
        """
        pass
    
    @abstractmethod
    def log_metric(self, metric_name: str, value: float, unit: str = "",
                  tags: Optional[Dict[str, str]] = None) -> None:
        """
        Log a metric value.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
            tags: Optional tags for the metric
        """
        pass
    
    @abstractmethod
    def log_performance(self, operation_name: str, duration_ms: float,
                       success: bool = True, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Log performance information.
        
        Args:
            operation_name: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether the operation was successful
            metadata: Optional additional metadata
        """
        pass
    
    @abstractmethod
    def start_span(self, span_name: str, parent_span_id: Optional[str] = None) -> str:
        """
        Start a new logging span for tracing.
        
        Args:
            span_name: Name of the span
            parent_span_id: Optional parent span ID
            
        Returns:
            str: Span ID
        """
        pass
    
    @abstractmethod
    def end_span(self, span_id: str, success: bool = True, 
                metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        End a logging span.
        
        Args:
            span_id: ID of the span to end
            success: Whether the span completed successfully
            metadata: Optional metadata for the span
        """
        pass


class ILoggerFactory(ABC):
    """Interface for creating logger instances."""
    
    @abstractmethod
    def create_logger(self, name: str, level: Optional[LogLevel] = None) -> ILogger:
        """
        Create a logger instance.
        
        Args:
            name: Name of the logger
            level: Optional log level override
            
        Returns:
            ILogger: Logger instance
        """
        pass
    
    @abstractmethod
    def create_structured_logger(self, name: str, 
                                level: Optional[LogLevel] = None) -> IStructuredLogger:
        """
        Create a structured logger instance.
        
        Args:
            name: Name of the logger
            level: Optional log level override
            
        Returns:
            IStructuredLogger: Structured logger instance
        """
        pass
    
    @abstractmethod
    def create_lambda_logger(self, function_name: str) -> ILogger:
        """
        Create a logger specifically configured for Lambda functions.
        
        Args:
            function_name: Name of the Lambda function
            
        Returns:
            ILogger: Lambda-configured logger
        """
        pass
    
    @abstractmethod
    def get_logger(self, name: str) -> Optional[ILogger]:
        """
        Get an existing logger by name.
        
        Args:
            name: Name of the logger
            
        Returns:
            Optional[ILogger]: Existing logger or None if not found
        """
        pass


class ILogConfiguration(ABC):
    """Interface for logging configuration management."""
    
    @abstractmethod
    def get_log_level(self) -> LogLevel:
        """
        Get the current log level.
        
        Returns:
            LogLevel: Current log level
        """
        pass
    
    @abstractmethod
    def set_log_level(self, level: LogLevel) -> None:
        """
        Set the log level.
        
        Args:
            level: Log level to set
        """
        pass
    
    @abstractmethod
    def get_log_format(self) -> LogFormat:
        """
        Get the current log format.
        
        Returns:
            LogFormat: Current log format
        """
        pass
    
    @abstractmethod
    def set_log_format(self, format_type: LogFormat) -> None:
        """
        Set the log format.
        
        Args:
            format_type: Log format to set
        """
        pass
    
    @abstractmethod
    def is_structured_logging_enabled(self) -> bool:
        """
        Check if structured logging is enabled.
        
        Returns:
            bool: True if structured logging is enabled
        """
        pass
    
    @abstractmethod
    def enable_structured_logging(self, enabled: bool = True) -> None:
        """
        Enable or disable structured logging.
        
        Args:
            enabled: Whether to enable structured logging
        """
        pass
    
    @abstractmethod
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get the current logging configuration.
        
        Returns:
            Dict[str, Any]: Current configuration
        """
        pass
    
    @abstractmethod
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """
        Update the logging configuration.
        
        Args:
            config: New configuration values
        """
        pass


class ILogDestination(ABC):
    """Interface for log destinations (CloudWatch, console, file, etc.)."""
    
    @abstractmethod
    async def write_log(self, log_entry: Dict[str, Any]) -> bool:
        """
        Write a log entry to the destination.
        
        Args:
            log_entry: Log entry to write
            
        Returns:
            bool: True if write was successful
        """
        pass
    
    @abstractmethod
    async def write_batch(self, log_entries: List[Dict[str, Any]]) -> int:
        """
        Write multiple log entries in batch.
        
        Args:
            log_entries: List of log entries to write
            
        Returns:
            int: Number of entries successfully written
        """
        pass
    
    @abstractmethod
    async def flush(self) -> bool:
        """
        Flush any buffered log entries.
        
        Returns:
            bool: True if flush was successful
        """
        pass
    
    @property
    @abstractmethod
    def destination_name(self) -> str:
        """Get the name of the log destination."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the destination is currently available."""
        pass


class ILogAggregator(ABC):
    """Interface for aggregating logs from multiple sources."""
    
    @abstractmethod
    async def collect_logs(self, source_filters: Optional[Dict[str, Any]] = None,
                          time_range: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Collect logs from configured sources.
        
        Args:
            source_filters: Optional filters for log sources
            time_range: Optional time range for log collection
            
        Returns:
            List[Dict[str, Any]]: Collected log entries
        """
        pass
    
    @abstractmethod
    async def search_logs(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search logs using a query string.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: Matching log entries
        """
        pass
    
    @abstractmethod
    async def get_log_statistics(self, time_range: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about logs in a time range.
        
        Args:
            time_range: Time range for statistics
            
        Returns:
            Dict[str, Any]: Log statistics
        """
        pass