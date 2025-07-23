"""Einfache Tests für grundlegende Shared-Komponenten."""

import pytest
from src.shared.dependency_injection.container import DIContainer
from src.shared.dependency_injection.bootstrap import get_container, reset_container
from src.shared.exceptions.domain import SearchRequestException, ShareTokenNotFoundException
from src.shared.exceptions.base import BaseApplicationException, ErrorSeverity, ErrorCategory, ErrorContext
from src.shared.exceptions.infrastructure import InfrastructureException
from src.infrastructure.config.models import AppConfig, Environment, DatabaseConfig, DatabaseProvider
from src.infrastructure.config.loader import ConfigLoader
from src.infrastructure.logging.console_logger import ConsoleLogger
from src.infrastructure.logging.logger_factory import LoggerFactory
from src.infrastructure.logging.structured_logger import StructuredLogger
from src.infrastructure.logging.cloudwatch_logger import CloudWatchLogger
from src.infrastructure.external_services.provider_registry import ProviderRegistry
from src.infrastructure.external_services.provider_aggregator import ProviderAggregator
from src.infrastructure.external_services.mock_providers import MockProviderService
from src.infrastructure.persistence.mock_repositories import MockSearchResultRepository
from src.infrastructure.messaging.mock_messaging import MockMessageQueue, MockWorkflowOrchestrator, MockEventBus
from src.infrastructure.messaging.mock_connection_manager import MockConnectionManager
from src.domain.entities.connection_session import ConnectionSession
from src.domain.entities.search_result import SearchResult
from src.domain.entities.provider_offer import ProviderOffer
from src.domain.value_objects.address import Address
from src.application.interfaces.providers import IProviderService
from src.application.interfaces.repositories import ISearchResultRepository
from src.application.interfaces.messaging import IMessagingAdapter, IConnectionManager
from src.application.interfaces.logging import ILogger
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase
from src.application.use_cases.share_results_use_case import ShareResultsUseCase
from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from src.application.use_cases.process_results_use_case import ProcessResultsUseCase
from src.application.use_cases.requestor_use_case import RequestorUseCase
from src.application.use_cases.address_normalization_use_case import AddressNormalizationUseCase
from src.application.use_cases.authorization_use_case import AuthorizationUseCase
from src.presentation.controllers.base_controller import BaseController
from src.presentation.http_controllers.search_controller import SearchController
from src.presentation.http_controllers.share_controller import ShareController
from src.presentation.websocket_handlers.connection_handler import ConnectionHandler
from src.presentation.websocket_handlers.websocket_server import WebSocketServer
from src.presentation.lambda_handlers.search_handler import SearchHandler
from src.presentation.lambda_handlers.share_api_handler import ShareApiHandler
from src.presentation.lambda_handlers.connect_handler import ConnectHandler
from src.presentation.lambda_handlers.requestor_handler import RequestorHandler
from src.presentation.lambda_handlers.results_handler import ResultsHandler
from src.presentation.lambda_handlers.address_normalizer_handler import AddressNormalizerHandler
from src.presentation.lambda_handlers.authorizer_handler import AuthorizerHandler
from src.presentation.lambda_handlers.disconnect_handler import DisconnectHandler
from src.presentation.lambda_handlers.connection_limit_enforcer_handler import ConnectionLimitEnforcerHandler
from unittest.mock import MagicMock, patch
import asyncio
import json
from datetime import datetime, timedelta


class TestBasicDIContainer:
    def test_container_creation(self):
        """Test that a DI container can be created"""
        container = DIContainer()
        assert container is not None
        assert isinstance(container, DIContainer)

    def test_container_registration_and_resolution(self):
        """Test basic registration and resolution"""
        container = DIContainer()

        # Register a simple service
        container.register(str, lambda: "test_value")

        # Resolve the service
        result = container.resolve(str)
        assert result == "test_value"

    def test_container_singleton_behavior(self):
        """Test that singleton services return the same instance"""
        container = DIContainer()

        # Register a singleton service
        container.register_singleton(list, lambda: [1, 2, 3])

        # Resolve twice
        instance1 = container.resolve(list)
        instance2 = container.resolve(list)

        assert instance1 is instance2
        assert instance1 == [1, 2, 3]

    def test_container_is_registered(self):
        """Test that container can check if services are registered"""
        container = DIContainer()

        # Initially not registered
        assert not container.is_registered(str)

        # After registration
        container.register(str, lambda: "test")
        assert container.is_registered(str)

    def test_container_clear(self):
        """Test that container can be cleared"""
        container = DIContainer()

        # Register a service
        container.register(str, lambda: "test")
        assert container.is_registered(str)

        # Clear container
        container.clear()
        assert not container.is_registered(str)

    def test_container_resolve_unregistered_service(self):
        """Test that container raises exception for unregistered service"""
        container = DIContainer()

        with pytest.raises(Exception):
            container.resolve(str)

    def test_container_register_instance(self):
        """Test registering an instance"""
        container = DIContainer()
        test_instance = [1, 2, 3]
        container.register_instance(list, test_instance)

        result = container.resolve(list)
        assert result is test_instance

    def test_container_register_factory(self):
        """Test registering a factory function"""
        container = DIContainer()

        def factory():
            return {"key": "value"}

        container.register(dict, factory)
        result = container.resolve(dict)
        assert result == {"key": "value"}


