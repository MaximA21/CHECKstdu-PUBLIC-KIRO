"""Retry handling middleware for graceful degradation."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Callable, Any, Optional, Dict, List, Type
from functools import wraps

from ..exceptions import (
    BaseApplicationException,
    RetryableException,
    ExternalServiceException,
    InfrastructureException,
    ErrorSeverity
)
from ...application.interfaces.logging import ILogger


class RetryHandler(ABC):
    """Base class for retry handling strategies."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        logger: Optional[ILogger] = None
    ):
        """Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            logger: Logger instance for retry events
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logger
    
    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Get delay for the given attempt number."""
        pass
    
    @abstractmethod
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if the operation should be retried."""
        pass
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_error = e
                
                if attempt == self.max_retries or not self.should_retry(e, attempt):
                    break
                
                delay = self.get_delay(attempt)
                
                if self.logger:
                    self.logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_retries} after {delay}s",
                        {
                            'error': str(e),
                            'attempt': attempt + 1,
                            'delay': delay,
                            'function': func.__name__
                        }
                    )
                
                await asyncio.sleep(delay)
        
        # If we get here, all retries failed
        if self.logger:
            self.logger.error(
                f"All retry attempts failed for {func.__name__}",
                {
                    'error': str(last_error),
                    'max_retries': self.max_retries,
                    'function': func.__name__
                }
            )
        
        raise last_error


class ExponentialBackoffRetryHandler(RetryHandler):
    """Retry handler with exponential backoff strategy."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        logger: Optional[ILogger] = None
    ):
        """Initialize exponential backoff retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            backoff_multiplier: Multiplier for exponential backoff
            max_delay: Maximum delay between retries
            jitter: Whether to add random jitter to delays
            retryable_exceptions: List of exception types that should trigger retries
            logger: Logger instance for retry events
        """
        super().__init__(max_retries, base_delay, logger)
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [
            RetryableException,
            ExternalServiceException,
            InfrastructureException
        ]
    
    def get_delay(self, attempt: int) -> float:
        """Get exponential backoff delay with optional jitter."""
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        
        return delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if error is retryable."""
        # Check if it's a retryable exception type
        if isinstance(error, RetryableException):
            return error.should_retry()
        
        # Check if it's in our list of retryable exceptions
        for exc_type in self.retryable_exceptions:
            if isinstance(error, exc_type):
                # Don't retry critical errors
                if isinstance(error, BaseApplicationException):
                    return error.severity != ErrorSeverity.CRITICAL
                return True
        
        return False


class GracefulDegradationHandler:
    """Handler for graceful service degradation."""
    
    def __init__(
        self,
        fallback_strategies: Optional[Dict[str, Callable]] = None,
        logger: Optional[ILogger] = None
    ):
        """Initialize graceful degradation handler.
        
        Args:
            fallback_strategies: Dictionary of service names to fallback functions
            logger: Logger instance for degradation events
        """
        self.fallback_strategies = fallback_strategies or {}
        self.logger = logger
        self.service_health = {}  # Track service health status
    
    def register_fallback(self, service_name: str, fallback_func: Callable) -> None:
        """Register a fallback strategy for a service."""
        self.fallback_strategies[service_name] = fallback_func
    
    def mark_service_unhealthy(self, service_name: str, error: Exception) -> None:
        """Mark a service as unhealthy."""
        self.service_health[service_name] = {
            'healthy': False,
            'last_error': str(error),
            'timestamp': time.time()
        }
        
        if self.logger:
            self.logger.warning(
                f"Service {service_name} marked as unhealthy",
                {
                    'service': service_name,
                    'error': str(error),
                    'timestamp': time.time()
                }
            )
    
    def mark_service_healthy(self, service_name: str) -> None:
        """Mark a service as healthy."""
        self.service_health[service_name] = {
            'healthy': True,
            'last_error': None,
            'timestamp': time.time()
        }
        
        if self.logger:
            self.logger.info(
                f"Service {service_name} marked as healthy",
                {
                    'service': service_name,
                    'timestamp': time.time()
                }
            )
    
    def is_service_healthy(self, service_name: str) -> bool:
        """Check if a service is healthy."""
        return self.service_health.get(service_name, {}).get('healthy', True)
    
    async def execute_with_fallback(
        self,
        service_name: str,
        primary_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with fallback strategy."""
        try:
            # Try primary function
            if asyncio.iscoroutinefunction(primary_func):
                result = await primary_func(*args, **kwargs)
            else:
                result = primary_func(*args, **kwargs)
            
            # Mark service as healthy if it was previously unhealthy
            if not self.is_service_healthy(service_name):
                self.mark_service_healthy(service_name)
            
            return result
            
        except Exception as e:
            # Mark service as unhealthy
            self.mark_service_unhealthy(service_name, e)
            
            # Try fallback if available
            if service_name in self.fallback_strategies:
                if self.logger:
                    self.logger.info(
                        f"Using fallback strategy for {service_name}",
                        {
                            'service': service_name,
                            'error': str(e),
                            'fallback_available': True
                        }
                    )
                
                fallback_func = self.fallback_strategies[service_name]
                
                try:
                    if asyncio.iscoroutinefunction(fallback_func):
                        return await fallback_func(*args, **kwargs)
                    else:
                        return fallback_func(*args, **kwargs)
                except Exception as fallback_error:
                    if self.logger:
                        self.logger.error(
                            f"Fallback strategy failed for {service_name}",
                            {
                                'service': service_name,
                                'primary_error': str(e),
                                'fallback_error': str(fallback_error)
                            }
                        )
                    raise fallback_error
            else:
                if self.logger:
                    self.logger.error(
                        f"No fallback strategy available for {service_name}",
                        {
                            'service': service_name,
                            'error': str(e),
                            'fallback_available': False
                        }
                    )
                raise e


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    retryable_exceptions: Optional[List[Type[Exception]]] = None
):
    """Decorator for adding retry logic to functions."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            retry_handler = ExponentialBackoffRetryHandler(
                max_retries=max_retries,
                base_delay=base_delay,
                backoff_multiplier=backoff_multiplier,
                retryable_exceptions=retryable_exceptions
            )
            return await retry_handler.execute_with_retry(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            retry_handler = ExponentialBackoffRetryHandler(
                max_retries=max_retries,
                base_delay=base_delay,
                backoff_multiplier=backoff_multiplier,
                retryable_exceptions=retryable_exceptions
            )
            return asyncio.run(retry_handler.execute_with_retry(func, *args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def with_fallback(service_name: str, fallback_func: Callable):
    """Decorator for adding fallback logic to functions."""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            degradation_handler = GracefulDegradationHandler({
                service_name: fallback_func
            })
            return await degradation_handler.execute_with_fallback(
                service_name, func, *args, **kwargs
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            degradation_handler = GracefulDegradationHandler({
                service_name: fallback_func
            })
            return asyncio.run(degradation_handler.execute_with_fallback(
                service_name, func, *args, **kwargs
            ))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator