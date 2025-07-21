"""Bootstrap module for dependency injection container setup."""

import os
from typing import Optional

from .container import DIContainer
from .factory import ServiceFactory
from ...infrastructure.config.loader import ConfigLoader, ConfigurationError
from ...infrastructure.config.validator import ConfigValidator
from ...infrastructure.config.service_selector import ServiceSelector


_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get or create the global DI container instance."""
    global _container
    
    if _container is None:
        _container = _create_container()
    
    return _container


def _create_container() -> DIContainer:
    """Create and configure the DI container."""
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.load_config()
        
        # Validate configuration and log warnings
        validation_results = ConfigValidator.get_all_validation_results(config)
        _log_validation_results(validation_results)
        
        # Create service selector
        service_selector = ServiceSelector(config)
        
        # Create service factory and container
        from .factory import ServiceFactoryProvider
        factory = ServiceFactoryProvider.get_factory(config)
        container = factory.create_container(config, service_selector)
        
        # Register use cases
        _register_use_cases(container)
        
        # Register controllers
        _register_controllers(container)
        
        # Log environment summary
        _log_environment_summary(service_selector)
        
        return container
        
    except ConfigurationError as e:
        # Log configuration error and re-raise
        print(f"Configuration error during bootstrap: {e}")
        if hasattr(e, 'errors'):
            for error in e.errors:
                print(f"  - {error}")
        raise


def _register_use_cases(container: DIContainer) -> None:
    """Register application use cases."""
    from ...application.use_cases.search_offers_use_case import SearchOffersUseCase
    from ...application.use_cases.share_results_use_case import ShareResultsUseCase
    from ...application.use_cases.process_results_use_case import ProcessResultsUseCase
    from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
    from ...application.use_cases.requestor_use_case import RequestorUseCase
    from ...application.use_cases.address_normalization_use_case import AddressNormalizationUseCase
    from ...application.use_cases.authorization_use_case import AuthorizationUseCase
    
    # Register use cases as transient (new instance each time)
    container.register_transient(SearchOffersUseCase, SearchOffersUseCase)
    container.register_transient(ShareResultsUseCase, ShareResultsUseCase)
    container.register_transient(ProcessResultsUseCase, ProcessResultsUseCase)
    container.register_transient(ConnectionManagementUseCase, ConnectionManagementUseCase)
    container.register_transient(RequestorUseCase, RequestorUseCase)
    container.register_transient(AddressNormalizationUseCase, AddressNormalizationUseCase)
    container.register_transient(AuthorizationUseCase, AuthorizationUseCase)


def reset_container() -> None:
    """Reset the global container (useful for testing)."""
    global _container
    _container = None


def _register_controllers(container: DIContainer) -> None:
    """Register presentation controllers."""
    from ...presentation.http_controllers.search_controller import SearchController
    from ...presentation.http_controllers.share_controller import ShareController
    from ...presentation.websocket_handlers.websocket_server import WebSocketServerController
    from ...application.interfaces.logging import ILogger
    
    # Register a default logger instance
    default_logger = container.get_logger("default")
    container.register_instance(ILogger, default_logger)
    
    # Register controllers as transient (new instance each time)
    container.register_transient(SearchController, SearchController)
    container.register_transient(ShareController, ShareController)
    container.register_transient(WebSocketServerController, WebSocketServerController)


def create_test_container() -> DIContainer:
    """Create a container configured for testing."""
    # Set test environment
    os.environ['APP_ENVIRONMENT'] = 'testing'
    
    # Reset container to force recreation with test config
    reset_container()
    
    # Create container
    container = _create_container()
    
    return container


def _log_validation_results(validation_results: dict) -> None:
    """Log configuration validation results."""
    for category, issues in validation_results.items():
        if issues:
            print(f"Configuration {category}:")
            for issue in issues:
                print(f"  - {issue}")


def _log_environment_summary(service_selector: ServiceSelector) -> None:
    """Log environment configuration summary."""
    summary = service_selector.get_environment_summary()
    print("Environment Configuration:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


def get_config():
    """Get the current configuration."""
    config_loader = ConfigLoader()
    return config_loader.load_config()