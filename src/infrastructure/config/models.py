"""Configuration models for the application."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class Environment(Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseProvider(Enum):
    """Database provider types."""
    AWS_DYNAMODB = "aws_dynamodb"
    AZURE_COSMOS = "azure_cosmos"
    MOCK = "mock"


class MessagingProvider(Enum):
    """Messaging provider types."""
    AWS_SQS = "aws_sqs"
    AZURE_SERVICEBUS = "azure_servicebus"
    MOCK = "mock"


class LoggingProvider(Enum):
    """Logging provider types."""
    AWS_CLOUDWATCH = "aws_cloudwatch"
    AZURE_MONITOR = "azure_monitor"
    CONSOLE = "console"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    provider: DatabaseProvider
    connection_string: Optional[str] = None
    table_prefix: str = ""
    region: Optional[str] = None
    timeout_seconds: int = 30


@dataclass
class MessagingConfig:
    """Messaging configuration."""
    provider: MessagingProvider
    connection_string: Optional[str] = None
    queue_prefix: str = ""
    region: Optional[str] = None
    timeout_seconds: int = 30


@dataclass
class LoggingConfig:
    """Logging configuration."""
    provider: LoggingProvider
    level: str = "INFO"
    structured: bool = True
    log_group: Optional[str] = None
    region: Optional[str] = None


@dataclass
class ProviderConfig:
    """External provider configuration."""
    name: str
    enabled: bool = True
    timeout_seconds: int = 30
    retry_attempts: int = 3
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContainerConfig:
    """Container deployment configuration."""
    http_port: int = 8080
    websocket_port: int = 8081
    cors_enabled: bool = True
    request_timeout_seconds: int = 30
    max_connections: int = 1000
    health_check_interval: int = 30


@dataclass
class AppConfig:
    """Main application configuration."""
    environment: Environment
    database: DatabaseConfig
    messaging: MessagingConfig
    logging: LoggingConfig
    provider_configs: Dict[str, ProviderConfig] = field(default_factory=dict)
    container: ContainerConfig = field(default_factory=ContainerConfig)
    debug: bool = False
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == Environment.TESTING
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT