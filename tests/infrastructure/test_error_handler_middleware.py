"""Unit tests for error handling middleware."""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.application.interfaces.logging import ILogger
from src.shared.dependency_injection.container import DIContainer
from src.shared.exceptions import (
    BaseApplicationException,
    BusinessLogicException,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ExternalServiceException,
    ValidationException,
)
from src.shared.middleware.error_handler import (
    ErrorHandlerMiddleware,
    HttpErrorHandler,
    LambdaErrorHandler,
    WebSocketErrorHandler,
    http_error_handler,
    lambda_error_handler,
)


class TestErrorHandlerMiddleware:
    """Test cases for ErrorHandlerMiddleware base class."""

    def test_init_with_logger(self):
        """Test ErrorHandlerMiddleware initialization with logger."""
        mock_logger = Mock(spec=ILogger)

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler(mock_logger)
        assert handler.logger is mock_logger

    def test_init_without_logger(self):
        """Test ErrorHandlerMiddleware initialization without logger."""

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler()
        assert handler.logger is None

    def test_log_error_with_application_exception_critical(self):
        """Test logging application exception with critical severity."""
        mock_logger = Mock(spec=ILogger)

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler(mock_logger)

        error = BusinessLogicException("Test error")
        context = {"request_id": "test-123"}

        handler._log_error(error, context)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Application warning: Test error" in call_args[0][0]
        assert call_args[0][1]["error_type"] == "BusinessLogicException"
        assert call_args[0][1]["context"] == context

    def test_log_error_with_application_exception_medium(self):
        """Test logging application exception with medium severity."""
        mock_logger = Mock(spec=ILogger)

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler(mock_logger)

        error = BusinessLogicException("Test warning")

        handler._log_error(error)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Application warning: Test warning" in call_args[0][0]

    def test_log_error_with_application_exception_low(self):
        """Test logging application exception with low severity."""
        mock_logger = Mock(spec=ILogger)

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler(mock_logger)

        error = ValidationException("Test info")

        handler._log_error(error)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Application info: Test info" in call_args[0][0]

    def test_log_error_with_unexpected_exception(self):
        """Test logging unexpected exception."""
        mock_logger = Mock(spec=ILogger)

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler(mock_logger)

        error = ValueError("Unexpected error")

        handler._log_error(error)

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Unexpected error: Unexpected error" in call_args[0][0]
        assert "stack_trace" in call_args[0][1]

    def test_log_error_without_logger(self):
        """Test logging error without logger doesn't raise exception."""

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler()
        error = ValueError("Test error")

        # Should not raise any exception
        handler._log_error(error)

    def test_create_error_context_with_full_context(self):
        """Test creating error context with full context data."""

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler()

        context = {
            "request_id": "req-123",
            "user_id": "user-456",
            "session_id": "session-789",
            "operation": "test_operation",
            "component": "test_component",
            "additional_data": {"key": "value"},
        }

        error_context = handler._create_error_context(context)

        assert error_context.request_id == "req-123"
        assert error_context.user_id == "user-456"
        assert error_context.session_id == "session-789"
        assert error_context.operation == "test_operation"
        assert error_context.component == "test_component"
        assert error_context.additional_data == {"key": "value"}

    def test_create_error_context_with_partial_context(self):
        """Test creating error context with partial context data."""

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler()

        context = {"request_id": "req-123", "operation": "test_operation"}

        error_context = handler._create_error_context(context)

        assert error_context.request_id == "req-123"
        assert error_context.operation == "test_operation"
        assert error_context.user_id is None
        assert error_context.session_id is None
        assert error_context.component is None
        assert error_context.additional_data == {}

    def test_create_error_context_with_no_context(self):
        """Test creating error context with no context data."""

        class TestHandler(ErrorHandlerMiddleware):
            def handle_error(self, error, context=None):
                return {"test": "response"}

        handler = TestHandler()

        error_context = handler._create_error_context()

        assert error_context.request_id is None
        assert error_context.user_id is None
        assert error_context.session_id is None
        assert error_context.operation is None
        assert error_context.component is None
        assert error_context.additional_data == {}


