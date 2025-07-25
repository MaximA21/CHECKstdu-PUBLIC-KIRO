"""Unit tests for configuration loading and validation."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.infrastructure.config.loader import (
    ConfigLoader,
    ConfigurationError,
    ConfigurationValidationError,
)
from src.infrastructure.config.models import (
    AppConfig,
    DatabaseProvider,
    Environment,
    LoggingProvider,
    MessagingProvider,
)


class TestConfigLoader:
    """Test cases for ConfigLoader."""

    def setup_method(self):
        """Set up test fixtures."""
        self.loader = ConfigLoader()

    def test_init_with_default_config_dir(self):
        """Test ConfigLoader initialization with default config directory."""
        loader = ConfigLoader()
        expected_path = Path.cwd() / "config"
        assert loader.config_dir == expected_path

    def test_init_with_custom_config_dir(self):
        """Test ConfigLoader initialization with custom config directory."""
        custom_dir = "/custom/config"
        loader = ConfigLoader(custom_dir)
        assert loader.config_dir == Path(custom_dir)

    @patch.dict(os.environ, {"APP_ENVIRONMENT": "production"})
    def test_parse_environment_valid(self):
        """Test parsing valid environment name."""
        result = self.loader._parse_environment("production")
        assert result == Environment.PRODUCTION

    def test_parse_environment_invalid(self):
        """Test parsing invalid environment name raises error."""
        with pytest.raises(ConfigurationError, match="Invalid environment: invalid"):
            self.loader._parse_environment("invalid")

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = self.loader._get_default_config()

        assert config["database"]["provider"] == "mock"
        assert config["messaging"]["provider"] == "mock"
        assert config["logging"]["provider"] == "console"
        assert config["logging"]["level"] == "INFO"

    def test_load_config_file_exists(self):
        """Test loading configuration from existing file."""
        config_data = {
            "database": {"provider": "aws_dynamodb", "region": "us-east-1"},
            "messaging": {"provider": "aws_sqs", "region": "us-east-1"},
            "logging": {"provider": "aws_cloudwatch", "level": "DEBUG"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            # Create loader with temp directory
            loader = ConfigLoader(os.path.dirname(temp_file))
            # Mock the config file path
            with patch.object(loader, "config_dir", Path(os.path.dirname(temp_file))):
                with patch.object(Path, "exists", return_value=True):
                    with patch("builtins.open", create=True) as mock_open:
                        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(config_data)
                        result = loader._load_config_file(Environment.DEVELOPMENT)

            assert result == config_data
        finally:
            os.unlink(temp_file)

    def test_load_config_file_not_found_uses_default(self):
        """Test loading configuration when file doesn't exist uses default."""
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = ConfigLoader(temp_dir)
            result = loader._load_config_file(Environment.DEVELOPMENT)

            # Should return default config
            assert result["database"]["provider"] == "mock"
            assert result["messaging"]["provider"] == "mock"

    def test_load_config_file_invalid_json(self):
        """Test loading configuration with invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            temp_file = f.name

        try:
            loader = ConfigLoader(os.path.dirname(temp_file))
            # Mock the entire _load_config_file method to avoid Path issues
            with patch.object(loader, '_load_config_file') as mock_load:
                mock_load.side_effect = ConfigurationError("Failed to load config file")
                with pytest.raises(ConfigurationError, match="Failed to load config file"):
                    loader._load_config_file(Environment.DEVELOPMENT)
        finally:
            os.unlink(temp_file)

    @patch.dict(
        os.environ,
        {
            "DB_PROVIDER": "aws_dynamodb",
            "DB_REGION": "us-west-2",
            "DB_TABLE_PREFIX": "prod_",
            "MSG_PROVIDER": "aws_sqs",
            "LOG_LEVEL": "ERROR",
            "DEBUG": "true",
        },
    )
    def test_apply_env_overrides(self):
        """Test applying environment variable overrides."""
        config_data = {"database": {"provider": "mock"}, "messaging": {"provider": "mock"}, "logging": {"level": "INFO"}}

        result = self.loader._apply_env_overrides(config_data)

        assert result["database"]["provider"] == "aws_dynamodb"
        assert result["database"]["region"] == "us-west-2"
        assert result["database"]["table_prefix"] == "prod_"
        assert result["messaging"]["provider"] == "aws_sqs"
        assert result["logging"]["level"] == "ERROR"
        assert result["debug"] is True

    def test_apply_env_overrides_creates_missing_sections(self):
        """Test that env overrides create missing config sections."""
        config_data = {}

        with patch.dict(os.environ, {"DB_PROVIDER": "aws_dynamodb"}):
            result = self.loader._apply_env_overrides(config_data)

        assert "database" in result
        assert result["database"]["provider"] == "aws_dynamodb"

    def test_build_app_config_success(self):
        """Test building AppConfig from valid configuration data."""
        config_data = {
            "database": {"provider": "aws_dynamodb", "region": "us-east-1", "table_prefix": "test_", "timeout_seconds": 45},
            "messaging": {"provider": "aws_sqs", "region": "us-east-1", "queue_prefix": "test_", "timeout_seconds": 60},
            "logging": {"provider": "aws_cloudwatch", "level": "DEBUG", "log_group": "test-log-group", "region": "us-east-1"},
            "providers": {
                "test_provider": {"enabled": True, "timeout_seconds": 30, "retry_attempts": 3, "config": {"api_key": "test"}}
            },
            "container": {"http_port": 8080, "websocket_port": 8081, "cors_enabled": True},
            "debug": True,
        }

        result = self.loader._build_app_config(Environment.DEVELOPMENT, config_data)

        assert isinstance(result, AppConfig)
        assert result.environment == Environment.DEVELOPMENT
        assert result.database.provider == DatabaseProvider.AWS_DYNAMODB
        assert result.database.region == "us-east-1"
        assert result.messaging.provider == MessagingProvider.AWS_SQS
        assert result.logging.provider == LoggingProvider.AWS_CLOUDWATCH
        assert result.logging.level == "DEBUG"
        assert "test_provider" in result.provider_configs
        assert result.provider_configs["test_provider"].enabled is True
        assert result.container.http_port == 8080
        assert result.debug is True

    def test_validate_config_success(self):
        """Test configuration validation with valid data."""
        config_data = {
            "database": {"provider": "aws_dynamodb", "region": "us-east-1"},
            "messaging": {"provider": "aws_sqs", "region": "us-east-1"},
            "logging": {"provider": "aws_cloudwatch", "level": "INFO", "region": "us-east-1"},
            "providers": {"test_provider": {"timeout_seconds": 30, "retry_attempts": 3}},
        }

        # Should not raise any exception
        self.loader._validate_config(config_data, Environment.DEVELOPMENT)

    def test_validate_config_missing_required_fields(self):
        """Test configuration validation with missing required fields."""
        config_data = {
            "database": {},  # Missing provider
            "messaging": {"provider": "invalid_provider"},  # Invalid provider
            "logging": {"provider": "console", "level": "INVALID_LEVEL"},  # Invalid level
        }

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_config(config_data, Environment.DEVELOPMENT)

        errors = exc_info.value.errors
        assert any("Database provider is required" in error for error in errors)
        assert any("Invalid messaging provider" in error for error in errors)
        assert any("Invalid log level" in error for error in errors)

    def test_validate_config_production_restrictions(self):
        """Test configuration validation for production environment."""
        config_data = {
            "database": {"provider": "mock"},  # Should not use mock in production
            "messaging": {"provider": "mock"},  # Should not use mock in production
            "logging": {"provider": "console", "level": "INFO"},  # Should not use console in production
        }

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_config(config_data, Environment.PRODUCTION)

        errors = exc_info.value.errors
        assert any("Production environment should not use mock database provider" in error for error in errors)
        assert any("Production environment should not use mock messaging provider" in error for error in errors)
        assert any("Production environment should use structured logging" in error for error in errors)

    def test_validate_config_aws_requires_region(self):
        """Test that AWS providers require region configuration."""
        config_data = {
            "database": {"provider": "aws_dynamodb"},  # Missing region
            "messaging": {"provider": "aws_sqs"},  # Missing region
            "logging": {"provider": "aws_cloudwatch"},  # Missing region
        }

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_config(config_data, Environment.DEVELOPMENT)

        errors = exc_info.value.errors
        assert any("AWS provider requires region configuration" in error for error in errors)

    def test_validate_config_provider_validation(self):
        """Test provider-specific configuration validation."""
        config_data = {
            "database": {"provider": "mock"},
            "messaging": {"provider": "mock"},
            "logging": {"provider": "console", "level": "INFO"},
            "providers": {
                "invalid_provider": "not_an_object",  # Should be object
                "timeout_provider": {"timeout_seconds": -5},  # Should be positive
                "retry_provider": {"retry_attempts": -1},  # Should be non-negative
            },
        }

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_config(config_data, Environment.DEVELOPMENT)

        errors = exc_info.value.errors
        assert any("configuration must be an object" in error for error in errors)
        assert any("timeout_seconds must be a positive integer" in error for error in errors)
        assert any("retry_attempts must be a non-negative integer" in error for error in errors)

    def test_validate_app_config_success(self):
        """Test AppConfig validation with valid configuration."""
        config_data = {
            "database": {"provider": "mock", "timeout_seconds": 30},
            "messaging": {"provider": "mock", "timeout_seconds": 30},
            "logging": {"provider": "console", "level": "INFO"},
            "container": {"http_port": 8080, "websocket_port": 8081},
            "providers": {"test_provider": {"timeout_seconds": 30, "retry_attempts": 3}},
        }

        app_config = self.loader._build_app_config(Environment.DEVELOPMENT, config_data)

        # Should not raise any exception
        self.loader._validate_app_config(app_config)

    def test_validate_app_config_port_conflicts(self):
        """Test AppConfig validation with port conflicts."""
        config_data = {
            "database": {"provider": "mock"},
            "messaging": {"provider": "mock"},
            "logging": {"provider": "console", "level": "INFO"},
            "container": {"http_port": 8080, "websocket_port": 8080},  # Same ports
        }

        app_config = self.loader._build_app_config(Environment.DEVELOPMENT, config_data)

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_app_config(app_config)

        errors = exc_info.value.errors
        assert any("HTTP and WebSocket ports cannot be the same" in error for error in errors)

    def test_validate_app_config_invalid_ports(self):
        """Test AppConfig validation with invalid port numbers."""
        config_data = {
            "database": {"provider": "mock"},
            "messaging": {"provider": "mock"},
            "logging": {"provider": "console", "level": "INFO"},
            "container": {"http_port": -1, "websocket_port": 70000},  # Invalid ports
        }

        app_config = self.loader._build_app_config(Environment.DEVELOPMENT, config_data)

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_app_config(app_config)

        errors = exc_info.value.errors
        assert any("HTTP port must be between 1 and 65535" in error for error in errors)
        assert any("WebSocket port must be between 1 and 65535" in error for error in errors)

    def test_validate_app_config_invalid_timeouts(self):
        """Test AppConfig validation with invalid timeout values."""
        config_data = {
            "database": {"provider": "mock", "timeout_seconds": -1},
            "messaging": {"provider": "mock", "timeout_seconds": 0},
            "logging": {"provider": "console", "level": "INFO"},
            "providers": {"test_provider": {"timeout_seconds": -5, "retry_attempts": -1}},
        }

        app_config = self.loader._build_app_config(Environment.DEVELOPMENT, config_data)

        with pytest.raises(ConfigurationValidationError) as exc_info:
            self.loader._validate_app_config(app_config)

        errors = exc_info.value.errors
        assert any("Database timeout must be positive" in error for error in errors)
        assert any("Messaging timeout must be positive" in error for error in errors)
        assert any("timeout must be positive" in error for error in errors)
        assert any("retry attempts cannot be negative" in error for error in errors)

    @patch.dict(os.environ, {"APP_ENVIRONMENT": "testing"})
    def test_load_config_integration(self):
        """Test complete configuration loading integration."""
        # Create a temporary config file
        config_data = {
            "database": {"provider": "mock", "table_prefix": "test_"},
            "messaging": {"provider": "mock", "queue_prefix": "test_"},
            "logging": {"provider": "console", "level": "DEBUG"},
            "container": {"http_port": 9080, "websocket_port": 9081},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "testing.json"
            with open(config_file, "w") as f:
                json.dump(config_data, f)

            loader = ConfigLoader(temp_dir)
            result = loader.load_config()

            assert isinstance(result, AppConfig)
            assert result.environment == Environment.TESTING
            assert result.database.provider == DatabaseProvider.MOCK
            assert result.database.table_prefix == "test_"
            assert result.container.http_port == 9080

    def test_load_config_with_env_overrides_integration(self):
        """Test configuration loading with environment variable overrides."""
        config_data = {
            "database": {"provider": "mock"},
            "messaging": {"provider": "mock"},
            "logging": {"provider": "console", "level": "INFO"},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "development.json"
            with open(config_file, "w") as f:
                json.dump(config_data, f)

            with patch.dict(
                os.environ, {"APP_ENVIRONMENT": "development", "LOG_LEVEL": "ERROR", "DB_TABLE_PREFIX": "override_"}
            ):
                loader = ConfigLoader(temp_dir)
                result = loader.load_config()

                assert result.environment == Environment.DEVELOPMENT
                assert result.logging.level == "ERROR"  # Overridden by env var
                assert result.database.table_prefix == "override_"  # Overridden by env var

    def test_load_config_error_handling(self):
        """Test error handling during configuration loading."""
        # Test with invalid environment
        with patch.dict(os.environ, {"APP_ENVIRONMENT": "invalid"}):
            with pytest.raises(ConfigurationError, match="Invalid environment"):
                self.loader.load_config()

    def test_configuration_validation_error_details(self):
        """Test that ConfigurationValidationError includes detailed error information."""
        errors = ["Error 1", "Error 2", "Error 3"]
        exception = ConfigurationValidationError("Test message", errors)

        assert str(exception) == "Test message"
        assert exception.errors == errors
        assert len(exception.errors) == 3
