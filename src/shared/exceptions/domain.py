"""Domain-specific exceptions for the application."""

from typing import Any, Dict, Optional

from .base import (
    BaseApplicationException,
    BusinessLogicException,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ValidationException,
)


class DomainException(BaseApplicationException):
    """Base exception for domain-related errors."""

    def __init__(self, message: str, **kwargs):
        """Initialize domain exception."""
        # Set defaults only if not already provided
        if "severity" not in kwargs:
            kwargs["severity"] = ErrorSeverity.MEDIUM
        if "category" not in kwargs:
            kwargs["category"] = ErrorCategory.BUSINESS_LOGIC

        super().__init__(message, **kwargs)


class InvalidAddressException(ValidationException):
    """Exception raised when an address is invalid or not supported."""

    def __init__(self, message: str, address: Optional[str] = None, **kwargs):
        """Initialize with message and optional address."""
        context = kwargs.get("context", ErrorContext())
        if address:
            context.additional_data["address"] = address

        # Remove severity and category from kwargs since ValidationException sets them
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["severity", "category"]}

        super().__init__(message, context=context, **filtered_kwargs)
        self.address = address


class ProviderUnavailableException(DomainException):
    """Exception raised when a provider service is unavailable."""

    def __init__(self, message: str, provider_name: Optional[str] = None, **kwargs):
        """Initialize with message and optional provider name."""
        context = kwargs.get("context", ErrorContext())
        if provider_name:
            context.additional_data["provider_name"] = provider_name

        # Set specific values for this exception type
        kwargs.update(
            {
                "severity": ErrorSeverity.HIGH,
                "category": ErrorCategory.EXTERNAL_SERVICE,
                "context": context,
                "recoverable": True,
            }
        )

        super().__init__(message, **kwargs)
        self.provider_name = provider_name


class OfferValidationException(ValidationException):
    """Exception raised when an offer fails validation."""

    def __init__(self, message: str, offer_data: Optional[Dict[str, Any]] = None, **kwargs):
        """Initialize with message and optional offer data."""
        context = kwargs.get("context", ErrorContext())
        if offer_data:
            context.additional_data["offer_data"] = offer_data

        # Remove severity and category from kwargs since ValidationException sets them
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ["severity", "category"]}

        super().__init__(message, context=context, **filtered_kwargs)
        self.offer_data = offer_data


class ConnectionSessionException(DomainException):
    """Exception raised for connection session related errors."""

    def __init__(self, message: str, session_id: Optional[str] = None, **kwargs):
        """Initialize with message and optional session ID."""
        context = kwargs.get("context", ErrorContext())
        if session_id:
            context.additional_data["session_id"] = session_id

        kwargs.update({"severity": ErrorSeverity.MEDIUM, "category": ErrorCategory.BUSINESS_LOGIC, "context": context})

        super().__init__(message, **kwargs)
        self.session_id = session_id


class SearchResultException(DomainException):
    """Exception raised for search result related errors."""

    def __init__(self, message: str, request_id: Optional[str] = None, **kwargs):
        """Initialize with message and optional request ID."""
        context = kwargs.get("context", ErrorContext())
        if request_id:
            context.additional_data["request_id"] = request_id

        kwargs.update({"severity": ErrorSeverity.MEDIUM, "category": ErrorCategory.BUSINESS_LOGIC, "context": context})

        super().__init__(message, **kwargs)
        self.request_id = request_id


class RateLimitExceededException(DomainException):
    """Exception raised when rate limits are exceeded."""

    def __init__(self, message: str, provider_name: Optional[str] = None, retry_after: Optional[int] = None, **kwargs):
        """Initialize with message, provider name, and retry time."""
        context = kwargs.get("context", ErrorContext())
        context.additional_data.update({"provider_name": provider_name, "retry_after": retry_after})

        kwargs.update(
            {
                "severity": ErrorSeverity.MEDIUM,
                "category": ErrorCategory.RATE_LIMITING,
                "context": context,
                "recoverable": True,
            }
        )

        super().__init__(message, **kwargs)
        self.provider_name = provider_name
        self.retry_after = retry_after


