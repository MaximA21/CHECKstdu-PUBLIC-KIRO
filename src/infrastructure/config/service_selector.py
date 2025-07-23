"""Service selection based on configuration and environment."""

from typing import Any, Dict, Type

from src.application.interfaces.connections import IConnectionManager
from src.application.interfaces.logging import ILogger, ILoggerFactory
from src.application.interfaces.messaging import IMessageQueue, IWorkflowOrchestrator

# Import interfaces
from src.application.interfaces.repositories import IConnectionRepository, ISearchResultRepository
from src.infrastructure.logging.logger_factory import LoggerFactory
from src.infrastructure.messaging.mock_connection_manager import MockConnectionManager
from src.infrastructure.messaging.mock_messaging import MockMessageQueue, MockWorkflowOrchestrator

# Import mock implementations (always available)
from src.infrastructure.persistence.mock_repositories import MockConnectionRepository, MockSearchResultRepository

from .models import AppConfig, DatabaseProvider, LoggingProvider, MessagingProvider


class ServiceSelector:
    """Selects appropriate service implementations based on configuration."""

    def __init__(self, config: AppConfig):
        self.config = config

    def get_search_result_repository(self) -> ISearchResultRepository:
        """Get search result repository implementation."""
        if self.config.database.provider == DatabaseProvider.AWS_DYNAMODB:
            try:
                from src.infrastructure.persistence.aws_dynamodb_repository import DynamoDBSearchResultRepository

                return DynamoDBSearchResultRepository(
                    region=self.config.database.region,
                    table_prefix=self.config.database.table_prefix,
                    timeout_seconds=self.config.database.timeout_seconds,
                )
            except ImportError:
                # Fall back to mock if AWS dependencies not available
                return MockSearchResultRepository()
        elif self.config.database.provider == DatabaseProvider.MOCK:
            return MockSearchResultRepository()
        else:
            raise ValueError(f"Unsupported database provider: {self.config.database.provider}")

    def get_connection_repository(self) -> IConnectionRepository:
        """Get connection repository implementation."""
        if self.config.database.provider == DatabaseProvider.AWS_DYNAMODB:
            try:
                from src.infrastructure.persistence.aws_dynamodb_repository import DynamoDBConnectionRepository

                return DynamoDBConnectionRepository(
                    region=self.config.database.region,
                    table_prefix=self.config.database.table_prefix,
                    timeout_seconds=self.config.database.timeout_seconds,
                )
            except ImportError:
                # Fall back to mock if AWS dependencies not available
                return MockConnectionRepository()
        elif self.config.database.provider == DatabaseProvider.MOCK:
            return MockConnectionRepository()
        else:
            raise ValueError(f"Unsupported database provider: {self.config.database.provider}")

    def get_message_queue(self) -> IMessageQueue:
        """Get message queue implementation."""
        if self.config.messaging.provider == MessagingProvider.AWS_SQS:
            try:
                from src.infrastructure.messaging.aws_sqs_adapter import AWSSQSAdapter

                return AWSSQSAdapter(
                    region=self.config.messaging.region,
                    queue_prefix=self.config.messaging.queue_prefix,
                    timeout_seconds=self.config.messaging.timeout_seconds,
                )
            except ImportError:
                # Fall back to mock if AWS dependencies not available
                return MockMessageQueue()
        elif self.config.messaging.provider == MessagingProvider.MOCK:
            return MockMessageQueue()
        else:
            raise ValueError(f"Unsupported messaging provider: {self.config.messaging.provider}")

    def get_workflow_orchestrator(self) -> IWorkflowOrchestrator:
        """Get workflow orchestrator implementation."""
        if self.config.messaging.provider == MessagingProvider.AWS_SQS:
            try:
                from src.infrastructure.messaging.aws_step_functions_adapter import AWSStepFunctionsAdapter

                return AWSStepFunctionsAdapter(
                    region=self.config.messaging.region, timeout_seconds=self.config.messaging.timeout_seconds
                )
            except ImportError:
                # Fall back to mock if AWS dependencies not available
                return MockWorkflowOrchestrator()
        elif self.config.messaging.provider == MessagingProvider.MOCK:
            return MockWorkflowOrchestrator()
        else:
            raise ValueError(f"Unsupported messaging provider: {self.config.messaging.provider}")

    def get_connection_manager(self) -> IConnectionManager:
        """Get connection manager implementation."""
        if self.config.messaging.provider == MessagingProvider.AWS_SQS:
            try:
                from src.infrastructure.messaging.aws_websocket_adapter import AWSWebSocketAdapter

                return AWSWebSocketAdapter(
                    region=self.config.messaging.region, timeout_seconds=self.config.messaging.timeout_seconds
                )
            except ImportError:
                # Fall back to mock if AWS dependencies not available
                return MockConnectionManager()
        elif self.config.messaging.provider == MessagingProvider.MOCK:
            return MockConnectionManager()
        else:
            raise ValueError(f"Unsupported messaging provider: {self.config.messaging.provider}")

    def get_logger_factory(self) -> ILoggerFactory:
        """Get logger factory implementation."""
        provider_name = self.config.logging.provider.value
        config = {
            "level": self.config.logging.level,
            "structured": self.config.logging.structured,
            "cloudwatch_log_group": self.config.logging.log_group,
            "region": self.config.logging.region,
        }
        return LoggerFactory(provider=provider_name, config=config)

    def get_provider_configs(self) -> Dict[str, Any]:
        """Get provider configurations."""
        return {
            name: {
                "enabled": config.enabled,
                "timeout_seconds": config.timeout_seconds,
                "retry_attempts": config.retry_attempts,
                **config.config,
            }
            for name, config in self.config.provider_configs.items()
        }

    def is_mock_environment(self) -> bool:
        """Check if running in mock environment."""
        return (
            self.config.database.provider == DatabaseProvider.MOCK and self.config.messaging.provider == MessagingProvider.MOCK
        )

    def is_aws_environment(self) -> bool:
        """Check if running in AWS environment."""
        return (
            self.config.database.provider == DatabaseProvider.AWS_DYNAMODB
            or self.config.messaging.provider == MessagingProvider.AWS_SQS
            or self.config.logging.provider == LoggingProvider.AWS_CLOUDWATCH
        )

    def get_environment_summary(self) -> Dict[str, str]:
        """Get summary of selected services."""
        return {
            "environment": self.config.environment.value,
            "database": self.config.database.provider.value,
            "messaging": self.config.messaging.provider.value,
            "logging": self.config.logging.provider.value,
            "debug": str(self.config.debug),
            "providers_enabled": str(len([p for p in self.config.provider_configs.values() if p.enabled])),
        }
