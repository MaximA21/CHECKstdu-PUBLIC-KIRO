"""Logger factory with dependency injection support."""

from typing import Any, Dict, Optional, Type

from ...application.interfaces.logging import ILogger, ILoggerFactory, IStructuredLogger, LogLevel
from .cloudwatch_logger import CloudWatchLoggerFactory
from .console_logger import ConsoleLoggerFactory
from .log_configuration import LogConfiguration
from .structured_logger import StructuredLogger


class LoggerFactory(ILoggerFactory):
    """Main logger factory with environment-aware provider selection."""

    def __init__(self, provider: str = "auto", config: Optional[Dict[str, Any]] = None):
        """
        Initialize logger factory.

        Args:
            provider: Logger provider ("console", "cloudwatch", "auto")
            config: Optional configuration dictionary
        """
        self._provider = provider
        self._config = config or {}
        self._log_configuration = LogConfiguration()
        self._factories: Dict[str, ILoggerFactory] = {}
        self._loggers: Dict[str, ILogger] = {}

        self._initialize_factories()

    def _initialize_factories(self) -> None:
        """Initialize provider-specific factories."""
        # Console factory (always available)
        self._factories["console"] = ConsoleLoggerFactory()

        # CloudWatch factory (if in AWS environment)
        if self._is_aws_environment() or self._provider == "cloudwatch":
            default_log_group = self._config.get("cloudwatch_log_group")
            self._factories["cloudwatch"] = CloudWatchLoggerFactory(default_log_group)

    def _is_aws_environment(self) -> bool:
        """Check if running in AWS environment."""
        import os

        return (
            os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None
            or os.environ.get("AWS_EXECUTION_ENV") is not None
            or os.environ.get("AWS_REGION") is not None
        )

    def _get_effective_provider(self) -> str:
        """Get the effective provider based on configuration and environment."""
        if self._provider == "auto":
            if self._is_aws_environment():
                return "cloudwatch"
            else:
                return "console"
        return self._provider

    def create_logger(self, name: str, level: Optional[LogLevel] = None) -> ILogger:
        """Create a logger instance using the appropriate provider."""
        cache_key = f"{name}_{level.value if level else 'default'}"

        if cache_key not in self._loggers:
            provider = self._get_effective_provider()
            factory = self._factories.get(provider, self._factories["console"])

            # Use configuration-specific level if not provided
            effective_level = level or self._log_configuration.get_effective_log_level_for_logger(name)

            logger = factory.create_logger(name, effective_level)
            self._loggers[cache_key] = logger

        return self._loggers[cache_key]

    def create_structured_logger(self, name: str, level: Optional[LogLevel] = None) -> IStructuredLogger:
        """Create a structured logger instance."""
        cache_key = f"structured_{name}_{level.value if level else 'default'}"

        if cache_key not in self._loggers:
            provider = self._get_effective_provider()
            factory = self._factories.get(provider, self._factories["console"])

            effective_level = level or self._log_configuration.get_effective_log_level_for_logger(name)

            # Try to create structured logger from provider factory
            if hasattr(factory, "create_structured_logger"):
                logger = factory.create_structured_logger(name, effective_level)
            else:
                # Fallback to our structured logger implementation
                logger = StructuredLogger(name, effective_level)

            self._loggers[cache_key] = logger

        return self._loggers[cache_key]

    def create_lambda_logger(self, function_name: str) -> ILogger:
        """Create a logger specifically configured for Lambda functions."""
        cache_key = f"lambda_{function_name}"

        if cache_key not in self._loggers:
            provider = self._get_effective_provider()
            factory = self._factories.get(provider, self._factories["console"])

            logger = factory.create_lambda_logger(function_name)
            self._loggers[cache_key] = logger

        return self._loggers[cache_key]

    def get_logger(self, name: str) -> Optional[ILogger]:
        """Get an existing logger by name."""
        # Try to find logger with any level
        for cache_key, logger in self._loggers.items():
            if cache_key.startswith(name + "_") or cache_key == name:
                return logger
        return None

    def create_logger_for_class(self, cls: Type) -> ILogger:
        """
        Create a logger for a specific class.

        Args:
            cls: Class to create logger for

        Returns:
            ILogger: Logger instance
        """
        logger_name = f"{cls.__module__}.{cls.__name__}"
        return self.create_logger(logger_name)

    def create_logger_for_module(self, module_name: str) -> ILogger:
        """
        Create a logger for a specific module.

        Args:
            module_name: Module name

        Returns:
            ILogger: Logger instance
        """
        return self.create_logger(module_name)

    def set_provider(self, provider: str) -> None:
        """
        Set the logger provider.

        Args:
            provider: Provider name ("console", "cloudwatch", "auto")
        """
        if provider != self._provider:
            self._provider = provider
            # Clear cached loggers to force recreation with new provider
            self._loggers.clear()
            self._initialize_factories()

    def get_provider(self) -> str:
        """Get the current provider."""
        return self._provider

    def get_effective_provider(self) -> str:
        """Get the effective provider (resolved from "auto")."""
        return self._get_effective_provider()

    def configure_provider(self, provider: str, config: Dict[str, Any]) -> None:
        """
        Configure a specific provider.

        Args:
            provider: Provider name
            config: Provider configuration
        """
        self._config[provider] = config

        # Reinitialize factories if needed
        if provider in self._factories:
            self._initialize_factories()

    def get_configuration(self) -> Dict[str, Any]:
        """Get the current factory configuration."""
        return {
            "provider": self._provider,
            "effective_provider": self._get_effective_provider(),
            "is_aws_environment": self._is_aws_environment(),
            "available_providers": list(self._factories.keys()),
            "config": self._config,
            "cached_loggers": list(self._loggers.keys()),
        }

    def clear_cache(self) -> None:
        """Clear all cached loggers."""
        self._loggers.clear()

    def shutdown(self) -> None:
        """Shutdown the factory and clean up resources."""
        # Clear all loggers
        self._loggers.clear()

        # Clear factories
        self._factories.clear()


# Convenience function for quick logger creation
def create_logger(name: str, provider: str = "auto", level: Optional[LogLevel] = None) -> ILogger:
    """
    Quick function to create a logger.

    Args:
        name: Logger name
        provider: Logger provider
        level: Optional log level

    Returns:
        ILogger: Logger instance
    """
    factory = LoggerFactory(provider)
    return factory.create_logger(name, level)


def create_lambda_logger(function_name: str, provider: str = "auto") -> ILogger:
    """
    Quick function to create a Lambda logger.

    Args:
        function_name: Lambda function name
        provider: Logger provider

    Returns:
        ILogger: Lambda logger instance
    """
    factory = LoggerFactory(provider)
    return factory.create_lambda_logger(function_name)