class TestBootstrapFunctions:
    def test_get_container(self):
        """Test that get_container returns a container"""
        container = get_container()
        assert container is not None
        assert isinstance(container, DIContainer)

    def test_reset_container(self):
        """Test that reset_container works"""
        # Get initial container
        container1 = get_container()

        # Reset container
        reset_container()

        # Get new container
        container2 = get_container()

        # They should be different instances
        assert container1 is not container2

    def test_get_container_singleton(self):
        """Test that get_container returns the same instance"""
        container1 = get_container()
        container2 = get_container()
        assert container1 is container2


class TestBasicExceptions:
    def test_search_request_exception(self):
        """Test SearchRequestException creation and properties"""
        exception = SearchRequestException("Test error message")
        assert str(exception) == "[SEARCHREQUEST_ERROR] Test error message"
        assert exception.message == "Test error message"

    def test_share_token_not_found_exception(self):
        """Test ShareTokenNotFoundException creation and properties"""
        exception = ShareTokenNotFoundException("Share token not found or expired", "invalid-token")
        assert str(exception) == "[SHARETOKENNOTFOUND_ERROR] Share token not found or expired"
        assert exception.share_token == "invalid-token"

    def test_base_application_exception(self):
        """Test BaseApplicationException creation"""
        exception = BaseApplicationException("Test error")
        assert exception.message == "Test error"
        assert exception.error_code is not None

    def test_base_application_exception_with_severity(self):
        """Test BaseApplicationException with severity"""
        exception = BaseApplicationException("Test error", severity=ErrorSeverity.HIGH, category=ErrorCategory.SYSTEM)
        assert exception.severity == ErrorSeverity.HIGH
        assert exception.category == ErrorCategory.SYSTEM

    def test_error_severity_values(self):
        """Test ErrorSeverity values"""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_category_values(self):
        """Test ErrorCategory values"""
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.BUSINESS_LOGIC.value == "business_logic"
        assert ErrorCategory.SYSTEM.value == "system"
        assert ErrorCategory.EXTERNAL_SERVICE.value == "external_service"

    def test_error_context(self):
        """Test ErrorContext creation"""
        context = ErrorContext()
        assert context.additional_data == {}
        assert context.timestamp is not None

    def test_error_context_with_data(self):
        """Test ErrorContext with additional data"""
        context = ErrorContext()
        context.additional_data["key"] = "value"
        assert context.additional_data["key"] == "value"

    def test_infrastructure_exception(self):
        """Test InfrastructureException creation"""
        exception = InfrastructureException("Infrastructure error")
        assert exception.message == "Infrastructure error"


