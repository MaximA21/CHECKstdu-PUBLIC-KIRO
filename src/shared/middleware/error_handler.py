"""Error handling middleware for different entry points."""

import json
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime

from ..exceptions import (
    BaseApplicationException,
    ValidationException,
    BusinessLogicException,
    ExternalServiceException,
    InfrastructureException,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
)
from ..dependency_injection.container import DIContainer
from ...application.interfaces.logging import ILogger


class ErrorHandlerMiddleware(ABC):
    """Base class for error handling middleware."""

    def __init__(self, logger: Optional[ILogger] = None):
        """Initialize error handler middleware."""
        self.logger = logger

    @abstractmethod
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an error and return appropriate response."""
        pass

    def _log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Log error with appropriate level based on severity."""
        if not self.logger:
            return

        error_data = {"error_type": type(error).__name__, "error_message": str(error), "context": context or {}}

        if isinstance(error, BaseApplicationException):
            error_data.update(error.to_dict())

            if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
                self.logger.error(f"Application error: {error.message}", error_data)
            elif error.severity == ErrorSeverity.MEDIUM:
                self.logger.warning(f"Application warning: {error.message}", error_data)
            else:
                self.logger.info(f"Application info: {error.message}", error_data)
        else:
            error_data["stack_trace"] = traceback.format_exc()
            self.logger.error(f"Unexpected error: {str(error)}", error_data)

    def _create_error_context(self, context: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """Create error context from request context."""
        error_context = ErrorContext()

        if context:
            error_context.request_id = context.get("request_id")
            error_context.user_id = context.get("user_id")
            error_context.session_id = context.get("session_id")
            error_context.operation = context.get("operation")
            error_context.component = context.get("component")
            error_context.additional_data = context.get("additional_data", {})

        return error_context


class LambdaErrorHandler(ErrorHandlerMiddleware):
    """Error handler for AWS Lambda functions."""

    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle error and return Lambda-compatible response."""
        self._log_error(error, context)

        if isinstance(error, BaseApplicationException):
            return self._handle_application_error(error)
        else:
            return self._handle_unexpected_error(error)

    def _handle_application_error(self, error: BaseApplicationException) -> Dict[str, Any]:
        """Handle application-specific errors."""
        status_code = self._get_http_status_code(error)

        response_body = {
            "error": True,
            "error_code": error.error_code,
            "message": error.user_message,
            "timestamp": error.context.timestamp.isoformat(),
            "request_id": error.context.request_id,
        }

        # Add field errors for validation exceptions
        if isinstance(error, ValidationException) and error.has_field_errors():
            response_body["field_errors"] = error.field_errors

        # Add retry information for retryable errors
        if hasattr(error, "should_retry") and error.should_retry():
            response_body["retryable"] = True
            response_body["retry_after"] = getattr(error, "get_retry_delay", lambda: 1.0)()

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "X-Error-Code": error.error_code,
                "X-Request-ID": error.context.request_id or "unknown",
            },
            "body": json.dumps(response_body),
        }

    def _handle_unexpected_error(self, error: Exception) -> Dict[str, Any]:
        """Handle unexpected errors."""
        error_id = f"UNEXPECTED_ERROR_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "X-Error-Code": error_id},
            "body": json.dumps(
                {
                    "error": True,
                    "error_code": error_id,
                    "message": "An unexpected error occurred. Please contact support.",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        }

    def _get_http_status_code(self, error: BaseApplicationException) -> int:
        """Get appropriate HTTP status code for error."""
        if isinstance(error, ValidationException):
            return 400
        elif error.category == ErrorCategory.AUTHENTICATION:
            return 401
        elif error.category == ErrorCategory.AUTHORIZATION:
            return 403
        elif error.category == ErrorCategory.BUSINESS_LOGIC:
            if "not found" in error.message.lower():
                return 404
            return 400
        elif error.category == ErrorCategory.RATE_LIMITING:
            return 429
        elif error.category == ErrorCategory.EXTERNAL_SERVICE:
            return 502
        elif error.severity == ErrorSeverity.CRITICAL:
            return 500
        else:
            return 400


class HttpErrorHandler(ErrorHandlerMiddleware):
    """Error handler for HTTP API endpoints."""

    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle error and return HTTP-compatible response."""
        self._log_error(error, context)

        if isinstance(error, BaseApplicationException):
            return self._handle_application_error(error)
        else:
            return self._handle_unexpected_error(error)

    def _handle_application_error(self, error: BaseApplicationException) -> Dict[str, Any]:
        """Handle application-specific errors."""
        status_code = self._get_http_status_code(error)

        response_data = {
            "error": {
                "code": error.error_code,
                "message": error.user_message,
                "category": error.category.value,
                "severity": error.severity.value,
                "timestamp": error.context.timestamp.isoformat(),
                "request_id": error.context.request_id,
            }
        }

        # Add field errors for validation exceptions
        if isinstance(error, ValidationException) and error.has_field_errors():
            response_data["error"]["field_errors"] = error.field_errors

        return {
            "status_code": status_code,
            "data": response_data,
            "headers": {"X-Error-Code": error.error_code, "X-Request-ID": error.context.request_id or "unknown"},
        }

    def _handle_unexpected_error(self, error: Exception) -> Dict[str, Any]:
        """Handle unexpected errors."""
        error_id = f"UNEXPECTED_ERROR_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        return {
            "status_code": 500,
            "data": {
                "error": {
                    "code": error_id,
                    "message": "An unexpected error occurred. Please contact support.",
                    "category": "system",
                    "severity": "critical",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            },
            "headers": {"X-Error-Code": error_id},
        }

    def _get_http_status_code(self, error: BaseApplicationException) -> int:
        """Get appropriate HTTP status code for error."""
        if isinstance(error, ValidationException):
            return 400
        elif error.category == ErrorCategory.AUTHENTICATION:
            return 401
        elif error.category == ErrorCategory.AUTHORIZATION:
            return 403
        elif error.category == ErrorCategory.BUSINESS_LOGIC:
            if "not found" in error.message.lower():
                return 404
            return 400
        elif error.category == ErrorCategory.RATE_LIMITING:
            return 429
        elif error.category == ErrorCategory.EXTERNAL_SERVICE:
            return 502
        elif error.severity == ErrorSeverity.CRITICAL:
            return 500
        else:
            return 400


class WebSocketErrorHandler(ErrorHandlerMiddleware):
    """Error handler for WebSocket connections."""

    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle error and return WebSocket-compatible response."""
        self._log_error(error, context)

        if isinstance(error, BaseApplicationException):
            return self._handle_application_error(error)
        else:
            return self._handle_unexpected_error(error)

    def _handle_application_error(self, error: BaseApplicationException) -> Dict[str, Any]:
        """Handle application-specific errors."""
        return {
            "type": "error",
            "data": {
                "error_code": error.error_code,
                "message": error.user_message,
                "category": error.category.value,
                "severity": error.severity.value,
                "timestamp": error.context.timestamp.isoformat(),
                "request_id": error.context.request_id,
                "recoverable": error.recoverable,
            },
        }

    def _handle_unexpected_error(self, error: Exception) -> Dict[str, Any]:
        """Handle unexpected errors."""
        error_id = f"UNEXPECTED_ERROR_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        return {
            "type": "error",
            "data": {
                "error_code": error_id,
                "message": "An unexpected error occurred. Please reconnect.",
                "category": "system",
                "severity": "critical",
                "timestamp": datetime.utcnow().isoformat(),
                "recoverable": False,
            },
        }


def lambda_error_handler(handler_func: Callable, container: Optional[DIContainer] = None) -> Callable:
    """Decorator for Lambda function error handling."""

    def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Wrapper function with error handling."""
        error_handler = LambdaErrorHandler()

        # Get logger from container if available
        if container:
            try:
                logger = container.get("ILogger")
                error_handler.logger = logger
            except:
                pass  # Continue without logger if not available

        try:
            # Extract request context
            request_context = {
                "request_id": getattr(context, "aws_request_id", None),
                "operation": handler_func.__name__,
                "component": "lambda_handler",
            }

            return handler_func(event, context)

        except Exception as e:
            return error_handler.handle_error(e, request_context)

    return wrapper


def http_error_handler(handler_func: Callable, container: Optional[DIContainer] = None) -> Callable:
    """Decorator for HTTP endpoint error handling."""

    def wrapper(*args, **kwargs) -> Dict[str, Any]:
        """Wrapper function with error handling."""
        error_handler = HttpErrorHandler()

        # Get logger from container if available
        if container:
            try:
                logger = container.get("ILogger")
                error_handler.logger = logger
            except:
                pass  # Continue without logger if not available

        try:
            return handler_func(*args, **kwargs)

        except Exception as e:
            request_context = {"operation": handler_func.__name__, "component": "http_handler"}
            return error_handler.handle_error(e, request_context)

    return wrapper
