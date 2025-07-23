"""Integration module for comprehensive error handling across the application."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ...application.interfaces.logging import ILogger
from ..exceptions import BaseApplicationException, ErrorContext
from ..monitoring import ErrorMonitor, HealthCheckRegistry
from .circuit_breaker import CircuitBreakerRegistry
from .error_handler import ErrorHandlerMiddleware, LambdaErrorHandler
from .retry_handler import ExponentialBackoffRetryHandler, GracefulDegradationHandler


class ComprehensiveErrorHandler:
    """Comprehensive error handling system that integrates all error handling components."""

    def __init__(
        self,
        logger: Optional[ILogger] = None,
        enable_monitoring: bool = True,
        enable_circuit_breakers: bool = True,
        enable_retry: bool = True,
        enable_health_checks: bool = True,
    ):
        """Initialize comprehensive error handler.

        Args:
            logger: Logger instance for error events
            enable_monitoring: Whether to enable error monitoring
            enable_circuit_breakers: Whether to enable circuit breakers
            enable_retry: Whether to enable retry logic
            enable_health_checks: Whether to enable health checks
        """
        self.logger = logger

        # Initialize components based on configuration
        self.error_monitor = ErrorMonitor(logger=logger) if enable_monitoring else None
        self.circuit_breaker_registry = CircuitBreakerRegistry(logger=logger) if enable_circuit_breakers else None
        self.degradation_handler = GracefulDegradationHandler(logger=logger) if enable_retry else None
        self.health_check_registry = HealthCheckRegistry(logger=logger) if enable_health_checks else None

        # Error handlers for different contexts
        self.lambda_error_handler = LambdaErrorHandler(logger=logger)

        # Alert callbacks
        self.alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        # Setup monitoring alerts if enabled
        if self.error_monitor:
            self.error_monitor.add_alert_callback(self._handle_error_alert)

    def handle_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None, service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle an error comprehensively.

        Args:
            error: The exception that occurred
            context: Additional context information
            service_name: Name of the service where error occurred

        Returns:
            Error response dictionary
        """
        # Record error for monitoring
        if self.error_monitor:
            self.error_monitor.record_error(error, context)

        # Update circuit breaker if service name provided
        if service_name and self.circuit_breaker_registry:
            circuit_breaker = self.circuit_breaker_registry.get_circuit_breaker(service_name)
            # Circuit breaker will be updated when the service is called next time

        # Generate error response
        return self.lambda_error_handler.handle_error(error, context)

    async def execute_with_protection(
        self,
        func: Callable,
        service_name: str,
        context: Optional[Dict[str, Any]] = None,
        enable_retry: bool = True,
        enable_circuit_breaker: bool = True,
        enable_fallback: bool = True,
        fallback_func: Optional[Callable] = None,
        *args,
        **kwargs,
    ) -> Any:
        """Execute a function with comprehensive error protection.

        Args:
            func: Function to execute
            service_name: Name of the service
            context: Execution context
            enable_retry: Whether to enable retry logic
            enable_circuit_breaker: Whether to use circuit breaker
            enable_fallback: Whether to use fallback logic
            fallback_func: Fallback function to use if primary fails
            *args: Arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Function result or fallback result
        """
        # Create error context
        error_context = ErrorContext(
            request_id=context.get("request_id") if context else None,
            operation=func.__name__,
            component=service_name,
            additional_data=context or {},
        )

        try:
            # Execute with circuit breaker protection
            if enable_circuit_breaker and self.circuit_breaker_registry:
                circuit_breaker = self.circuit_breaker_registry.get_circuit_breaker(service_name)

                if enable_retry:
                    # Combine circuit breaker with retry
                    retry_handler = ExponentialBackoffRetryHandler(logger=self.logger)

                    async def protected_func():
                        return await circuit_breaker.call(func, *args, **kwargs)

                    return await retry_handler.execute_with_retry(protected_func)
                else:
                    return await circuit_breaker.call(func, *args, **kwargs)

            elif enable_retry:
                # Just retry without circuit breaker
                retry_handler = ExponentialBackoffRetryHandler(logger=self.logger)
                return await retry_handler.execute_with_retry(func, *args, **kwargs)

            else:
                # Execute directly
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

        except Exception as e:
            # Record error
            if self.error_monitor:
                self.error_monitor.record_error(e, context)

            # Try fallback if enabled and available
            if enable_fallback and fallback_func:
                try:
                    if self.logger:
                        self.logger.info(
                            f"Executing fallback for {service_name}",
                            {"service": service_name, "primary_error": str(e), "fallback_function": fallback_func.__name__},
                        )

                    if asyncio.iscoroutinefunction(fallback_func):
                        return await fallback_func(*args, **kwargs)
                    else:
                        return fallback_func(*args, **kwargs)

                except Exception as fallback_error:
                    if self.logger:
                        self.logger.error(
                            f"Fallback failed for {service_name}",
                            {"service": service_name, "primary_error": str(e), "fallback_error": str(fallback_error)},
                        )
                    raise fallback_error

            # No fallback available or fallback disabled
            raise e

    def register_fallback(self, service_name: str, fallback_func: Callable) -> None:
        """Register a fallback function for a service."""
        if self.degradation_handler:
            self.degradation_handler.register_fallback(service_name, fallback_func)

    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add callback for error alerts."""
        self.alert_callbacks.append(callback)

    def _handle_error_alert(self, alert) -> None:
        """Handle error alerts from monitoring system."""
        alert_data = alert.to_dict()

        # Log alert
        if self.logger:
            self.logger.error(f"Error alert triggered: {alert.title}", alert_data)

        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                if self.logger:
                    self.logger.error(
                        f"Error in alert callback: {str(e)}", {"callback": callback.__name__, "alert_id": alert.alert_id}
                    )

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health information."""
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_monitoring": None,
            "circuit_breakers": None,
            "health_checks": None,
        }

        # Error monitoring data
        if self.error_monitor:
            health_data["error_monitoring"] = {
                "metrics": self.error_monitor.get_metrics().to_dict(),
                "active_alerts": [alert.to_dict() for alert in self.error_monitor.get_active_alerts()],
            }

        # Circuit breaker states
        if self.circuit_breaker_registry:
            health_data["circuit_breakers"] = {
                name: state.value for name, state in self.circuit_breaker_registry.get_all_states().items()
            }

        # Health check results
        if self.health_check_registry:
            health_data["health_checks"] = self.health_check_registry.get_health_summary()

        return health_data

    async def perform_health_checks(self) -> Dict[str, Any]:
        """Perform all registered health checks."""
        if not self.health_check_registry:
            return {"error": "Health checks not enabled"}

        await self.health_check_registry.check_all()
        return self.health_check_registry.get_health_summary()

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers."""
        if self.circuit_breaker_registry:
            self.circuit_breaker_registry.reset_all()

            if self.logger:
                self.logger.info("All circuit breakers reset")

    def clear_error_history(self) -> None:
        """Clear error monitoring history."""
        if self.error_monitor:
            self.error_monitor.clear_history()

            if self.logger:
                self.logger.info("Error monitoring history cleared")


# Global instance for easy access
_global_error_handler: Optional[ComprehensiveErrorHandler] = None


def get_error_handler() -> Optional[ComprehensiveErrorHandler]:
    """Get the global error handler instance."""
    return _global_error_handler


def initialize_error_handler(logger: Optional[ILogger] = None, **kwargs) -> ComprehensiveErrorHandler:
    """Initialize the global error handler."""
    global _global_error_handler
    _global_error_handler = ComprehensiveErrorHandler(logger=logger, **kwargs)
    return _global_error_handler


def handle_error(
    error: Exception, context: Optional[Dict[str, Any]] = None, service_name: Optional[str] = None
) -> Dict[str, Any]:
    """Handle an error using the global error handler."""
    handler = get_error_handler()
    if handler:
        return handler.handle_error(error, context, service_name)
    else:
        # Fallback to basic error handling
        return {
            "statusCode": 500,
            "body": '{"error": "Internal server error"}',
            "headers": {"Content-Type": "application/json"},
        }
