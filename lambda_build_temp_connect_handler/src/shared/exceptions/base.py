"""Base exception classes with enhanced error handling capabilities."""

import traceback
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


class ErrorSeverity(Enum):
    """Error severity levels for categorizing exceptions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for grouping related exceptions."""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    RATE_LIMITING = "rate_limiting"
    DATA_PROCESSING = "data_processing"
    SYSTEM = "system"


@dataclass
class ErrorContext:
    """Context information for errors."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    operation: Optional[str] = None
    component: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


class BaseApplicationException(Exception):
    """Base exception class for all application exceptions."""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        error_code: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        recoverable: bool = False,
        user_message: Optional[str] = None
    ):
        """Initialize base application exception.
        
        Args:
            message: Technical error message for developers
            severity: Error severity level
            category: Error category for grouping
            error_code: Unique error code for identification
            context: Additional context information
            cause: Original exception that caused this error
            recoverable: Whether the error is recoverable
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.error_code = error_code or self._generate_error_code()
        self.context = context or ErrorContext()
        self.cause = cause
        self.recoverable = recoverable
        self.user_message = user_message or self._generate_user_message()
        self.stack_trace = traceback.format_exc()
        
    def _generate_error_code(self) -> str:
        """Generate a default error code based on exception class."""
        class_name = self.__class__.__name__
        return f"{class_name.upper().replace('EXCEPTION', '_ERROR')}"
    
    def _generate_user_message(self) -> str:
        """Generate a user-friendly error message."""
        if self.severity == ErrorSeverity.CRITICAL:
            return "A critical system error occurred. Please contact support."
        elif self.severity == ErrorSeverity.HIGH:
            return "An error occurred while processing your request. Please try again."
        elif self.severity == ErrorSeverity.MEDIUM:
            return "Unable to complete the operation. Please check your input and try again."
        else:
            return "A minor issue occurred. The operation may still succeed."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and monitoring."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "recoverable": self.recoverable,
            "timestamp": self.context.timestamp.isoformat(),
            "request_id": self.context.request_id,
            "user_id": self.context.user_id,
            "session_id": self.context.session_id,
            "operation": self.context.operation,
            "component": self.context.component,
            "additional_data": self.context.additional_data,
            "cause": str(self.cause) if self.cause else None,
            "stack_trace": self.stack_trace
        }
    
    def __str__(self) -> str:
        """String representation of the exception."""
        return f"[{self.error_code}] {self.message}"
    
    def __repr__(self) -> str:
        """Detailed representation of the exception."""
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"severity={self.severity.value}, "
            f"category={self.category.value}, "
            f"error_code='{self.error_code}', "
            f"recoverable={self.recoverable})"
        )


class RetryableException(BaseApplicationException):
    """Base class for exceptions that support retry logic."""
    
    def __init__(
        self,
        message: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        **kwargs
    ):
        """Initialize retryable exception.
        
        Args:
            message: Error message
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            backoff_multiplier: Multiplier for exponential backoff
            **kwargs: Additional arguments for BaseApplicationException
        """
        super().__init__(message, recoverable=True, **kwargs)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_multiplier = backoff_multiplier
        self.retry_count = 0
    
    def should_retry(self) -> bool:
        """Check if the operation should be retried."""
        return self.retry_count < self.max_retries
    
    def get_retry_delay(self) -> float:
        """Get the delay for the next retry attempt."""
        return self.retry_delay * (self.backoff_multiplier ** self.retry_count)
    
    def increment_retry_count(self) -> None:
        """Increment the retry counter."""
        self.retry_count += 1


class ValidationException(BaseApplicationException):
    """Exception for validation errors."""
    
    def __init__(
        self,
        message: str,
        field_errors: Optional[Dict[str, List[str]]] = None,
        **kwargs
    ):
        """Initialize validation exception.
        
        Args:
            message: Error message
            field_errors: Dictionary of field names to error messages
            **kwargs: Additional arguments for BaseApplicationException
        """
        super().__init__(
            message,
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )
        self.field_errors = field_errors or {}
    
    def add_field_error(self, field: str, error: str) -> None:
        """Add a field-specific error."""
        if field not in self.field_errors:
            self.field_errors[field] = []
        self.field_errors[field].append(error)
    
    def has_field_errors(self) -> bool:
        """Check if there are field-specific errors."""
        return bool(self.field_errors)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary including field errors."""
        result = super().to_dict()
        result["field_errors"] = self.field_errors
        return result


class BusinessLogicException(BaseApplicationException):
    """Exception for business logic violations."""
    
    def __init__(self, message: str, **kwargs):
        """Initialize business logic exception."""
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.BUSINESS_LOGIC,
            **kwargs
        )


class ExternalServiceException(BaseApplicationException):
    """Exception for external service failures."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs
    ):
        """Initialize external service exception.
        
        Args:
            message: Error message
            service_name: Name of the external service
            status_code: HTTP status code if applicable
            response_body: Response body from the service
            **kwargs: Additional arguments for BaseApplicationException
        """
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL_SERVICE,
            **kwargs
        )
        self.service_name = service_name
        self.status_code = status_code
        self.response_body = response_body
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary including service details."""
        result = super().to_dict()
        result.update({
            "service_name": self.service_name,
            "status_code": self.status_code,
            "response_body": self.response_body
        })
        return result