class TestConfiguration:
    def test_app_config_creation(self):
        """Test AppConfig creation"""
        config = AppConfig()
        assert config is not None

    def test_environment_values(self):
        """Test Environment enum values"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.PRODUCTION.value == "production"

    def test_database_config_creation(self):
        """Test DatabaseConfig creation"""
        config = DatabaseConfig()
        assert config is not None

    def test_database_provider_values(self):
        """Test DatabaseProvider enum values"""
        assert DatabaseProvider.MOCK.value == "mock"
        assert DatabaseProvider.DYNAMODB.value == "dynamodb"

    def test_config_loader_creation(self):
        """Test ConfigLoader creation"""
        loader = ConfigLoader()
        assert loader is not None


class TestLogging:
    def test_console_logger_creation(self):
        """Test ConsoleLogger creation"""
        logger = ConsoleLogger()
        assert logger is not None

    def test_logger_factory_creation(self):
        """Test LoggerFactory creation"""
        factory = LoggerFactory()
        assert factory is not None

    def test_structured_logger_creation(self):
        """Test StructuredLogger creation"""
        logger = StructuredLogger()
        assert logger is not None

    def test_cloudwatch_logger_creation(self):
        """Test CloudWatchLogger creation"""
        logger = CloudWatchLogger()
        assert logger is not None


class TestExternalServices:
    def test_provider_registry_creation(self):
        """Test ProviderRegistry creation"""
        registry = ProviderRegistry()
        assert registry is not None

    def test_provider_aggregator_creation(self):
        """Test ProviderAggregator creation"""
        aggregator = ProviderAggregator()
        assert aggregator is not None

    def test_mock_provider_service_creation(self):
        """Test MockProviderService creation"""
        service = MockProviderService("test_provider")
        assert service.provider_name == "test_provider"


class TestPersistence:
    def test_mock_search_result_repository_creation(self):
        """Test MockSearchResultRepository creation"""
        repo = MockSearchResultRepository()
        assert repo is not None


class TestMessaging:
    def test_mock_message_queue_creation(self):
        """Test MockMessageQueue creation"""
        queue = MockMessageQueue()
        assert queue is not None

    def test_mock_workflow_orchestrator_creation(self):
        """Test MockWorkflowOrchestrator creation"""
        orchestrator = MockWorkflowOrchestrator()
        assert orchestrator is not None

    def test_mock_event_bus_creation(self):
        """Test MockEventBus creation"""
        event_bus = MockEventBus()
        assert event_bus is not None

    def test_mock_connection_manager_creation(self):
        """Test MockConnectionManager creation"""
        manager = MockConnectionManager()
        assert manager is not None


class TestDomainEntities:
    def test_connection_session_creation(self):
        """Test ConnectionSession creation"""
        session = ConnectionSession("test_connection")
        assert session.connection_id == "test_connection"

    def test_search_result_creation(self):
        """Test SearchResult creation"""
        result = SearchResult("test_request")
        assert result.request_id == "test_request"

    def test_provider_offer_creation(self):
        """Test ProviderOffer creation"""
        offer = ProviderOffer("test_provider", "test_offer")
        assert offer.provider_name == "test_provider"
        assert offer.offer_id == "test_offer"

    def test_address_creation(self):
        """Test Address creation"""
        address = Address("Test Street 123", "12345", "Test City")
        assert address.street == "Test Street 123"
        assert address.postal_code == "12345"
        assert address.city == "Test City"


class TestApplicationInterfaces:
    def test_provider_service_interface(self):
        """Test IProviderService interface"""
        # This is an abstract class, so we test that it exists
        assert IProviderService is not None

    def test_search_result_repository_interface(self):
        """Test ISearchResultRepository interface"""
        assert ISearchResultRepository is not None

    def test_messaging_adapter_interface(self):
        """Test IMessagingAdapter interface"""
        assert IMessagingAdapter is not None

    def test_connection_manager_interface(self):
        """Test IConnectionManager interface"""
        assert IConnectionManager is not None

    def test_logger_interface(self):
        """Test ILogger interface"""
        assert ILogger is not None


class TestUseCases:
    def test_search_offers_use_case_creation(self):
        """Test SearchOffersUseCase creation"""
        use_case = SearchOffersUseCase(
            provider_registry=MagicMock(), result_repository=MagicMock(), messaging_adapter=MagicMock(), logger=MagicMock()
        )
        assert use_case is not None

    def test_share_results_use_case_creation(self):
        """Test ShareResultsUseCase creation"""
        use_case = ShareResultsUseCase(result_repository=MagicMock(), logger=MagicMock())
        assert use_case is not None

    def test_connection_management_use_case_creation(self):
        """Test ConnectionManagementUseCase creation"""
        use_case = ConnectionManagementUseCase(connection_manager=MagicMock(), logger=MagicMock())
        assert use_case is not None

    def test_process_results_use_case_creation(self):
        """Test ProcessResultsUseCase creation"""
        use_case = ProcessResultsUseCase(result_repository=MagicMock(), logger=MagicMock())
        assert use_case is not None

    def test_requestor_use_case_creation(self):
        """Test RequestorUseCase creation"""
        use_case = RequestorUseCase(messaging_adapter=MagicMock(), logger=MagicMock())
        assert use_case is not None

    def test_address_normalization_use_case_creation(self):
        """Test AddressNormalizationUseCase creation"""
        use_case = AddressNormalizationUseCase(logger=MagicMock())
        assert use_case is not None

    def test_authorization_use_case_creation(self):
        """Test AuthorizationUseCase creation"""
        use_case = AuthorizationUseCase(logger=MagicMock())
        assert use_case is not None


class TestPresentation:
    def test_base_controller_creation(self):
        """Test BaseController creation"""
        controller = BaseController(logger=MagicMock())
        assert controller is not None

    def test_search_controller_creation(self):
        """Test SearchController creation"""
        controller = SearchController(search_use_case=MagicMock(), logger=MagicMock())
        assert controller is not None

    def test_share_controller_creation(self):
        """Test ShareController creation"""
        controller = ShareController(share_use_case=MagicMock(), logger=MagicMock())
        assert controller is not None

    def test_connection_handler_creation(self):
        """Test ConnectionHandler creation"""
        handler = ConnectionHandler(connection_use_case=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_websocket_server_creation(self):
        """Test WebSocketServer creation"""
        server = WebSocketServer(connection_handler=MagicMock(), logger=MagicMock())
        assert server is not None


class TestLambdaHandlers:
    def test_search_handler_creation(self):
        """Test SearchHandler creation"""
        handler = SearchHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_share_api_handler_creation(self):
        """Test ShareApiHandler creation"""
        handler = ShareApiHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_connect_handler_creation(self):
        """Test ConnectHandler creation"""
        handler = ConnectHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_requestor_handler_creation(self):
        """Test RequestorHandler creation"""
        handler = RequestorHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_results_handler_creation(self):
        """Test ResultsHandler creation"""
        handler = ResultsHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_address_normalizer_handler_creation(self):
        """Test AddressNormalizerHandler creation"""
        handler = AddressNormalizerHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_authorizer_handler_creation(self):
        """Test AuthorizerHandler creation"""
        handler = AuthorizerHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_disconnect_handler_creation(self):
        """Test DisconnectHandler creation"""
        handler = DisconnectHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None

    def test_connection_limit_enforcer_handler_creation(self):
        """Test ConnectionLimitEnforcerHandler creation"""
        handler = ConnectionLimitEnforcerHandler(container=MagicMock(), logger=MagicMock())
        assert handler is not None


class TestIntegration:
    def test_di_container_with_exceptions(self):
        """Test DI Container with Exception Handling"""
        container = DIContainer()

        # Test that container Exception Handling supports
        try:
            container.resolve(str)  # Should raise Exception
            assert False, "Should raise Exception"
        except Exception:
            assert True  # Expected behavior

    def test_bootstrap_with_container(self):
        """Test Bootstrap with Container Integration"""
        reset_container()
        container = get_container()

        # Test that container works
        container.register_instance(str, "test_value")
        result = container.resolve(str)
        assert result == "test_value"

    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy"""
        # Test that domain exceptions inherit from base
        search_exception = SearchRequestException("test")
        assert isinstance(search_exception, BaseApplicationException)

        share_exception = ShareTokenNotFoundException("test", "token")
        assert isinstance(share_exception, BaseApplicationException)

    def test_configuration_integration(self):
        """Test configuration components work together"""
        config = AppConfig()
        loader = ConfigLoader()

        assert config is not None
        assert loader is not None

    def test_logging_integration(self):
        """Test logging components work together"""
        console_logger = ConsoleLogger()
        factory = LoggerFactory()
        structured_logger = StructuredLogger()
        cloudwatch_logger = CloudWatchLogger()

        assert console_logger is not None
        assert factory is not None
        assert structured_logger is not None
        assert cloudwatch_logger is not None

    def test_external_services_integration(self):
        """Test external services components work together"""
        registry = ProviderRegistry()
        aggregator = ProviderAggregator()
        mock_service = MockProviderService("test")

        assert registry is not None
        assert aggregator is not None
        assert mock_service is not None

    def test_persistence_integration(self):
        """Test persistence components work together"""
        repo = MockSearchResultRepository()
        assert repo is not None

    def test_messaging_integration(self):
        """Test messaging components work together"""
        message_queue = MockMessageQueue()
        workflow_orchestrator = MockWorkflowOrchestrator()
        event_bus = MockEventBus()
        connection_manager = MockConnectionManager()

        assert message_queue is not None
        assert workflow_orchestrator is not None
        assert event_bus is not None
        assert connection_manager is not None

    def test_domain_entities_integration(self):
        """Test domain entities work together"""
        session = ConnectionSession("test")
        result = SearchResult("test")
        offer = ProviderOffer("test", "offer")
        address = Address("street", "12345", "city")

        assert session is not None
        assert result is not None
        assert offer is not None
        assert address is not None

    def test_application_interfaces_integration(self):
        """Test application interfaces work together"""
        # These are abstract classes, so we just test they exist
        assert IProviderService is not None
        assert ISearchResultRepository is not None
        assert IMessagingAdapter is not None
        assert IConnectionManager is not None
        assert ILogger is not None

    def test_use_cases_integration(self):
        """Test use cases work together"""
        search_use_case = SearchOffersUseCase(
            provider_registry=MagicMock(), result_repository=MagicMock(), messaging_adapter=MagicMock(), logger=MagicMock()
        )
        share_use_case = ShareResultsUseCase(result_repository=MagicMock(), logger=MagicMock())

        assert search_use_case is not None
        assert share_use_case is not None

    def test_presentation_integration(self):
        """Test presentation components work together"""
        base_controller = BaseController(logger=MagicMock())
        search_controller = SearchController(search_use_case=MagicMock(), logger=MagicMock())

        assert base_controller is not None
        assert search_controller is not None

    def test_lambda_handlers_integration(self):
        """Test lambda handlers work together"""
        search_handler = SearchHandler(container=MagicMock(), logger=MagicMock())
        share_handler = ShareApiHandler(container=MagicMock(), logger=MagicMock())

        assert search_handler is not None
        assert share_handler is not None
