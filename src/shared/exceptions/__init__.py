"""Custom exception types for the application."""

from .base import (
    BaseApplicationException,
    ValidationException,
    BusinessLogicException,
    ExternalServiceException,
    RetryableException,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext
)
from .domain import (
    DomainException,
    InvalidAddressException,
    ProviderUnavailableException,
    OfferValidationException,
    ConnectionSessionException,
    SearchResultException,
    RateLimitExceededException,
    DataParsingException,
    ConfigurationException,
    SearchRequestException,
    ProcessingException,
    ConnectionException,
    ShareTokenNotFoundException,
    ShareResultsException
)
from .infrastructure import (
    InfrastructureException,
    DatabaseConnectionException,
    MessageQueueException,
    ExternalServiceException,
    StorageException,
    ConnectionManagerException,
    LoggingException
)

__all__ = [
    # Base exceptions
    'BaseApplicationException',
    'ValidationException',
    'BusinessLogicException',
    'ExternalServiceException',
    'RetryableException',
    'ErrorSeverity',
    'ErrorCategory',
    'ErrorContext',
    
    # Domain exceptions
    'DomainException',
    'InvalidAddressException',
    'ProviderUnavailableException',
    'OfferValidationException',
    'ConnectionSessionException',
    'SearchResultException',
    'RateLimitExceededException',
    'DataParsingException',
    'ConfigurationException',
    'SearchRequestException',
    'ProcessingException',
    'ConnectionException',
    'ShareTokenNotFoundException',
    'ShareResultsException',
    
    # Infrastructure exceptions
    'InfrastructureException',
    'DatabaseConnectionException',
    'MessageQueueException',
    'ExternalServiceException',
    'StorageException',
    'ConnectionManagerException',
    'LoggingException',
]