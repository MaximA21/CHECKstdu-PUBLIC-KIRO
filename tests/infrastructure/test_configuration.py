"""Tests for configuration management system."""

import os
import pytest
import tempfile
import json
from pathlib import Path

from src.infrastructure.config.loader import ConfigLoader, ConfigurationError, ConfigurationValidationError
from src.infrastructure.config.validator import ConfigValidator
from src.infrastructure.config.service_selector import ServiceSelector
from src.infrastructure.config.models import Environment, DatabaseProvider, MessagingProvider, LoggingProvider


class TestConfigLoader:
    """Test configuration loading functionality."""
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        loader = ConfigLoader()
        config = loader.load_config()
        
        assert config is not None
        assert config.environment in [Environment.DEVELOPMENT, Environment.TESTING, Environment.STAGING, Environment.PRODUCTION]
        assert config.database is not None
        assert config.messaging is not None
        assert config.logging is not None
    
    def test_load_environment_specific_config(self):
        """Test loading environment-specific configuration."""
        # Test development environment
        os.environ['APP_ENVIRONMENT'] = 'development'
        loader = ConfigLoader()
        config = loader.load_config()
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is True
        assert config.logging.level == "DEBUG"
    
    def test_environment_variable_overrides(self):
        """Test environment variable overrides."""
        os.environ['APP_ENVIRONMENT'] = 'development'
        os.environ['DB_PROVIDER'] = 'aws_dynamodb'
        os.environ['LOG_LEVEL'] = 'ERROR'
        os.environ['DEBUG'] = 'false'
        
        try:
            loader = ConfigLoader()
            config = loader.load_config()
            
            assert config.database.provider == DatabaseProvider.AWS_DYNAMODB
            assert config.logging.level == "ERROR"
            assert config.debug is False
        finally:
            # Clean up environment variables
            for key in ['DB_PROVIDER', 'LOG_LEVEL', 'DEBUG']:
                if key in os.environ:
                    del os.environ[key]
    
    def test_invalid_environment(self):
        """Test handling of invalid environment."""
        os.environ['APP_ENVIRONMENT'] = 'invalid_env'
        
        try:
            loader = ConfigLoader()
            with pytest.raises(ConfigurationError):
                loader.load_config()
        finally:
            os.environ['APP_ENVIRONMENT'] = 'testing'
    
    def test_missing_config_file_fallback(self):
        """Test fallback behavior when config file is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            loader = ConfigLoader(config_dir=temp_dir)
            config = loader.load_config()
            
            # Should use default configuration
            assert config is not None
            assert config.database.provider == DatabaseProvider.MOCK
            assert config.messaging.provider == MessagingProvider.MOCK
    
    def test_invalid_json_config(self):
        """Test handling of invalid JSON configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "development.json"
            config_file.write_text("{ invalid json }")
            
            os.environ['APP_ENVIRONMENT'] = 'development'
            loader = ConfigLoader(config_dir=temp_dir)
            
            with pytest.raises(ConfigurationError):
                loader.load_config()
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create invalid configuration
            invalid_config = {
                "database": {"provider": "invalid_provider"},
                "messaging": {"provider": "invalid_messaging"},
                "logging": {"provider": "invalid_logging", "level": "INVALID_LEVEL"}
            }
            
            config_file = Path(temp_dir) / "development.json"
            config_file.write_text(json.dumps(invalid_config))
            
            os.environ['APP_ENVIRONMENT'] = 'development'
            loader = ConfigLoader(config_dir=temp_dir)
            
            with pytest.raises(ConfigurationValidationError) as exc_info:
                loader.load_config()
            
            assert len(exc_info.value.errors) > 0
    
    def test_production_validation(self):
        """Test production-specific validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create production config with mock services (should fail validation)
            prod_config = {
                "database": {"provider": "mock"},
                "messaging": {"provider": "mock"},
                "logging": {"provider": "console"}
            }
            
            config_file = Path(temp_dir) / "production.json"
            config_file.write_text(json.dumps(prod_config))
            
            os.environ['APP_ENVIRONMENT'] = 'production'
            loader = ConfigLoader(config_dir=temp_dir)
            
            with pytest.raises(ConfigurationValidationError) as exc_info:
                loader.load_config()
            
            errors = exc_info.value.errors
            assert any("mock database" in error for error in errors)
            assert any("mock messaging" in error for error in errors)


class TestConfigValidator:
    """Test configuration validation functionality."""
    
    def test_environment_consistency_validation(self):
        """Test environment consistency validation."""
        from src.infrastructure.config.models import AppConfig, DatabaseConfig, MessagingConfig, LoggingConfig
        
        # Create production config with debug enabled (should warn)
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB, region="eu-central-1"),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS, region="eu-central-1"),
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH, region="eu-central-1"),
            debug=True
        )
        
        warnings = ConfigValidator.validate_environment_consistency(config)
        assert any("Debug mode is enabled in production" in warning for warning in warnings)
    
    def test_aws_configuration_validation(self):
        """Test AWS-specific configuration validation."""
        from src.infrastructure.config.models import AppConfig, DatabaseConfig, MessagingConfig, LoggingConfig
        
        # Create AWS config without regions (should error)
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS),
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH)
        )
        
        errors = ConfigValidator.validate_aws_configuration(config)
        assert any("DynamoDB requires region" in error for error in errors)
        assert any("SQS requires region" in error for error in errors)
        assert any("CloudWatch requires region" in error for error in errors)
    
    def test_provider_configuration_validation(self):
        """Test provider configuration validation."""
        from src.infrastructure.config.models import AppConfig, DatabaseConfig, MessagingConfig, LoggingConfig, ProviderConfig
        
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            provider_configs={
                "byteme": ProviderConfig(name="byteme", enabled=False, timeout_seconds=120, retry_attempts=10)
            }
        )
        
        warnings = ConfigValidator.validate_provider_configuration(config)
        assert any("disabled in production" in warning for warning in warnings)
        assert any("high timeout" in warning for warning in warnings)
        assert any("high retry attempts" in warning for warning in warnings)


class TestServiceSelector:
    """Test service selection functionality."""
    
    def test_mock_service_selection(self):
        """Test selection of mock services."""
        from src.infrastructure.config.models import AppConfig, DatabaseConfig, MessagingConfig, LoggingConfig
        
        config = AppConfig(
            environment=Environment.TESTING,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE)
        )
        
        selector = ServiceSelector(config)
        
        # Test repository selection
        search_repo = selector.get_search_result_repository()
        connection_repo = selector.get_connection_repository()
        
        assert search_repo is not None
        assert connection_repo is not None
        
        # Test messaging selection
        message_queue = selector.get_message_queue()
        workflow_orchestrator = selector.get_workflow_orchestrator()
        connection_manager = selector.get_connection_manager()
        
        assert message_queue is not None
        assert workflow_orchestrator is not None
        assert connection_manager is not None
        
        # Test logging selection
        logger_factory = selector.get_logger_factory()
        assert logger_factory is not None
        
        # Test environment checks
        assert selector.is_mock_environment() is True
        assert selector.is_aws_environment() is False
    
    def test_aws_service_selection(self):
        """Test selection of AWS services."""
        from src.infrastructure.config.models import AppConfig, DatabaseConfig, MessagingConfig, LoggingConfig
        
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB, region="eu-central-1"),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS, region="eu-central-1"),
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH, region="eu-central-1")
        )
        
        selector = ServiceSelector(config)
        
        # Test environment checks
        assert selector.is_mock_environment() is False
        assert selector.is_aws_environment() is True
        
        # Test environment summary
        summary = selector.get_environment_summary()
        assert summary["environment"] == "production"
        assert summary["database"] == "aws_dynamodb"
        assert summary["messaging"] == "aws_sqs"
        assert summary["logging"] == "aws_cloudwatch"
    
    def test_provider_configs(self):
        """Test provider configuration retrieval."""
        from src.infrastructure.config.models import AppConfig, DatabaseConfig, MessagingConfig, LoggingConfig, ProviderConfig
        
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            provider_configs={
                "byteme": ProviderConfig(
                    name="byteme",
                    enabled=True,
                    timeout_seconds=30,
                    retry_attempts=3,
                    config={"base_url": "https://api.byteme.com"}
                )
            }
        )
        
        selector = ServiceSelector(config)
        provider_configs = selector.get_provider_configs()
        
        assert "byteme" in provider_configs
        assert provider_configs["byteme"]["enabled"] is True
        assert provider_configs["byteme"]["timeout_seconds"] == 30
        assert provider_configs["byteme"]["base_url"] == "https://api.byteme.com"


class TestConfigurationIntegration:
    """Test integration between configuration components."""
    
    def test_full_configuration_flow(self):
        """Test complete configuration loading and service selection flow."""
        os.environ['APP_ENVIRONMENT'] = 'development'
        
        try:
            # Load configuration
            loader = ConfigLoader()
            config = loader.load_config()
            
            # Validate configuration
            validation_results = ConfigValidator.get_all_validation_results(config)
            
            # Should have minimal warnings for development
            assert isinstance(validation_results, dict)
            
            # Create service selector
            selector = ServiceSelector(config)
            
            # Test service creation
            search_repo = selector.get_search_result_repository()
            message_queue = selector.get_message_queue()
            logger_factory = selector.get_logger_factory()
            
            assert search_repo is not None
            assert message_queue is not None
            assert logger_factory is not None
            
        finally:
            if 'APP_ENVIRONMENT' in os.environ:
                del os.environ['APP_ENVIRONMENT']
    
    def test_bootstrap_integration(self):
        """Test integration with bootstrap system."""
        from src.shared.dependency_injection.bootstrap import get_config
        
        os.environ['APP_ENVIRONMENT'] = 'testing'
        
        try:
            config = get_config()
            assert config.environment == Environment.TESTING
            assert config.is_testing is True
            
        finally:
            if 'APP_ENVIRONMENT' in os.environ:
                del os.environ['APP_ENVIRONMENT']


# Cleanup after tests
def teardown_module():
    """Clean up environment variables after tests."""
    env_vars_to_clean = [
        'APP_ENVIRONMENT', 'DB_PROVIDER', 'MSG_PROVIDER', 'LOG_PROVIDER',
        'DB_REGION', 'MSG_REGION', 'LOG_LEVEL', 'DEBUG'
    ]
    
    for var in env_vars_to_clean:
        if var in os.environ:
            del os.environ[var]