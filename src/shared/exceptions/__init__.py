"""Custom exception types for the application."""

from .base import (
    BaseApplicationException,
    BusinessLogicException,
    ErrorCategory,
    ErrorContext,
    ErrorSeverity,
    ExternalServiceException,
    RetryableException,
    ValidationException,
)
from .domain import (
    ConfigurationException,
    ConnectionException,
    ConnectionSessionException,
    DataParsingException,
    DomainException,
    InvalidAddressException,
    OfferValidationException,
    ProcessingException,
    ProviderUnavailableException,
    RateLimitExceededException,
    SearchRequestException,
    SearchResultException,
    ShareResultsException,
    ShareTokenNotFoundException,
)
from .infrastructure import (
    ConnectionManagerException,
    DatabaseConnectionException,
    ExternalServiceException,
    InfrastructureException,
    LoggingException,
    MessageQueueException,
    StorageException,
)

__all__ = [
    # Base exceptions
    "BaseApplicationException",
    "ValidationException",
    "BusinessLogicException",
    "ExternalServiceException",
    "RetryableException",
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorContext",
    # Domain exceptions
    "DomainException",
    "InvalidAddressException",
    "ProviderUnavailableException",
    "OfferValidationException",
    "ConnectionSessionException",
    "SearchResultException",
    "RateLimitExceededException",
    "DataParsingException",
    "ConfigurationException",
    "SearchRequestException",
    "ProcessingException",
    "ConnectionException",
    "ShareTokenNotFoundException",
    "ShareResultsException",
    # Infrastructure exceptions
    "InfrastructureException",
    "DatabaseConnectionException",
    "MessageQueueException",
    "ExternalServiceException",
    "StorageException",
    "ConnectionManagerException",
    "LoggingException",
]
