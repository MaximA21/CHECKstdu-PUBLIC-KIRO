"""Structured logger implementation with enhanced capabilities."""

import time
import uuid
from typing import Dict, Any, Optional
from ...application.interfaces.logging import IStructuredLogger, LogLevel
from .console_logger import ConsoleLogger


class StructuredLogger(ConsoleLogger, IStructuredLogger):
    """Structured logger implementation with tracing and metrics support."""

    def __init__(self, name: str, level: Optional[LogLevel] = None, use_console: bool = True):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            level: Optional log level override
            use_console: Whether to use console output
        """
        super().__init__(name, level)
        self._use_console = use_console
        self._active_spans: Dict[str, Dict[str, Any]] = {}

    def log_event(self, event_name: str, event_data: Dict[str, Any], level: LogLevel = LogLevel.INFO) -> None:
        """Log a structured event."""
        structured_data = {
            "event_type": "application_event",
            "event_name": event_name,
            "event_data": event_data,
            "timestamp": time.time(),
        }

        message = f"Event: {event_name}"
        self.log_with_level(level, message, structured_data)

    def log_metric(self, metric_name: str, value: float, unit: str = "", tags: Optional[Dict[str, str]] = None) -> None:
        """Log a metric value."""
        structured_data = {
            "event_type": "metric",
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            "metric_tags": tags or {},
            "timestamp": time.time(),
        }

        message = f"Metric: {metric_name}={value}{unit}"
        self.info(message, structured_data)

    def log_performance(
        self, operation_name: str, duration_ms: float, success: bool = True, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log performance information."""
        structured_data = {
            "event_type": "performance",
            "operation_name": operation_name,
            "duration_ms": duration_ms,
            "success": success,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }

        status = "SUCCESS" if success else "FAILURE"
        message = f"Performance: {operation_name} completed in {duration_ms}ms [{status}]"

        level = LogLevel.INFO if success else LogLevel.WARNING
        self.log_with_level(level, message, structured_data)

    def start_span(self, span_name: str, parent_span_id: Optional[str] = None) -> str:
        """Start a new logging span for tracing."""
        span_id = str(uuid.uuid4())

        span_data = {
            "span_id": span_id,
            "span_name": span_name,
            "parent_span_id": parent_span_id,
            "start_time": time.time(),
            "status": "active",
        }

        self._active_spans[span_id] = span_data

        structured_data = {
            "event_type": "span_start",
            "span_id": span_id,
            "span_name": span_name,
            "parent_span_id": parent_span_id,
            "timestamp": span_data["start_time"],
        }

        message = f"Span started: {span_name} [{span_id}]"
        self.debug(message, structured_data)

        return span_id

    def end_span(self, span_id: str, success: bool = True, metadata: Optional[Dict[str, Any]] = None) -> None:
        """End a logging span."""
        if span_id not in self._active_spans:
            self.warning(f"Attempted to end unknown span: {span_id}")
            return

        span_data = self._active_spans[span_id]
        end_time = time.time()
        duration_ms = (end_time - span_data["start_time"]) * 1000

        structured_data = {
            "event_type": "span_end",
            "span_id": span_id,
            "span_name": span_data["span_name"],
            "parent_span_id": span_data.get("parent_span_id"),
            "duration_ms": duration_ms,
            "success": success,
            "metadata": metadata or {},
            "timestamp": end_time,
        }

        status = "SUCCESS" if success else "FAILURE"
        message = f"Span ended: {span_data['span_name']} [{span_id}] - {duration_ms:.2f}ms [{status}]"

        level = LogLevel.DEBUG if success else LogLevel.WARNING
        self.log_with_level(level, message, structured_data)

        # Remove from active spans
        del self._active_spans[span_id]

    def log_request_start(self, request_id: str, method: str, path: str, headers: Optional[Dict[str, str]] = None) -> None:
        """Log the start of a request."""
        structured_data = {
            "event_type": "request_start",
            "request_id": request_id,
            "http_method": method,
            "request_path": path,
            "request_headers": headers or {},
            "timestamp": time.time(),
        }

        message = f"Request started: {method} {path} [{request_id}]"
        self.info(message, structured_data)

    def log_request_end(
        self, request_id: str, status_code: int, duration_ms: float, response_size: Optional[int] = None
    ) -> None:
        """Log the end of a request."""
        structured_data = {
            "event_type": "request_end",
            "request_id": request_id,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "response_size_bytes": response_size,
            "timestamp": time.time(),
        }

        message = f"Request completed: [{request_id}] - {status_code} in {duration_ms:.2f}ms"

        # Log level based on status code
        if status_code < 400:
            level = LogLevel.INFO
        elif status_code < 500:
            level = LogLevel.WARNING
        else:
            level = LogLevel.ERROR

        self.log_with_level(level, message, structured_data)

    def log_database_operation(
        self, operation: str, table: str, duration_ms: float, success: bool = True, record_count: Optional[int] = None
    ) -> None:
        """Log database operations."""
        structured_data = {
            "event_type": "database_operation",
            "db_operation": operation,
            "db_table": table,
            "duration_ms": duration_ms,
            "success": success,
            "record_count": record_count,
            "timestamp": time.time(),
        }

        message = f"DB Operation: {operation} on {table} - {duration_ms:.2f}ms"
        if record_count is not None:
            message += f" ({record_count} records)"

        level = LogLevel.INFO if success else LogLevel.ERROR
        self.log_with_level(level, message, structured_data)

    def log_external_api_call(
        self,
        service_name: str,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: Optional[int] = None,
        success: bool = True,
    ) -> None:
        """Log external API calls."""
        structured_data = {
            "event_type": "external_api_call",
            "service_name": service_name,
            "api_endpoint": endpoint,
            "http_method": method,
            "duration_ms": duration_ms,
            "status_code": status_code,
            "success": success,
            "timestamp": time.time(),
        }

        message = f"API Call: {method} {service_name}{endpoint} - {duration_ms:.2f}ms"
        if status_code:
            message += f" [{status_code}]"

        level = LogLevel.INFO if success else LogLevel.ERROR
        self.log_with_level(level, message, structured_data)

    def get_active_spans(self) -> Dict[str, Dict[str, Any]]:
        """Get all currently active spans."""
        return self._active_spans.copy()

    def clear_active_spans(self) -> None:
        """Clear all active spans (useful for cleanup)."""
        for span_id in list(self._active_spans.keys()):
            self.end_span(span_id, success=False, metadata={"reason": "forced_cleanup"})
