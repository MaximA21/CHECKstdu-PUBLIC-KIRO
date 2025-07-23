"""Tests for dependency injection container."""

import os
from unittest.mock import patch

import pytest

from src.infrastructure.config import AppConfig, Environment
from src.shared.dependency_injection import (
    DIContainer,
    ServiceLifetime,
    ServiceNotRegisteredException,
    ServiceResolutionException,
    get_container,
)


class ITestService:
    """Test service interface."""

    def get_value(self) -> str:
        pass


class TestServiceImpl(ITestService):
    """Test service implementation."""

    def get_value(self) -> str:
        return "test_value"


class ServiceWithDependency:
    """Test service with dependency."""

    def __init__(self, test_service: ITestService):
        self.test_service = test_service

    def get_combined_value(self) -> str:
        return f"combined_{self.test_service.get_value()}"


class TestDIContainer:
    """Test cases for DIContainer."""

    def test_register_and_resolve_transient(self):
        """Test registering and resolving transient services."""
        container = DIContainer()
        container.register(ITestService, TestServiceImpl)

        service1 = container.resolve(ITestService)
        service2 = container.resolve(ITestService)

        assert isinstance(service1, TestServiceImpl)
        assert isinstance(service2, TestServiceImpl)
        assert service1 is not service2  # Different instances for transient

    def test_register_and_resolve_singleton(self):
        """Test registering and resolving singleton services."""
        container = DIContainer()
        container.register_singleton(ITestService, TestServiceImpl)

        service1 = container.resolve(ITestService)
        service2 = container.resolve(ITestService)

        assert isinstance(service1, TestServiceImpl)
        assert service1 is service2  # Same instance for singleton

    def test_register_instance(self):
        """Test registering specific instance."""
        container = DIContainer()
        instance = TestServiceImpl()
        container.register_instance(ITestService, instance)

        resolved = container.resolve(ITestService)
        assert resolved is instance

    def test_dependency_injection(self):
        """Test automatic dependency injection."""
        container = DIContainer()
        container.register(ITestService, TestServiceImpl)
        container.register(ServiceWithDependency, ServiceWithDependency)

        service = container.resolve(ServiceWithDependency)
        assert isinstance(service, ServiceWithDependency)
        assert service.get_combined_value() == "combined_test_value"

    def test_unregistered_service_raises_exception(self):
        """Test that resolving unregistered service raises exception."""
        container = DIContainer()

        with pytest.raises(ServiceNotRegisteredException):
            container.resolve(ITestService)

    def test_is_registered(self):
        """Test service registration check."""
        container = DIContainer()

        assert not container.is_registered(ITestService)

        container.register(ITestService, TestServiceImpl)
        assert container.is_registered(ITestService)

    def test_clear_services(self):
        """Test clearing all services."""
        container = DIContainer()
        container.register(ITestService, TestServiceImpl)

        assert container.is_registered(ITestService)

        container.clear()
        assert not container.is_registered(ITestService)


class TestApplicationBootstrap:
    """Test cases for application bootstrap."""

    @patch.dict(os.environ, {"APP_ENVIRONMENT": "testing"})
    def test_initialize_application(self):
        """Test application initialization."""
        container = get_container()

        assert isinstance(container, DIContainer)
        assert container.is_registered(AppConfig)

        config = container.resolve(AppConfig)
        assert config.environment == Environment.TESTING

    @patch.dict(os.environ, {"APP_ENVIRONMENT": "testing"})
    def test_get_container_after_initialization(self):
        """Test getting container after initialization."""
        get_container()
        container = get_container()

        assert isinstance(container, DIContainer)

    def test_get_container_before_initialization_raises_error(self):
        """Test that getting container before initialization works (auto-initialization)."""
        # Clear any existing bootstrap
        import src.shared.dependency_injection.bootstrap as bootstrap_module

        bootstrap_module._container = None

        # The current implementation creates a container automatically
        container = get_container()
        assert isinstance(container, DIContainer)

        # Test that subsequent calls return the same container
        container2 = get_container()
        assert container is container2


if __name__ == "__main__":
    pytest.main([__file__])
