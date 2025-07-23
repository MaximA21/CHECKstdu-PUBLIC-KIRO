"""Health check system for monitoring service availability."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ...application.interfaces.logging import ILogger


class HealthStatus(Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health information for a component."""

    name: str
    status: HealthStatus
    message: str = ""
    last_check: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "response_time_ms": self.response_time_ms,
            "metadata": self.metadata,
        }


class HealthCheck(ABC):
    """Base class for health checks."""

    def __init__(self, name: str, timeout_seconds: float = 5.0, logger: Optional[ILogger] = None):
        """Initialize health check.

        Args:
            name: Name of the component being checked
            timeout_seconds: Timeout for health check execution
            logger: Logger instance for health check events
        """
        self.name = name
        self.timeout_seconds = timeout_seconds
        self.logger = logger

    @abstractmethod
    async def check_health(self) -> ComponentHealth:
        """Perform health check and return status."""
        pass

    async def execute_check(self) -> ComponentHealth:
        """Execute health check with timeout and error handling."""
        start_time = time.time()

        try:
            # Execute health check with timeout
            health = await asyncio.wait_for(self.check_health(), timeout=self.timeout_seconds)

            # Calculate response time
            response_time = (time.time() - start_time) * 1000
            health.response_time_ms = response_time
            health.last_check = datetime.utcnow()

            if self.logger:
                self.logger.debug(
                    f"Health check completed for {self.name}",
                    {"component": self.name, "status": health.status.value, "response_time_ms": response_time},
                )

            return health

        except asyncio.TimeoutError:
            health = ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout_seconds}s",
                last_check=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

            if self.logger:
                self.logger.warning(
                    f"Health check timeout for {self.name}", {"component": self.name, "timeout": self.timeout_seconds}
                )

            return health

        except Exception as e:
            health = ComponentHealth(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                last_check=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
            )

            if self.logger:
                self.logger.error(
                    f"Health check error for {self.name}",
                    {"component": self.name, "error": str(e), "error_type": type(e).__name__},
                )

            return health


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connections."""

    def __init__(self, name: str, connection_test_func: Callable[[], Any], **kwargs):
        """Initialize database health check.

        Args:
            name: Name of the database
            connection_test_func: Function to test database connection
            **kwargs: Additional arguments for HealthCheck
        """
        super().__init__(name, **kwargs)
        self.connection_test_func = connection_test_func

    async def check_health(self) -> ComponentHealth:
        """Check database health."""
        try:
            # Test database connection
            if asyncio.iscoroutinefunction(self.connection_test_func):
                await self.connection_test_func()
            else:
                self.connection_test_func()

            return ComponentHealth(name=self.name, status=HealthStatus.HEALTHY, message="Database connection successful")

        except Exception as e:
            return ComponentHealth(
                name=self.name, status=HealthStatus.UNHEALTHY, message=f"Database connection failed: {str(e)}"
            )


class ExternalServiceHealthCheck(HealthCheck):
    """Health check for external services."""

    def __init__(self, name: str, service_test_func: Callable[[], Any], degraded_threshold_ms: float = 2000.0, **kwargs):
        """Initialize external service health check.

        Args:
            name: Name of the external service
            service_test_func: Function to test service availability
            degraded_threshold_ms: Response time threshold for degraded status
            **kwargs: Additional arguments for HealthCheck
        """
        super().__init__(name, **kwargs)
        self.service_test_func = service_test_func
        self.degraded_threshold_ms = degraded_threshold_ms

    async def check_health(self) -> ComponentHealth:
        """Check external service health."""
        start_time = time.time()

        try:
            # Test service availability
            if asyncio.iscoroutinefunction(self.service_test_func):
                result = await self.service_test_func()
            else:
                result = self.service_test_func()

            response_time_ms = (time.time() - start_time) * 1000

            # Determine status based on response time
            if response_time_ms > self.degraded_threshold_ms:
                status = HealthStatus.DEGRADED
                message = f"Service responding slowly ({response_time_ms:.1f}ms)"
            else:
                status = HealthStatus.HEALTHY
                message = "Service responding normally"

            return ComponentHealth(
                name=self.name, status=status, message=message, metadata={"result": str(result) if result else None}
            )

        except Exception as e:
            return ComponentHealth(name=self.name, status=HealthStatus.UNHEALTHY, message=f"Service check failed: {str(e)}")


class MemoryHealthCheck(HealthCheck):
    """Health check for memory usage."""

    def __init__(
        self, name: str = "memory", warning_threshold_percent: float = 80.0, critical_threshold_percent: float = 95.0, **kwargs
    ):
        """Initialize memory health check.

        Args:
            name: Name of the health check
            warning_threshold_percent: Memory usage threshold for degraded status
            critical_threshold_percent: Memory usage threshold for unhealthy status
            **kwargs: Additional arguments for HealthCheck
        """
        super().__init__(name, **kwargs)
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent

    async def check_health(self) -> ComponentHealth:
        """Check memory usage."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            usage_percent = memory.percent

            if usage_percent >= self.critical_threshold:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {usage_percent:.1f}%"
            elif usage_percent >= self.warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {usage_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {usage_percent:.1f}%"

            return ComponentHealth(
                name=self.name,
                status=status,
                message=message,
                metadata={
                    "usage_percent": usage_percent,
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                },
            )

        except ImportError:
            return ComponentHealth(
                name=self.name, status=HealthStatus.UNKNOWN, message="psutil not available for memory monitoring"
            )
        except Exception as e:
            return ComponentHealth(name=self.name, status=HealthStatus.UNHEALTHY, message=f"Memory check failed: {str(e)}")


class HealthCheckRegistry:
    """Registry for managing multiple health checks."""

    def __init__(self, logger: Optional[ILogger] = None):
        """Initialize health check registry."""
        self.health_checks: Dict[str, HealthCheck] = {}
        self.logger = logger
        self.last_results: Dict[str, ComponentHealth] = {}

    def register(self, health_check: HealthCheck) -> None:
        """Register a health check."""
        self.health_checks[health_check.name] = health_check

        if self.logger:
            self.logger.info(f"Health check registered: {health_check.name}", {"component": health_check.name})

    def unregister(self, name: str) -> bool:
        """Unregister a health check."""
        if name in self.health_checks:
            del self.health_checks[name]
            if name in self.last_results:
                del self.last_results[name]

            if self.logger:
                self.logger.info(f"Health check unregistered: {name}", {"component": name})
            return True
        return False

    async def check_all(self) -> Dict[str, ComponentHealth]:
        """Execute all registered health checks."""
        if not self.health_checks:
            return {}

        # Execute all health checks concurrently
        tasks = [health_check.execute_check() for health_check in self.health_checks.values()]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        health_results = {}
        for i, result in enumerate(results):
            health_check = list(self.health_checks.values())[i]

            if isinstance(result, Exception):
                # Health check itself failed
                health_results[health_check.name] = ComponentHealth(
                    name=health_check.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check execution failed: {str(result)}",
                    last_check=datetime.utcnow(),
                )
            else:
                health_results[health_check.name] = result

        # Store results
        self.last_results = health_results

        return health_results

    async def check_component(self, name: str) -> Optional[ComponentHealth]:
        """Execute health check for a specific component."""
        if name not in self.health_checks:
            return None

        result = await self.health_checks[name].execute_check()
        self.last_results[name] = result
        return result

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        if not self.last_results:
            return HealthStatus.UNKNOWN

        statuses = [health.status for health in self.last_results.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN

    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        overall_status = self.get_overall_status()

        return {
            "overall_status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {name: health.to_dict() for name, health in self.last_results.items()},
            "registered_checks": list(self.health_checks.keys()),
        }

    def get_unhealthy_components(self) -> List[ComponentHealth]:
        """Get list of unhealthy components."""
        return [health for health in self.last_results.values() if health.status == HealthStatus.UNHEALTHY]

    def get_degraded_components(self) -> List[ComponentHealth]:
        """Get list of degraded components."""
        return [health for health in self.last_results.values() if health.status == HealthStatus.DEGRADED]