class DataParsingException(DomainException):
    """Exception raised when data parsing fails."""

    def __init__(self, message: str, data_type: Optional[str] = None, raw_data: Optional[str] = None, **kwargs):
        """Initialize with message, data type, and optional raw data."""
        context = kwargs.get("context", ErrorContext())
        context.additional_data.update(
            {"data_type": data_type, "raw_data": raw_data[:1000] if raw_data else None}  # Truncate large data
        )

        kwargs.update({"severity": ErrorSeverity.MEDIUM, "category": ErrorCategory.DATA_PROCESSING, "context": context})

        super().__init__(message, **kwargs)
        self.data_type = data_type
        self.raw_data = raw_data


class ConfigurationException(DomainException):
    """Exception raised for configuration-related errors."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        """Initialize with message and optional config key."""
        context = kwargs.get("context", ErrorContext())
        if config_key:
            context.additional_data["config_key"] = config_key

        kwargs.update({"severity": ErrorSeverity.HIGH, "category": ErrorCategory.CONFIGURATION, "context": context})

        super().__init__(message, **kwargs)
        self.config_key = config_key


class SearchRequestException(DomainException):
    """Exception raised when a search request fails."""

    def __init__(self, message: str, request_id: Optional[str] = None, **kwargs):
        """Initialize with message and optional request ID."""
        context = kwargs.get("context", ErrorContext())
        if request_id:
            context.additional_data["request_id"] = request_id

        kwargs.update({"severity": ErrorSeverity.MEDIUM, "category": ErrorCategory.BUSINESS_LOGIC, "context": context})

        super().__init__(message, **kwargs)
        self.request_id = request_id


class ProcessingException(DomainException):
    """Exception raised when result processing fails."""

    def __init__(self, message: str, provider_name: Optional[str] = None, **kwargs):
        """Initialize with message and optional provider name."""
        context = kwargs.get("context", ErrorContext())
        if provider_name:
            context.additional_data["provider_name"] = provider_name

        kwargs.update({"severity": ErrorSeverity.MEDIUM, "category": ErrorCategory.DATA_PROCESSING, "context": context})

        super().__init__(message, **kwargs)
        self.provider_name = provider_name


class ConnectionException(DomainException):
    """Exception raised for connection management errors."""

    def __init__(self, message: str, connection_id: Optional[str] = None, **kwargs):
        """Initialize with message and optional connection ID."""
        context = kwargs.get("context", ErrorContext())
        if connection_id:
            context.additional_data["connection_id"] = connection_id

        kwargs.update({"severity": ErrorSeverity.HIGH, "category": ErrorCategory.NETWORK, "context": context})

        super().__init__(message, **kwargs)
        self.connection_id = connection_id


class ShareTokenNotFoundException(DomainException):
    """Exception raised when a share token is not found or expired."""

    def __init__(self, message: str, share_token: Optional[str] = None, **kwargs):
        """Initialize with message and optional share token."""
        context = kwargs.get("context", ErrorContext())
        if share_token:
            context.additional_data["share_token"] = share_token

        kwargs.update(
            {
                "severity": ErrorSeverity.LOW,
                "category": ErrorCategory.BUSINESS_LOGIC,
                "context": context,
                "user_message": "The requested content was not found or has expired.",
            }
        )

        super().__init__(message, **kwargs)
        self.share_token = share_token


class ShareResultsException(DomainException):
    """Exception raised for share results related errors."""

    def __init__(self, message: str, share_token: Optional[str] = None, **kwargs):
        """Initialize with message and optional share token."""
        context = kwargs.get("context", ErrorContext())
        if share_token:
            context.additional_data["share_token"] = share_token

        kwargs.update({"severity": ErrorSeverity.MEDIUM, "category": ErrorCategory.BUSINESS_LOGIC, "context": context})

        super().__init__(message, **kwargs)
        self.share_token = share_token


class AuthorizationException(DomainException):
    """Exception raised for authorization-related errors."""

    def __init__(self, message: str, user_id: Optional[str] = None, resource: Optional[str] = None, **kwargs):
        """Initialize with message and optional user ID and resource."""
        context = kwargs.get("context", ErrorContext())
        if user_id:
            context.additional_data["user_id"] = user_id
        if resource:
            context.additional_data["resource"] = resource

        kwargs.update(
            {
                "severity": ErrorSeverity.HIGH,
                "category": ErrorCategory.SECURITY,
                "context": context,
                "user_message": "Access denied. You don't have permission to access this resource.",
            }
        )

        super().__init__(message, **kwargs)
        self.user_id = user_id
        self.resource = resource
