"""Dependency injection container for service management."""

import inspect
import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union

T = TypeVar("T")


class ServiceLifetime(Enum):
    """Service lifetime management options."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceDescriptor:
    """Describes how a service should be created and managed."""

    def __init__(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[[], T], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
        dependencies: Optional[Dict[str, Type]] = None,
    ):
        self.service_type = service_type
        self.implementation = implementation
        self.lifetime = lifetime
        self.dependencies = dependencies or {}
        self._instance: Optional[T] = None
        self._lock = threading.Lock()


class DIContainer:
    """Dependency injection container with service registration and resolution."""

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = threading.Lock()

    def register(
        self,
        service_type: Type[T],
        implementation: Union[Type[T], Callable[[], T], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "DIContainer":
        """Register a service with the container.

        Args:
            service_type: The interface or abstract type
            implementation: The concrete implementation, factory function, or instance
            lifetime: Service lifetime management

        Returns:
            Self for method chaining
        """
        with self._lock:
            # Extract dependencies from constructor if implementation is a class
            dependencies = {}
            if inspect.isclass(implementation) and hasattr(implementation, "__init__"):
                sig = inspect.signature(implementation.__init__)
                for param_name, param in sig.parameters.items():
                    if param_name != "self" and param.annotation != inspect.Parameter.empty:
                        dependencies[param_name] = param.annotation

            descriptor = ServiceDescriptor(
                service_type=service_type, implementation=implementation, lifetime=lifetime, dependencies=dependencies
            )

            self._services[service_type] = descriptor

        return self

    def register_singleton(self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T], T]) -> "DIContainer":
        """Register a service as singleton."""
        return self.register(service_type, implementation, ServiceLifetime.SINGLETON)

    def register_transient(self, service_type: Type[T], implementation: Union[Type[T], Callable[[], T]]) -> "DIContainer":
        """Register a service as transient."""
        return self.register(service_type, implementation, ServiceLifetime.TRANSIENT)

    def register_instance(self, service_type: Type[T], instance: T) -> "DIContainer":
        """Register a specific instance as singleton."""
        with self._lock:
            self._singletons[service_type] = instance
            descriptor = ServiceDescriptor(
                service_type=service_type, implementation=instance, lifetime=ServiceLifetime.SINGLETON
            )
            self._services[service_type] = descriptor
        return self

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance.

        Args:
            service_type: The service type to resolve

        Returns:
            Service instance

        Raises:
            ServiceNotRegisteredException: If service is not registered
            ServiceResolutionException: If service cannot be resolved
        """
        if service_type not in self._services:
            raise ServiceNotRegisteredException(f"Service {service_type.__name__} is not registered")

        descriptor = self._services[service_type]

        try:
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                return self._resolve_singleton(descriptor)
            else:
                return self._create_instance(descriptor)
        except Exception as e:
            raise ServiceResolutionException(f"Failed to resolve service {service_type.__name__}: {str(e)}") from e

    def _resolve_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """Resolve singleton service instance."""
        if descriptor.service_type in self._singletons:
            return self._singletons[descriptor.service_type]

        with descriptor._lock:
            # Double-check locking pattern
            if descriptor.service_type in self._singletons:
                return self._singletons[descriptor.service_type]

            instance = self._create_instance(descriptor)
            self._singletons[descriptor.service_type] = instance
            return instance

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new service instance."""
        implementation = descriptor.implementation

        # If it's already an instance, return it
        if not (inspect.isclass(implementation) or callable(implementation)):
            return implementation

        # If it's a factory function
        if callable(implementation) and not inspect.isclass(implementation):
            return implementation()

        # If it's a class, resolve dependencies and instantiate
        if inspect.isclass(implementation):
            return self._instantiate_class(implementation, descriptor.dependencies)

        raise ServiceResolutionException(f"Cannot create instance from {implementation}")

    def _instantiate_class(self, cls: Type, dependencies: Dict[str, Type]) -> Any:
        """Instantiate a class with dependency injection."""
        if not dependencies:
            return cls()

        # Resolve dependencies
        resolved_deps = {}
        for param_name, dep_type in dependencies.items():
            resolved_deps[param_name] = self.resolve(dep_type)

        return cls(**resolved_deps)

    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered."""
        return service_type in self._services

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
            self._singletons.clear()

    def get(self, service_type: Type[T]) -> T:
        """Alias for resolve method."""
        return self.resolve(service_type)

    def get_logger(self, name: str):
        """Get a logger instance for the given name."""
        # Try to get logger factory from container, fallback to simple logger
        try:
            from ...application.interfaces.logging import ILoggerFactory

            if self.is_registered(ILoggerFactory):
                logger_factory = self.resolve(ILoggerFactory)
                return logger_factory.create_logger(name)
        except:
            pass

        # Fallback to simple logger wrapper
        from ...infrastructure.logging.console_logger import ConsoleLogger

        return ConsoleLogger(name)


class ServiceNotRegisteredException(Exception):
    """Raised when trying to resolve an unregistered service."""

    pass


class ServiceResolutionException(Exception):
    """Raised when service resolution fails."""

    pass