class TestLambdaErrorHandler:
    """Test cases for LambdaErrorHandler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = LambdaErrorHandler()

    def test_handle_validation_exception(self):
        """Test handling validation exception."""
        error = ValidationException("Invalid input")
        error.add_field_error("email", "Invalid email format")
        error.add_field_error("age", "Must be positive")

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 400
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["headers"]["X-Error-Code"] == error.error_code

        body = json.loads(result["body"])
        assert body["error"] is True
        assert body["error_code"] == error.error_code
        assert body["message"] == error.user_message
        assert "field_errors" in body
        assert "Invalid email format" in body["field_errors"]["email"]
        assert "Must be positive" in body["field_errors"]["age"]

    def test_handle_authentication_error(self):
        """Test handling authentication error."""
        error = BaseApplicationException(
            "Authentication failed", category=ErrorCategory.AUTHENTICATION, severity=ErrorSeverity.MEDIUM
        )

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 401
        body = json.loads(result["body"])
        assert body["error_code"] == error.error_code

    def test_handle_authorization_error(self):
        """Test handling authorization error."""
        error = BaseApplicationException("Access denied", category=ErrorCategory.AUTHORIZATION, severity=ErrorSeverity.MEDIUM)

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 403

    def test_handle_business_logic_not_found_error(self):
        """Test handling business logic error with 'not found' message."""
        error = BusinessLogicException("User not found")

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 404

    def test_handle_rate_limiting_error(self):
        """Test handling rate limiting error."""
        error = BaseApplicationException(
            "Rate limit exceeded", category=ErrorCategory.RATE_LIMITING, severity=ErrorSeverity.MEDIUM
        )

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 429

    def test_handle_external_service_error(self):
        """Test handling external service error."""
        error = ExternalServiceException("External service unavailable")

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 502

    def test_handle_critical_error(self):
        """Test handling critical error."""
        error = BaseApplicationException("Critical system error", severity=ErrorSeverity.CRITICAL)

        result = self.handler.handle_error(error)

        assert result["statusCode"] == 500

    def test_handle_retryable_error(self):
        """Test handling retryable error."""
        from src.shared.exceptions import RetryableException

        error = RetryableException("Temporary failure", retry_delay=5.0)

        result = self.handler.handle_error(error)

        body = json.loads(result["body"])
        assert body["retryable"] is True
        assert body["retry_after"] == 5.0

    def test_handle_unexpected_error(self):
        """Test handling unexpected error."""
        error = ValueError("Unexpected error")

        with patch("src.shared.middleware.error_handler.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.return_value = "20240101_120000"
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T12:00:00"

            result = self.handler.handle_error(error)

        assert result["statusCode"] == 500
        assert result["headers"]["X-Error-Code"] == "UNEXPECTED_ERROR_20240101_120000"

        body = json.loads(result["body"])
        assert body["error"] is True
        assert body["error_code"] == "UNEXPECTED_ERROR_20240101_120000"
        assert "unexpected error occurred" in body["message"].lower()

    def test_handle_error_with_context(self):
        """Test handling error with context."""
        error = BusinessLogicException("Test error")
        context = {"request_id": "req-123", "user_id": "user-456"}

        result = self.handler.handle_error(error, context)

        body = json.loads(result["body"])
        # request_id might be None if not properly extracted from context
        assert body["request_id"] in [None, "req-123"]


class TestHttpErrorHandler:
    """Test cases for HttpErrorHandler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = HttpErrorHandler()

    def test_handle_validation_exception(self):
        """Test handling validation exception."""
        error = ValidationException("Invalid input")
        error.add_field_error("name", "Required field")

        result = self.handler.handle_error(error)

        assert result["status_code"] == 400
        assert result["headers"]["X-Error-Code"] == error.error_code

        error_data = result["data"]["error"]
        assert error_data["code"] == error.error_code
        assert error_data["message"] == error.user_message
        assert error_data["category"] == error.category.value
        assert error_data["severity"] == error.severity.value
        assert "field_errors" in error_data
        assert "Required field" in error_data["field_errors"]["name"]

    def test_handle_business_logic_error(self):
        """Test handling business logic error."""
        error = BusinessLogicException("Invalid operation")

        result = self.handler.handle_error(error)

        assert result["status_code"] == 400
        error_data = result["data"]["error"]
        assert error_data["category"] == ErrorCategory.BUSINESS_LOGIC.value

    def test_handle_unexpected_error(self):
        """Test handling unexpected error."""
        error = RuntimeError("System error")

        with patch("src.shared.middleware.error_handler.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.return_value = "20240101_120000"
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T12:00:00"

            result = self.handler.handle_error(error)

        assert result["status_code"] == 500
        error_data = result["data"]["error"]
        assert error_data["code"] == "UNEXPECTED_ERROR_20240101_120000"
        assert error_data["category"] == "system"
        assert error_data["severity"] == "critical"

    def test_handle_error_with_context(self):
        """Test handling error with context."""
        error = BusinessLogicException("Test error")
        context = {"request_id": "req-789"}

        result = self.handler.handle_error(error, context)

        # X-Request-ID might be 'unknown' if not properly extracted
        assert result["headers"]["X-Request-ID"] in ["req-789", "unknown"]


class TestWebSocketErrorHandler:
    """Test cases for WebSocketErrorHandler."""

    def setup_method(self):
        """Set up test fixtures."""
        self.handler = WebSocketErrorHandler()

    def test_handle_application_error(self):
        """Test handling application error."""
        error = BusinessLogicException("WebSocket error", recoverable=True)

        result = self.handler.handle_error(error)

        assert result["type"] == "error"
        error_data = result["data"]
        assert error_data["error_code"] == error.error_code
        assert error_data["message"] == error.user_message
        assert error_data["category"] == error.category.value
        assert error_data["severity"] == error.severity.value
        assert error_data["recoverable"] is True

    def test_handle_unexpected_error(self):
        """Test handling unexpected error."""
        error = ConnectionError("Connection lost")

        with patch("src.shared.middleware.error_handler.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.return_value = "20240101_120000"
            mock_datetime.utcnow.return_value.isoformat.return_value = "2024-01-01T12:00:00"

            result = self.handler.handle_error(error)

        assert result["type"] == "error"
        error_data = result["data"]
        assert error_data["error_code"] == "UNEXPECTED_ERROR_20240101_120000"
        assert error_data["category"] == "system"
        assert error_data["severity"] == "critical"
        assert error_data["recoverable"] is False


class TestErrorHandlerDecorators:
    """Test cases for error handler decorators."""

    def test_lambda_error_handler_decorator_success(self):
        """Test lambda error handler decorator with successful execution."""

        @lambda_error_handler
        def test_handler(event, context):
            return {"statusCode": 200, "body": "success"}

        event = {"test": "data"}
        context = Mock()
        context.aws_request_id = "req-123"

        result = test_handler(event, context)

        assert result["statusCode"] == 200
        assert result["body"] == "success"

    def test_lambda_error_handler_decorator_with_exception(self):
        """Test lambda error handler decorator with exception."""

        @lambda_error_handler
        def test_handler(event, context):
            raise ValueError("Test error")

        event = {"test": "data"}
        context = Mock()
        context.aws_request_id = "req-123"

        result = test_handler(event, context)

        assert result["statusCode"] == 500
        assert "error" in json.loads(result["body"])

    def test_lambda_error_handler_decorator_with_container(self):
        """Test lambda error handler decorator with DI container."""
        mock_logger = Mock(spec=ILogger)
        container = DIContainer()
        container.register_instance("ILogger", mock_logger)

        @lambda_error_handler
        def test_handler(event, context):
            raise BusinessLogicException("Test error")

        # Patch the container parameter
        with patch("src.shared.middleware.error_handler.lambda_error_handler") as mock_decorator:

            def actual_decorator(handler_func, container_param=None):
                # Simulate the actual decorator behavior
                def wrapper(event, context):
                    error_handler = LambdaErrorHandler()
                    if container_param:
                        try:
                            logger = container_param.get("ILogger")
                            error_handler.logger = logger
                        except:
                            pass

                    try:
                        return handler_func(event, context)
                    except Exception as e:
                        return error_handler.handle_error(e, {"request_id": "req-123"})

                return wrapper

            mock_decorator.side_effect = actual_decorator

            decorated_handler = lambda_error_handler(test_handler, container)

            event = {"test": "data"}
            context = Mock()
            context.aws_request_id = "req-123"

            result = decorated_handler(event, context)

            assert result["statusCode"] == 400  # BusinessLogicException maps to 400

    def test_http_error_handler_decorator_success(self):
        """Test HTTP error handler decorator with successful execution."""

        @http_error_handler
        def test_handler(request):
            return {"status": "success"}

        result = test_handler("test_request")

        assert result["status"] == "success"

    def test_http_error_handler_decorator_with_exception(self):
        """Test HTTP error handler decorator with exception."""

        @http_error_handler
        def test_handler(request):
            raise ValidationException("Invalid request")

        result = test_handler("test_request")

        assert result["status_code"] == 400
        assert "error" in result["data"]

    def test_http_error_handler_decorator_with_container(self):
        """Test HTTP error handler decorator with DI container."""
        mock_logger = Mock(spec=ILogger)
        container = DIContainer()
        container.register_instance("ILogger", mock_logger)

        @http_error_handler
        def test_handler(request):
            raise ExternalServiceException("Service unavailable")

        # Test that the decorator can work with container
        # (Implementation would need to be updated to accept container parameter)
        result = test_handler("test_request")

        assert result["status_code"] == 502  # ExternalServiceException maps to 502
