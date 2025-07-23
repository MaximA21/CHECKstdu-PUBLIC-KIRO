"""Service factory for creating environment-specific service implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Type, TypeVar

from ...application.interfaces.connections import IConnectionManager
from ...application.interfaces.logging import ILogger, ILoggerFactory
from ...application.interfaces.messaging import IMessageQueue, IWorkflowOrchestrator
from ...application.interfaces.providers import IProviderService
from ...application.interfaces.repositories import IConnectionRepository, ISearchResultRepository
from ...infrastructure.config.models import AppConfig, DatabaseProvider, LoggingProvider, MessagingProvider
from .container import DIContainer, ServiceLifetime

# Legacy IStorageService removed - using repository pattern instead


T = TypeVar("T")


class ServiceFactory(ABC):
    """Abstract base class for service factories."""

    @abstractmethod
    def create_container(self, config: AppConfig, service_selector=None) -> DIContainer:
        """Create and configure a DI container for the specific environment."""
        pass


class AWSServiceFactory(ServiceFactory):
    """Service factory for AWS-based implementations."""

    def create_container(self, config: AppConfig, service_selector=None) -> DIContainer:
        """Create DI container with AWS service implementations."""
        container = DIContainer()

        # Register configuration
        container.register_instance(AppConfig, config)

        # Use service selector if provided, otherwise fall back to config-based selection
        if service_selector:
            self._register_services_with_selector(container, config, service_selector)
        else:
            self._register_services_legacy(container, config)

        return container

    def _register_services_with_selector(self, container: DIContainer, config: AppConfig, service_selector) -> None:
        """Register services using the service selector."""
        # Register repositories
        container.register_instance(ISearchResultRepository, service_selector.get_search_result_repository())
        container.register_instance(IConnectionRepository, service_selector.get_connection_repository())

        # Register messaging services
        container.register_instance(IMessageQueue, service_selector.get_message_queue())
        container.register_instance(IWorkflowOrchestrator, service_selector.get_workflow_orchestrator())
        container.register_instance(IConnectionManager, service_selector.get_connection_manager())

        # Register logging services
        container.register_instance(ILoggerFactory, service_selector.get_logger_factory())

        # Register provider services
        self._register_provider_services(container, config)

        # Register legacy storage service for backward compatibility
        self._register_legacy_storage_service(container, config)

    def _register_services_legacy(self, container: DIContainer, config: AppConfig) -> None:
        """Register services using legacy config-based selection."""
        # Register repositories based on database provider
        if config.database.provider == DatabaseProvider.AWS_DYNAMODB:
            self._register_aws_repositories(container, config)
        else:
            self._register_mock_repositories(container, config)

        # Register messaging services
        if config.messaging.provider == MessagingProvider.AWS_SQS:
            self._register_aws_messaging(container, config)
        else:
            self._register_mock_messaging(container, config)

        # Register logging services
        if config.logging.provider == LoggingProvider.AWS_CLOUDWATCH:
            self._register_aws_logging(container, config)
        else:
            self._register_console_logging(container, config)

        # Register provider services
        self._register_provider_services(container, config)

        # Register legacy storage service for backward compatibility
        self._register_legacy_storage_service(container, config)

    def _register_aws_repositories(self, container: DIContainer, config: AppConfig) -> None:
        """Register AWS DynamoDB repository implementations."""
        from ...infrastructure.persistence.aws_dynamodb_repository import (
            AWSDynamoDBConnectionRepository,
            AWSDynamoDBSearchResultRepository,
        )

        container.register_singleton(ISearchResultRepository, AWSDynamoDBSearchResultRepository)
        container.register_singleton(IConnectionRepository, AWSDynamoDBConnectionRepository)

    def _register_mock_repositories(self, container: DIContainer, config: AppConfig) -> None:
        """Register mock repository implementations."""
        from ...infrastructure.persistence.mock_repositories import MockConnectionRepository, MockSearchResultRepository

        container.register_singleton(ISearchResultRepository, MockSearchResultRepository)
        container.register_singleton(IConnectionRepository, MockConnectionRepository)

    def _register_aws_messaging(self, container: DIContainer, config: AppConfig) -> None:
        """Register AWS SQS messaging implementations."""
        from ...infrastructure.messaging.aws_sqs_adapter import AWSSQSMessageQueue
        from ...infrastructure.messaging.aws_step_functions_adapter import AWSStepFunctionsOrchestrator

        container.register_singleton(IMessageQueue, AWSSQSMessageQueue)
        container.register_singleton(IWorkflowOrchestrator, AWSStepFunctionsOrchestrator)

    def _register_mock_messaging(self, container: DIContainer, config: AppConfig) -> None:
        """Register mock messaging implementations."""
        from ...infrastructure.messaging.mock_messaging import MockMessageQueue, MockWorkflowOrchestrator

        container.register_singleton(IMessageQueue, MockMessageQueue)
        container.register_singleton(IWorkflowOrchestrator, MockWorkflowOrchestrator)

    def _register_aws_logging(self, container: DIContainer, config: AppConfig) -> None:
        """Register AWS CloudWatch logging implementations."""
        from ...infrastructure.logging.logger_factory import LoggerFactory

        container.register_singleton(ILoggerFactory, LoggerFactory)

    def _register_console_logging(self, container: DIContainer, config: AppConfig) -> None:
        """Register console logging implementations."""
        from ...infrastructure.logging.logger_factory import LoggerFactory

        container.register_singleton(ILoggerFactory, LoggerFactory)

    def _register_provider_services(self, container: DIContainer, config: AppConfig) -> None:
        """Register external provider service implementations."""
        from ...infrastructure.external_services.provider_registry import ProviderRegistry
        from ...infrastructure.messaging.aws_websocket_adapter import AWSWebSocketConnectionManager

        container.register_singleton(ProviderRegistry, ProviderRegistry)
        container.register_singleton(IConnectionManager, AWSWebSocketConnectionManager)

    # Legacy storage service registration removed - using repository pattern instead


class MockServiceFactory(ServiceFactory):
    """Service factory for mock implementations (testing)."""

    def create_container(self, config: AppConfig, service_selector=None) -> DIContainer:
        """Create DI container with mock service implementations."""
        container = DIContainer()

        # Register configuration
        container.register_instance(AppConfig, config)

        # Use service selector if provided, otherwise use mock implementations
        if service_selector:
            self._register_services_with_selector(container, config, service_selector)
        else:
            # Register all mock implementations
            self._register_mock_repositories(container, config)
            self._register_mock_messaging(container, config)
            self._register_mock_logging(container, config)
            self._register_mock_providers(container, config)
            # Legacy storage registration removed - using repository pattern

        return container

    def _register_services_with_selector(self, container: DIContainer, config: AppConfig, service_selector) -> None:
        """Register services using the service selector."""
        # Register repositories
        container.register_instance(ISearchResultRepository, service_selector.get_search_result_repository())
        container.register_instance(IConnectionRepository, service_selector.get_connection_repository())

        # Register messaging services
        container.register_instance(IMessageQueue, service_selector.get_message_queue())
        container.register_instance(IWorkflowOrchestrator, service_selector.get_workflow_orchestrator())
        container.register_instance(IConnectionManager, service_selector.get_connection_manager())

        # Register logging services
        container.register_instance(ILoggerFactory, service_selector.get_logger_factory())

        # Register provider services
        self._register_mock_providers(container, config)

        # Legacy storage service registration removed - using repository pattern

    def _register_mock_repositories(self, container: DIContainer, config: AppConfig) -> None:
        """Register mock repository implementations."""
        from ...infrastructure.persistence.mock_repositories import MockConnectionRepository, MockSearchResultRepository

        container.register_singleton(ISearchResultRepository, MockSearchResultRepository)
        container.register_singleton(IConnectionRepository, MockConnectionRepository)

    def _register_mock_messaging(self, container: DIContainer, config: AppConfig) -> None:
        """Register mock messaging implementations."""
        from ...infrastructure.messaging.mock_connection_manager import MockConnectionManager
        from ...infrastructure.messaging.mock_messaging import MockMessageQueue, MockWorkflowOrchestrator

        container.register_singleton(IMessageQueue, MockMessageQueue)
        container.register_singleton(IWorkflowOrchestrator, MockWorkflowOrchestrator)
        container.register_singleton(IConnectionManager, MockConnectionManager)

    def _register_mock_logging(self, container: DIContainer, config: AppConfig) -> None:
        """Register mock logging implementations."""
        from ...infrastructure.logging.logger_factory import LoggerFactory

        container.register_singleton(ILoggerFactory, LoggerFactory)

    def _register_mock_providers(self, container: DIContainer, config: AppConfig) -> None:
        """Register mock provider implementations."""
        from ...infrastructure.external_services.mock_providers import MockProviderRegistry

        container.register_singleton(MockProviderRegistry, MockProviderRegistry)

    # Legacy mock storage service registration removed - using repository pattern instead


class ContainerServiceFactory(ServiceFactory):
    """Service factory for container-based deployments."""

    def create_container(self, config: AppConfig, service_selector=None) -> DIContainer:
        """Create DI container for container deployment."""
        # For container deployment, we can use the same AWS implementations
        # but with different configuration
        aws_factory = AWSServiceFactory()
        return aws_factory.create_container(config, service_selector)


class ServiceFactoryProvider:
    """Provides the appropriate service factory based on configuration."""

    @staticmethod
    def get_factory(config: AppConfig) -> ServiceFactory:
        """Get the appropriate service factory for the configuration.

        Args:
            config: Application configuration

        Returns:
            Service factory instance
        """
        if config.is_testing:
            return MockServiceFactory()
        elif config.database.provider == DatabaseProvider.MOCK:
            return MockServiceFactory()
        else:
            return AWSServiceFactory()

    @staticmethod
    def create_configured_container(config: AppConfig, service_selector=None) -> DIContainer:
        """Create a fully configured DI container.

        Args:
            config: Application configuration
            service_selector: Optional service selector for automatic service selection

        Returns:
            Configured DI container
        """
        factory = ServiceFactoryProvider.get_factory(config)
        return factory.create_container(config, service_selector)
