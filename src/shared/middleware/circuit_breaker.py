"""Circuit breaker pattern implementation for service resilience."""

import asyncio
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

from ...application.interfaces.logging import ILogger
from ..exceptions import (
    BaseApplicationException,
    ErrorCategory,
    ErrorSeverity,
    ExternalServiceException,
    InfrastructureException,
)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerException(BaseApplicationException):
    """Exception raised when circuit breaker is open."""

    def __init__(self, service_name: str, **kwargs):
        """Initialize circuit breaker exception."""
        super().__init__(
            f"Circuit breaker is open for service: {service_name}",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.EXTERNAL_SERVICE,
            user_message=f"Service {service_name} is temporarily unavailable. Please try again later.",
            recoverable=True,
            **kwargs,
        )
        self.service_name = service_name


class CircuitBreaker:
    """Circuit breaker implementation for service resilience."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        logger: Optional[ILogger] = None,
    ):
        """Initialize circuit breaker.

        Args:
            service_name: Name of the service being protected
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type that triggers circuit breaker
            logger: Logger instance for circuit breaker events
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.logger = logger

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self._lock = None  # Will be initialized when needed

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        # Initialize lock if not already done
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    if self.logger:
                        self.logger.info(
                            f"Circuit breaker for {self.service_name} moved to HALF_OPEN",
                            {"service": self.service_name, "state": self.state.value},
                        )
                else:
                    if self.logger:
                        self.logger.warning(
                            f"Circuit breaker for {self.service_name} is OPEN, failing fast",
                            {"service": self.service_name, "state": self.state.value},
                        )
                    raise CircuitBreakerException(self.service_name)

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Success - reset circuit breaker if it was half-open
            async with self._lock:
                if self.state == CircuitBreakerState.HALF_OPEN:
                    self._reset()
                    if self.logger:
                        self.logger.info(
                            f"Circuit breaker for {self.service_name} reset to CLOSED",
                            {"service": self.service_name, "state": self.state.value},
                        )

            return result

        except Exception as e:
            async with self._lock:
                if self._is_failure(e):
                    self._record_failure()

                    if self.state == CircuitBreakerState.HALF_OPEN:
                        # Failed during recovery attempt, go back to open
                        self.state = CircuitBreakerState.OPEN
                        if self.logger:
                            self.logger.warning(
                                f"Circuit breaker for {self.service_name} failed during recovery, back to OPEN",
                                {"service": self.service_name, "state": self.state.value, "error": str(e)},
                            )
                    elif self.failure_count >= self.failure_threshold:
                        # Too many failures, open the circuit
                        self.state = CircuitBreakerState.OPEN
                        if self.logger:
                            self.logger.error(
                                f"Circuit breaker for {self.service_name} opened due to failures",
                                {
                                    "service": self.service_name,
                                    "state": self.state.value,
                                    "failure_count": self.failure_count,
                                    "threshold": self.failure_threshold,
                                    "error": str(e),
                                },
                            )

            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _is_failure(self, exception: Exception) -> bool:
        """Determine if exception should be counted as a failure."""
        if isinstance(exception, self.expected_exception):
            # Don't count validation errors as circuit breaker failures
            if isinstance(exception, BaseApplicationException):
                return exception.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]
            return True
        return False

    def _record_failure(self) -> None:
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()

    def _reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self.state

    def get_failure_count(self) -> int:
        """Get current failure count."""
        return self.failure_count

    def force_open(self) -> None:
        """Force circuit breaker to open state."""
        self.state = CircuitBreakerState.OPEN
        self.last_failure_time = time.time()
        if self.logger:
            self.logger.warning(
                f"Circuit breaker for {self.service_name} forced to OPEN",
                {"service": self.service_name, "state": self.state.value},
            )

    def force_close(self) -> None:
        """Force circuit breaker to closed state."""
        self._reset()
        if self.logger:
            self.logger.info(
                f"Circuit breaker for {self.service_name} forced to CLOSED",
                {"service": self.service_name, "state": self.state.value},
            )


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self, logger: Optional[ILogger] = None):
        """Initialize circuit breaker registry."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = logger

    def get_circuit_breaker(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                service_name=service_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                logger=self.logger,
            )

        return self.circuit_breakers[service_name]

    def get_all_states(self) -> Dict[str, CircuitBreakerState]:
        """Get states of all circuit breakers."""
        return {name: cb.get_state() for name, cb in self.circuit_breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.force_close()

        if self.logger:
            self.logger.info("All circuit breakers reset to CLOSED")


def circuit_breaker(
    service_name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0, expected_exception: type = Exception
):
    """Decorator for adding circuit breaker protection to functions."""

    def decorator(func: Callable) -> Callable:
        cb = CircuitBreaker(
            service_name=service_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(cb.call(func, *args, **kwargs))

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
