"""Infrastructure-related exception classes."""

from .base import (
    BaseApplicationException,
    RetryableException,
    ExternalServiceException as BaseExternalServiceException,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext
)
from typing import Optional, Dict, Any


class InfrastructureException(BaseApplicationException):
    """Base exception for infrastructure-related errors."""
    
    def __init__(self, message: str, **kwargs):
        """Initialize infrastructure exception."""
        super().__init__(
            message,
            severity=kwargs.get('severity', ErrorSeverity.HIGH),
            category=kwargs.get('category', ErrorCategory.SYSTEM),
            **kwargs
        )


class DatabaseConnectionException(RetryableException):
    """Exception raised when database connection fails."""
    
    def __init__(
        self, 
        message: str, 
        database_name: Optional[str] = None,
        connection_string: Optional[str] = None,
        **kwargs
    ):
        """Initialize database connection exception."""
        context = kwargs.get('context', ErrorContext())
        context.additional_data.update({
            'database_name': database_name,
            'connection_string': connection_string[:50] + '...' if connection_string else None
        })
        
        super().__init__(
            message,
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.DATABASE,
            context=context,
            max_retries=kwargs.get('max_retries', 3),
            retry_delay=kwargs.get('retry_delay', 2.0),
            **kwargs
        )
        self.database_name = database_name
        self.connection_string = connection_string


class MessageQueueException(RetryableException):
    """Exception raised when message queue operations fail."""
    
    def __init__(
        self, 
        message: str, 
        queue_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """Initialize message queue exception."""
        context = kwargs.get('context', ErrorContext())
        context.additional_data.update({
            'queue_name': queue_name,
            'operation': operation
        })
        
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.SYSTEM,
            context=context,
            max_retries=kwargs.get('max_retries', 5),
            retry_delay=kwargs.get('retry_delay', 1.0),
            **kwargs
        )
        self.queue_name = queue_name
        self.operation = operation


class ExternalServiceException(BaseExternalServiceException):
    """Exception raised when external service calls fail."""
    
    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs
    ):
        """Initialize external service exception."""
        super().__init__(
            message,
            service_name=service_name,
            status_code=status_code,
            response_body=response_body,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL_SERVICE,
            **kwargs
        )


class StorageException(RetryableException):
    """Exception raised when storage operations fail."""
    
    def __init__(
        self, 
        message: str, 
        operation: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize storage exception."""
        context = kwargs.get('context', ErrorContext())
        context.additional_data.update({
            'operation': operation,
            'resource_id': resource_id
        })
        
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATABASE,
            context=context,
            max_retries=kwargs.get('max_retries', 3),
            retry_delay=kwargs.get('retry_delay', 1.5),
            **kwargs
        )
        self.operation = operation
        self.resource_id = resource_id


class ConnectionManagerException(InfrastructureException):
    """Exception raised when connection management fails."""
    
    def __init__(
        self, 
        message: str, 
        connection_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """Initialize connection manager exception."""
        context = kwargs.get('context', ErrorContext())
        context.additional_data.update({
            'connection_id': connection_id,
            'operation': operation
        })
        
        super().__init__(
            message,
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.NETWORK,
            context=context,
            **kwargs
        )
        self.connection_id = connection_id
        self.operation = operation


class LoggingException(InfrastructureException):
    """Exception raised when logging operations fail."""
    
    def __init__(
        self, 
        message: str, 
        logger_name: Optional[str] = None,
        log_level: Optional[str] = None,
        **kwargs
    ):
        """Initialize logging exception."""
        context = kwargs.get('context', ErrorContext())
        context.additional_data.update({
            'logger_name': logger_name,
            'log_level': log_level
        })
        
        super().__init__(
            message,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM,
            context=context,
            recoverable=True,
            **kwargs
        )
        self.logger_name = logger_name
        self.log_level = log_level