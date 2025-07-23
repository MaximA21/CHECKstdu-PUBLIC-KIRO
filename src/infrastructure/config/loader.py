"""Configuration loading and validation."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    AppConfig,
    ContainerConfig,
    DatabaseConfig,
    DatabaseProvider,
    Environment,
    LoggingConfig,
    LoggingProvider,
    MessagingConfig,
    MessagingProvider,
    ProviderConfig,
)


class ConfigurationError(Exception):
    """Configuration-related errors."""

    pass


class ConfigurationValidationError(ConfigurationError):
    """Configuration validation errors."""

    def __init__(self, message: str, errors: List[str]):
        super().__init__(message)
        self.errors = errors


class ConfigLoader:
    """Loads and validates application configuration from environment and files."""

    def __init__(self, config_dir: Optional[str] = None):
        """Initialize config loader.

        Args:
            config_dir: Directory containing configuration files
        """
        self.config_dir = Path(config_dir) if config_dir else Path.cwd() / "config"

    def load_config(self) -> AppConfig:
        """Load configuration from environment variables and files."""
        try:
            # Determine environment
            env_name = os.getenv("APP_ENVIRONMENT", "development").lower()
            environment = self._parse_environment(env_name)

            # Load base configuration
            config_data = self._load_config_file(environment)

            # Override with environment variables
            config_data = self._apply_env_overrides(config_data)

            # Validate configuration
            self._validate_config(config_data, environment)

            # Build configuration objects
            app_config = self._build_app_config(environment, config_data)

            # Validate final configuration
            self._validate_app_config(app_config)

            return app_config

        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {str(e)}") from e

    def _parse_environment(self, env_name: str) -> Environment:
        """Parse environment name to Environment enum."""
        try:
            return Environment(env_name)
        except ValueError:
            raise ConfigurationError(f"Invalid environment: {env_name}")

    def _load_config_file(self, environment: Environment) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        config_file = self.config_dir / f"{environment.value}.json"

        if not config_file.exists():
            # Try default config
            config_file = self.config_dir / "default.json"

        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                raise ConfigurationError(f"Failed to load config file {config_file}: {str(e)}")

        # Return minimal default configuration
        return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when no config file is found."""
        return {
            "database": {"provider": "mock", "table_prefix": "dev_"},
            "messaging": {"provider": "mock", "queue_prefix": "dev_"},
            "logging": {"provider": "console", "level": "INFO"},
            "providers": {},
        }

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Database overrides
        if "database" not in config_data:
            config_data["database"] = {}

        if os.getenv("DB_PROVIDER"):
            config_data["database"]["provider"] = os.getenv("DB_PROVIDER")
        if os.getenv("DB_REGION"):
            config_data["database"]["region"] = os.getenv("DB_REGION")
        if os.getenv("DB_TABLE_PREFIX"):
            config_data["database"]["table_prefix"] = os.getenv("DB_TABLE_PREFIX")

        # Messaging overrides
        if "messaging" not in config_data:
            config_data["messaging"] = {}

        if os.getenv("MSG_PROVIDER"):
            config_data["messaging"]["provider"] = os.getenv("MSG_PROVIDER")
        if os.getenv("MSG_REGION"):
            config_data["messaging"]["region"] = os.getenv("MSG_REGION")
        if os.getenv("MSG_QUEUE_PREFIX"):
            config_data["messaging"]["queue_prefix"] = os.getenv("MSG_QUEUE_PREFIX")

        # Logging overrides
        if "logging" not in config_data:
            config_data["logging"] = {}

        if os.getenv("LOG_PROVIDER"):
            config_data["logging"]["provider"] = os.getenv("LOG_PROVIDER")
        if os.getenv("LOG_LEVEL"):
            config_data["logging"]["level"] = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_GROUP"):
            config_data["logging"]["log_group"] = os.getenv("LOG_GROUP")

        # Debug mode
        if os.getenv("DEBUG"):
            config_data["debug"] = os.getenv("DEBUG").lower() in ("true", "1", "yes")

        return config_data

    def _build_app_config(self, environment: Environment, config_data: Dict[str, Any]) -> AppConfig:
        """Build AppConfig object from configuration data."""
        # Build database config
        db_data = config_data.get("database", {})
        database_config = DatabaseConfig(
            provider=DatabaseProvider(db_data.get("provider", "mock")),
            connection_string=db_data.get("connection_string"),
            table_prefix=db_data.get("table_prefix", ""),
            region=db_data.get("region"),
            timeout_seconds=db_data.get("timeout_seconds", 30),
        )

        # Build messaging config
        msg_data = config_data.get("messaging", {})
        messaging_config = MessagingConfig(
            provider=MessagingProvider(msg_data.get("provider", "mock")),
            connection_string=msg_data.get("connection_string"),
            queue_prefix=msg_data.get("queue_prefix", ""),
            region=msg_data.get("region"),
            timeout_seconds=msg_data.get("timeout_seconds", 30),
        )

        # Build logging config
        log_data = config_data.get("logging", {})
        logging_config = LoggingConfig(
            provider=LoggingProvider(log_data.get("provider", "console")),
            level=log_data.get("level", "INFO"),
            structured=log_data.get("structured", True),
            log_group=log_data.get("log_group"),
            region=log_data.get("region"),
        )

        # Build provider configs
        provider_configs = {}
        providers_data = config_data.get("providers", {})
        for name, provider_data in providers_data.items():
            provider_configs[name] = ProviderConfig(
                name=name,
                enabled=provider_data.get("enabled", True),
                timeout_seconds=provider_data.get("timeout_seconds", 30),
                retry_attempts=provider_data.get("retry_attempts", 3),
                config=provider_data.get("config", {}),
            )

        # Build container config
        container_data = config_data.get("container", {})
        container_config = ContainerConfig(
            http_port=container_data.get("http_port", 8080),
            websocket_port=container_data.get("websocket_port", 8081),
            cors_enabled=container_data.get("cors_enabled", True),
            request_timeout_seconds=container_data.get("request_timeout_seconds", 30),
            max_connections=container_data.get("max_connections", 1000),
            health_check_interval=container_data.get("health_check_interval", 30),
        )

        return AppConfig(
            environment=environment,
            database=database_config,
            messaging=messaging_config,
            logging=logging_config,
            provider_configs=provider_configs,
            container=container_config,
            debug=config_data.get("debug", False),
        )

    def _validate_config(self, config_data: Dict[str, Any], environment: Environment) -> None:
        """Validate configuration data before building objects."""
        errors = []

        # Validate database configuration
        db_config = config_data.get("database", {})
        if not db_config.get("provider"):
            errors.append("Database provider is required")
        else:
            try:
                DatabaseProvider(db_config["provider"])
            except ValueError:
                errors.append(f"Invalid database provider: {db_config['provider']}")

        # Validate messaging configuration
        msg_config = config_data.get("messaging", {})
        if not msg_config.get("provider"):
            errors.append("Messaging provider is required")
        else:
            try:
                MessagingProvider(msg_config["provider"])
            except ValueError:
                errors.append(f"Invalid messaging provider: {msg_config['provider']}")

        # Validate logging configuration
        log_config = config_data.get("logging", {})
        if not log_config.get("provider"):
            errors.append("Logging provider is required")
        else:
            try:
                LoggingProvider(log_config["provider"])
            except ValueError:
                errors.append(f"Invalid logging provider: {log_config['provider']}")

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_config.get("level") and log_config["level"] not in valid_levels:
            errors.append(f"Invalid log level: {log_config['level']}. Must be one of {valid_levels}")

        # Validate provider configurations
        providers = config_data.get("providers", {})
        for provider_name, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                errors.append(f"Provider '{provider_name}' configuration must be an object")
                continue

            if "timeout_seconds" in provider_config:
                timeout = provider_config["timeout_seconds"]
                if not isinstance(timeout, int) or timeout <= 0:
                    errors.append(f"Provider '{provider_name}' timeout_seconds must be a positive integer")

            if "retry_attempts" in provider_config:
                retries = provider_config["retry_attempts"]
                if not isinstance(retries, int) or retries < 0:
                    errors.append(f"Provider '{provider_name}' retry_attempts must be a non-negative integer")

        # Environment-specific validations
        if environment == Environment.PRODUCTION:
            # Production should use real services, not mocks
            if db_config.get("provider") == "mock":
                errors.append("Production environment should not use mock database provider")
            if msg_config.get("provider") == "mock":
                errors.append("Production environment should not use mock messaging provider")
            if log_config.get("provider") == "console":
                errors.append("Production environment should use structured logging, not console")

        # AWS-specific validations
        aws_providers = ["aws_dynamodb", "aws_sqs", "aws_cloudwatch"]
        for config_section, provider_key in [(db_config, "provider"), (msg_config, "provider"), (log_config, "provider")]:
            if config_section.get(provider_key) in aws_providers and not config_section.get("region"):
                errors.append(f"AWS {provider_key} requires region configuration")

        if errors:
            raise ConfigurationValidationError(f"Configuration validation failed with {len(errors)} errors", errors)

    def _validate_app_config(self, app_config: AppConfig) -> None:
        """Validate the final AppConfig object."""
        errors = []

        # Validate container ports
        if app_config.container.http_port == app_config.container.websocket_port:
            errors.append("HTTP and WebSocket ports cannot be the same")

        if app_config.container.http_port <= 0 or app_config.container.http_port > 65535:
            errors.append("HTTP port must be between 1 and 65535")

        if app_config.container.websocket_port <= 0 or app_config.container.websocket_port > 65535:
            errors.append("WebSocket port must be between 1 and 65535")

        # Validate timeout values
        if app_config.database.timeout_seconds <= 0:
            errors.append("Database timeout must be positive")

        if app_config.messaging.timeout_seconds <= 0:
            errors.append("Messaging timeout must be positive")

        # Validate provider configurations
        for name, provider_config in app_config.provider_configs.items():
            if provider_config.timeout_seconds <= 0:
                errors.append(f"Provider '{name}' timeout must be positive")

            if provider_config.retry_attempts < 0:
                errors.append(f"Provider '{name}' retry attempts cannot be negative")

        if errors:
            raise ConfigurationValidationError(f"AppConfig validation failed with {len(errors)} errors", errors)
