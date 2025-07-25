"""Unit tests for structured logger."""

import time
from unittest.mock import Mock, patch

import pytest

from src.application.interfaces.logging import LogLevel
from src.infrastructure.logging.structured_logger import StructuredLogger


class TestStructuredLogger:
    """Test cases for StructuredLogger."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = StructuredLogger("test.logger", LogLevel.INFO)

    def test_init_with_defaults(self):
        """Test StructuredLogger initialization with defaults."""
        logger = StructuredLogger("test.logger")
        assert logger.name == "test.logger"
        assert logger._use_console is True

    def test_init_with_custom_settings(self):
        """Test StructuredLogger initialization with custom settings."""
        logger = StructuredLogger("test.logger", LogLevel.DEBUG, use_console=False)
        assert logger.name == "test.logger"
        assert logger._use_console is False

    @patch("time.time", return_value=1234567890.123)
    def test_log_event(self, mock_time):
        """Test logging structured events."""
        event_data = {"user_id": "123", "action": "login"}

        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_event("user_login", event_data, LogLevel.INFO)

            mock_log.assert_called_once()
            args = mock_log.call_args

            assert args[0][0] == LogLevel.INFO
            assert args[0][1] == "Event: user_login"

            structured_data = args[0][2]
            assert structured_data["event_type"] == "application_event"
            assert structured_data["event_name"] == "user_login"
            assert structured_data["event_data"] == event_data
            assert structured_data["timestamp"] == 1234567890.123

    def test_log_event_with_default_level(self):
        """Test logging events with default INFO level."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_event("test_event", {})

            args = mock_log.call_args
            assert args[0][0] == LogLevel.INFO

    @patch("time.time", return_value=1234567890.123)
    def test_log_metric(self, mock_time):
        """Test logging metrics."""
        tags = {"environment": "test", "service": "api"}

        with patch.object(self.logger, "info") as mock_info:
            self.logger.log_metric("response_time", 150.5, "ms", tags)

            mock_info.assert_called_once()
            args = mock_info.call_args

            assert args[0][0] == "Metric: response_time=150.5ms"

            structured_data = args[0][1]
            assert structured_data["event_type"] == "metric"
            assert structured_data["metric_name"] == "response_time"
            assert structured_data["metric_value"] == 150.5
            assert structured_data["metric_unit"] == "ms"
            assert structured_data["metric_tags"] == tags
            assert structured_data["timestamp"] == 1234567890.123

    def test_log_metric_without_unit_and_tags(self):
        """Test logging metrics without unit and tags."""
        with patch.object(self.logger, "info") as mock_info:
            self.logger.log_metric("counter", 42)

            args = mock_info.call_args
            assert args[0][0] == "Metric: counter=42"

            structured_data = args[0][1]
            assert structured_data["metric_unit"] == ""
            assert structured_data["metric_tags"] == {}

    @patch("time.time", return_value=1234567890.123)
    def test_log_performance_success(self, mock_time):
        """Test logging successful performance metrics."""
        metadata = {"query_count": 3, "cache_hit": True}

        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_performance("database_query", 25.7, True, metadata)

            mock_log.assert_called_once()
            args = mock_log.call_args

            assert args[0][0] == LogLevel.INFO
            assert args[0][1] == "Performance: database_query completed in 25.7ms [SUCCESS]"

            structured_data = args[0][2]
            assert structured_data["event_type"] == "performance"
            assert structured_data["operation_name"] == "database_query"
            assert structured_data["duration_ms"] == 25.7
            assert structured_data["success"] is True
            assert structured_data["metadata"] == metadata
            assert structured_data["timestamp"] == 1234567890.123

    def test_log_performance_failure(self):
        """Test logging failed performance metrics."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_performance("api_call", 5000.0, False)

            args = mock_log.call_args
            assert args[0][0] == LogLevel.WARNING
            assert "FAILURE" in args[0][1]

            structured_data = args[0][2]
            assert structured_data["success"] is False

    def test_log_performance_defaults(self):
        """Test logging performance with default values."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_performance("operation", 100.0)

            args = mock_log.call_args
            structured_data = args[0][2]
            assert structured_data["success"] is True
            assert structured_data["metadata"] == {}

    @patch("time.time", return_value=1234567890.123)
    @patch("uuid.uuid4")
    def test_start_span(self, mock_uuid, mock_time):
        """Test starting a logging span."""
        mock_uuid.return_value.hex = "test-span-id"
        mock_uuid.return_value.__str__ = lambda x: "test-span-id"

        with patch.object(self.logger, "debug") as mock_debug:
            span_id = self.logger.start_span("test_operation", "parent-span-id")

            assert span_id == "test-span-id"
            assert span_id in self.logger._active_spans

            span_data = self.logger._active_spans[span_id]
            assert span_data["span_name"] == "test_operation"
            assert span_data["parent_span_id"] == "parent-span-id"
            assert span_data["start_time"] == 1234567890.123
            assert span_data["status"] == "active"

            mock_debug.assert_called_once()
            args = mock_debug.call_args
            assert "Span started: test_operation [test-span-id]" in args[0][0]

    def test_start_span_without_parent(self):
        """Test starting a span without parent span ID."""
        with patch.object(self.logger, "debug"):
            span_id = self.logger.start_span("root_operation")

            span_data = self.logger._active_spans[span_id]
            assert span_data["parent_span_id"] is None

    @patch("time.time")
    def test_end_span_success(self, mock_time):
        """Test ending a span successfully."""
        # Setup: start a span
        mock_time.return_value = 1234567890.0
        span_id = self.logger.start_span("test_operation")

        # End the span
        mock_time.return_value = 1234567890.5  # 500ms later
        metadata = {"records_processed": 100}

        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.end_span(span_id, True, metadata)

            # Span should be removed from active spans
            assert span_id not in self.logger._active_spans

            mock_log.assert_called_once()
            args = mock_log.call_args

            assert args[0][0] == LogLevel.DEBUG
            assert "Span ended: test_operation" in args[0][1]
            assert "SUCCESS" in args[0][1]

            structured_data = args[0][2]
            assert structured_data["event_type"] == "span_end"
            assert structured_data["span_id"] == span_id
            assert structured_data["duration_ms"] == 500.0
            assert structured_data["success"] is True
            assert structured_data["metadata"] == metadata

    def test_end_span_failure(self):
        """Test ending a span with failure."""
        span_id = self.logger.start_span("test_operation")

        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.end_span(span_id, False)

            args = mock_log.call_args
            assert args[0][0] == LogLevel.WARNING
            assert "FAILURE" in args[0][1]

            structured_data = args[0][2]
            assert structured_data["success"] is False

    def test_end_span_unknown_span(self):
        """Test ending an unknown span."""
        with patch.object(self.logger, "warning") as mock_warning:
            self.logger.end_span("unknown-span-id")

            mock_warning.assert_called_once()
            assert "unknown span" in mock_warning.call_args[0][0].lower()

    @patch("time.time", return_value=1234567890.123)
    def test_log_request_start(self, mock_time):
        """Test logging request start."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer token"}

        with patch.object(self.logger, "info") as mock_info:
            self.logger.log_request_start("req-123", "POST", "/api/users", headers)

            mock_info.assert_called_once()
            args = mock_info.call_args

            assert args[0][0] == "Request started: POST /api/users [req-123]"

            structured_data = args[0][1]
            assert structured_data["event_type"] == "request_start"
            assert structured_data["request_id"] == "req-123"
            assert structured_data["http_method"] == "POST"
            assert structured_data["request_path"] == "/api/users"
            assert structured_data["request_headers"] == headers
            assert structured_data["timestamp"] == 1234567890.123

    def test_log_request_start_without_headers(self):
        """Test logging request start without headers."""
        with patch.object(self.logger, "info") as mock_info:
            self.logger.log_request_start("req-123", "GET", "/api/health")

            args = mock_info.call_args
            structured_data = args[0][1]
            assert structured_data["request_headers"] == {}

    @patch("time.time", return_value=1234567890.123)
    def test_log_request_end_success(self, mock_time):
        """Test logging successful request end."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_request_end("req-123", 200, 150.5, 1024)

            mock_log.assert_called_once()
            args = mock_log.call_args

            assert args[0][0] == LogLevel.INFO
            assert args[0][1] == "Request completed: [req-123] - 200 in 150.50ms"

            structured_data = args[0][2]
            assert structured_data["event_type"] == "request_end"
            assert structured_data["request_id"] == "req-123"
            assert structured_data["status_code"] == 200
            assert structured_data["duration_ms"] == 150.5
            assert structured_data["response_size_bytes"] == 1024

    def test_log_request_end_client_error(self):
        """Test logging request end with client error."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_request_end("req-123", 400, 50.0)

            args = mock_log.call_args
            assert args[0][0] == LogLevel.WARNING

    def test_log_request_end_server_error(self):
        """Test logging request end with server error."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_request_end("req-123", 500, 1000.0)

            args = mock_log.call_args
            assert args[0][0] == LogLevel.ERROR

    def test_log_request_end_without_response_size(self):
        """Test logging request end without response size."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_request_end("req-123", 200, 100.0)

            args = mock_log.call_args
            structured_data = args[0][2]
            assert structured_data["response_size_bytes"] is None

    @patch("time.time", return_value=1234567890.123)
    def test_log_database_operation_success(self, mock_time):
        """Test logging successful database operation."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_database_operation("SELECT", "users", 25.3, True, 150)

            mock_log.assert_called_once()
            args = mock_log.call_args

            assert args[0][0] == LogLevel.INFO
            assert args[0][1] == "DB Operation: SELECT on users - 25.30ms (150 records)"

            structured_data = args[0][2]
            assert structured_data["event_type"] == "database_operation"
            assert structured_data["db_operation"] == "SELECT"
            assert structured_data["db_table"] == "users"
            assert structured_data["duration_ms"] == 25.3
            assert structured_data["success"] is True
            assert structured_data["record_count"] == 150

    def test_log_database_operation_failure(self):
        """Test logging failed database operation."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_database_operation("INSERT", "orders", 100.0, False)

            args = mock_log.call_args
            assert args[0][0] == LogLevel.ERROR

            structured_data = args[0][2]
            assert structured_data["success"] is False

    def test_log_database_operation_without_record_count(self):
        """Test logging database operation without record count."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_database_operation("UPDATE", "products", 50.0)

            args = mock_log.call_args
            assert "(150 records)" not in args[0][1]

            structured_data = args[0][2]
            assert structured_data["record_count"] is None

    @patch("time.time", return_value=1234567890.123)
    def test_log_external_api_call_success(self, mock_time):
        """Test logging successful external API call."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_external_api_call("payment_service", "/api/charge", "POST", 200.5, 201, True)

            mock_log.assert_called_once()
            args = mock_log.call_args

            assert args[0][0] == LogLevel.INFO
            assert args[0][1] == "API Call: POST payment_service/api/charge - 200.50ms [201]"

            structured_data = args[0][2]
            assert structured_data["event_type"] == "external_api_call"
            assert structured_data["service_name"] == "payment_service"
            assert structured_data["api_endpoint"] == "/api/charge"
            assert structured_data["http_method"] == "POST"
            assert structured_data["duration_ms"] == 200.5
            assert structured_data["status_code"] == 201
            assert structured_data["success"] is True

    def test_log_external_api_call_failure(self):
        """Test logging failed external API call."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_external_api_call("user_service", "/api/users/123", "GET", 5000.0, 500, False)

            args = mock_log.call_args
            assert args[0][0] == LogLevel.ERROR

    def test_log_external_api_call_without_status_code(self):
        """Test logging external API call without status code."""
        with patch.object(self.logger, "log_with_level") as mock_log:
            self.logger.log_external_api_call("service", "/endpoint", "GET", 100.0, success=True)

            args = mock_log.call_args
            assert "[" not in args[0][1] or "]" not in args[0][1]  # No status code in message

            structured_data = args[0][2]
            assert structured_data["status_code"] is None

    def test_get_active_spans(self):
        """Test getting active spans."""
        span1_id = self.logger.start_span("operation1")
        span2_id = self.logger.start_span("operation2", span1_id)

        active_spans = self.logger.get_active_spans()

        assert len(active_spans) == 2
        assert span1_id in active_spans
        assert span2_id in active_spans
        assert active_spans[span1_id]["span_name"] == "operation1"
        assert active_spans[span2_id]["parent_span_id"] == span1_id

    def test_get_active_spans_returns_copy(self):
        """Test that get_active_spans returns a copy, not the original dict."""
        span_id = self.logger.start_span("test_operation")

        active_spans = self.logger.get_active_spans()
        active_spans.clear()  # Modify the returned dict

        # Original should still have the span
        assert len(self.logger._active_spans) == 1
        assert span_id in self.logger._active_spans

    def test_clear_active_spans(self):
        """Test clearing all active spans."""
        span1_id = self.logger.start_span("operation1")
        span2_id = self.logger.start_span("operation2")

        assert len(self.logger._active_spans) == 2

        with patch.object(self.logger, "end_span") as mock_end_span:
            self.logger.clear_active_spans()

            # Should call end_span for each active span
            assert mock_end_span.call_count == 2

            # Check that end_span was called with correct parameters
            calls = mock_end_span.call_args_list
            span_ids_ended = {call[0][0] for call in calls}
            assert span_ids_ended == {span1_id, span2_id}

            # All calls should have success=False and forced_cleanup metadata
            for call in calls:
                assert call[1]["success"] is False
                assert call[1]["metadata"]["reason"] == "forced_cleanup"

    def test_clear_active_spans_empty(self):
        """Test clearing active spans when none exist."""
        assert len(self.logger._active_spans) == 0

        # Should not raise any exceptions
        self.logger.clear_active_spans()

        assert len(self.logger._active_spans) == 0


class TestStructuredLoggerIntegration:
    """Integration tests for StructuredLogger."""

    def test_span_lifecycle_integration(self):
        """Test complete span lifecycle."""
        logger = StructuredLogger("test.logger", LogLevel.DEBUG)

        # Start parent span
        with patch("time.time", return_value=1000.0):
            parent_span_id = logger.start_span("parent_operation")

        # Start child span
        with patch("time.time", return_value=1000.1):
            child_span_id = logger.start_span("child_operation", parent_span_id)

        # End child span
        with patch("time.time", return_value=1000.3):
            logger.end_span(child_span_id, True, {"result": "success"})

        # End parent span
        with patch("time.time", return_value=1000.5):
            logger.end_span(parent_span_id, True)

        # All spans should be completed
        assert len(logger.get_active_spans()) == 0

    def test_request_lifecycle_integration(self):
        """Test complete request lifecycle logging."""
        logger = StructuredLogger("test.logger", LogLevel.INFO)

        request_id = "req-12345"
        headers = {"Content-Type": "application/json"}

        # Log request start
        with patch("time.time", return_value=1000.0):
            logger.log_request_start(request_id, "POST", "/api/users", headers)

        # Log some operations during request
        logger.log_database_operation("INSERT", "users", 25.0, True, 1)
        logger.log_external_api_call("email_service", "/send", "POST", 150.0, 200, True)
        logger.log_metric("request_processing_time", 175.0, "ms")

        # Log request end
        with patch("time.time", return_value=1000.2):
            logger.log_request_end(request_id, 201, 200.0, 512)

        # Test that all logging calls work together without conflicts
        assert len(logger.get_active_spans()) == 0  # No spans should be left active

    def test_performance_monitoring_integration(self):
        """Test performance monitoring with spans and metrics."""
        logger = StructuredLogger("test.logger", LogLevel.INFO)

        # Start operation span
        with patch("time.time", return_value=1000.0):
            span_id = logger.start_span("complex_operation")

        # Log various performance metrics during operation
        logger.log_performance("database_query", 50.0, True, {"query": "SELECT * FROM users"})
        logger.log_performance("cache_lookup", 5.0, True, {"cache_hit": True})
        logger.log_performance("external_api", 200.0, False, {"timeout": True})

        # Log final metrics
        logger.log_metric("total_queries", 3)
        logger.log_metric("cache_hit_rate", 0.67, "ratio")

        # End operation span
        with patch("time.time", return_value=1000.3):
            logger.end_span(span_id, False, {"reason": "external_api_timeout"})

        # Verify clean state
        assert len(logger.get_active_spans()) == 0
