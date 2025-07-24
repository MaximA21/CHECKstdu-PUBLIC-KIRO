"""Unit tests for infrastructure configuration."""

import pytest
import os
from unittest.mock import patch, Mock
from src.infrastructure.config import AppConfig, Environment
from src.infrastructure.config.loader import ConfigLoader
from src.infrastructure.config.service_selector import ServiceSelector


class TestAppConfig:
    """Test AppConfig class."""

    def test_app_config_creation_with_defaults(self):
        """Test creating AppConfig with default values."""
        config = AppConfig()
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.log_level == "INFO"
        assert config.aws_region == "eu-central-1"

    def test_app_config_creation_with_custom_values(self):
        """Test creating AppConfig with custom values."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            log_level="DEBUG",
            aws_region="us-east-1",
            dynamodb_table_name="custom-table",
            sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/custom-queue"
        )
        
        assert config.environment == Environment.PRODUCTION
        assert config.log_level == "DEBUG"
        assert config.aws_region == "us-east-1"
        assert config.dynamodb_table_name == "custom-table"
        assert "custom-queue" in config.sqs_queue_url

    def test_app_config_validation(self):
        """Test AppConfig validation."""
        # Test invalid log level
        with pytest.raises(ValueError):
            AppConfig(log_level="INVALID")

    def test_app_config_is_production(self):
        """Test production environment detection."""
        prod_config = AppConfig(environment=Environment.PRODUCTION)
        dev_config = AppConfig(environment=Environment.DEVELOPMENT)
        
        assert prod_config.is_production() is True
        assert dev_config.is_production() is False

    def test_app_config_is_development(self):
        """Test development environment detection."""
        prod_config = AppConfig(environment=Environment.PRODUCTION)
        dev_config = AppConfig(environment=Environment.DEVELOPMENT)
        
        assert prod_config.is_development() is False
        assert dev_config.is_development() is True


class TestConfigLoader:
    """Test ConfigLoader class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.loader = ConfigLoader()

    @patch.dict(os.environ, {
        'APP_ENVIRONMENT': 'production',
        'LOG_LEVEL': 'DEBUG',
        'AWS_REGION': 'us-west-2'
    })
    def test_load_from_environment(self):
        """Test loading configuration from environment variables."""
        config = self.loader.load_from_environment()
        
        assert config.environment == Environment.PRODUCTION
        assert config.log_level == "DEBUG"
        assert config.aws_region == "us-west-2"

    @patch.dict(os.environ, {}, clear=True)
    def test_load_from_environment_with_defaults(self):
        """Test loading configuration with default values."""
        config = self.loader.load_from_environment()
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.log_level == "INFO"
        assert config.aws_region == "eu-central-1"

    def test_load_from_file_success(self):
        """Test loading configuration from file."""
        # Create a temporary config file
        import tempfile
        import json
        
        config_data = {
            "environment": "staging",
            "log_level": "WARNING",
            "aws_region": "eu-west-1",
            "dynamodb_table_name": "test-table"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            config = self.loader.load_from_file(config_file)
            
            assert config.environment == Environment.STAGING
            assert config.log_level == "WARNING"
            assert config.aws_region == "eu-west-1"
            assert config.dynamodb_table_name == "test-table"
        finally:
            os.unlink(config_file)

    def test_load_from_file_not_found(self):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            self.loader.load_from_file("nonexistent-config.json")

    def test_load_from_file_invalid_json(self):
        """Test loading configuration from invalid JSON file."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            config_file = f.name
        
        try:
            with pytest.raises(ValueError):
                self.loader.load_from_file(config_file)
        finally:
            os.unlink(config_file)

    @patch.dict(os.environ, {'APP_ENVIRONMENT': 'testing'})
    def test_load_config_auto_detection(self):
        """Test automatic configuration loading."""
        config = self.loader.load_config()
        
        assert config.environment == Environment.TESTING

    def test_merge_configs(self):
        """Test merging multiple configurations."""
        base_config = AppConfig(
            environment=Environment.DEVELOPMENT,
            log_level="INFO",
            aws_region="eu-central-1"
        )
        
        override_config = AppConfig(
            log_level="DEBUG",
            dynamodb_table_name="override-table"
        )
        
        merged = self.loader.merge_configs(base_config, override_config)
        
        assert merged.environment == Environment.DEVELOPMENT  # From base
        assert merged.log_level == "DEBUG"  # From override
        assert merged.aws_region == "eu-central-1"  # From base
        assert merged.dynamodb_table_name == "override-table"  # From override


class TestServiceSelector:
    """Test ServiceSelector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AppConfig(environment=Environment.TESTING)
        self.selector = ServiceSelector(self.config)

    def test_should_use_mock_services_in_testing(self):
        """Test that mock services are used in testing environment."""
        assert self.selector.should_use_mock_services() is True

    def test_should_use_real_services_in_production(self):
        """Test that real services are used in production environment."""
        prod_config = AppConfig(environment=Environment.PRODUCTION)
        prod_selector = ServiceSelector(prod_config)
        
        assert prod_selector.should_use_mock_services() is False

    def test_get_dynamodb_service_mock(self):
        """Test getting mock DynamoDB service."""
        service = self.selector.get_dynamodb_service()
        
        # Should return mock service in testing environment
        assert service is not None
        assert hasattr(service, 'put_item')  # Mock should have DynamoDB methods

    def test_get_sqs_service_mock(self):
        """Test getting mock SQS service."""
        service = self.selector.get_sqs_service()
        
        # Should return mock service in testing environment
        assert service is not None
        assert hasattr(service, 'send_message')  # Mock should have SQS methods

    def test_get_lambda_service_mock(self):
        """Test getting mock Lambda service."""
        service = self.selector.get_lambda_service()
        
        # Should return mock service in testing environment
        assert service is not None
        assert hasattr(service, 'invoke')  # Mock should have Lambda methods

    @patch('boto3.client')
    def test_get_dynamodb_service_real(self, mock_boto3_client):
        """Test getting real DynamoDB service."""
        prod_config = AppConfig(environment=Environment.PRODUCTION)
        prod_selector = ServiceSelector(prod_config)
        
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        service = prod_selector.get_dynamodb_service()
        
        mock_boto3_client.assert_called_with('dynamodb', region_name='eu-central-1')
        assert service == mock_client

    def test_get_service_configuration(self):
        """Test getting service configuration."""
        config = self.selector.get_service_configuration()
        
        assert 'use_mock_services' in config
        assert 'aws_region' in config
        assert 'environment' in config
        assert config['use_mock_services'] is True  # Testing environment
        assert config['environment'] == 'testing'

    def test_validate_service_configuration(self):
        """Test service configuration validation."""
        # Valid configuration should not raise
        self.selector.validate_service_configuration()
        
        # Invalid configuration should raise
        invalid_config = AppConfig(aws_region="")
        invalid_selector = ServiceSelector(invalid_config)
        
        with pytest.raises(ValueError):
            invalid_selector.validate_service_configuration()

    def test_get_provider_service_configuration(self):
        """Test getting provider service configuration."""
        provider_config = self.selector.get_provider_service_configuration()
        
        assert 'timeout' in provider_config
        assert 'retry_attempts' in provider_config
        assert 'use_circuit_breaker' in provider_config
        assert provider_config['timeout'] > 0
        assert provider_config['retry_attempts'] >= 0

    def test_get_monitoring_configuration(self):
        """Test getting monitoring configuration."""
        monitoring_config = self.selector.get_monitoring_configuration()
        
        assert 'enable_metrics' in monitoring_config
        assert 'enable_tracing' in monitoring_config
        assert 'log_level' in monitoring_config
        
        # In testing, monitoring should be minimal
        assert monitoring_config['enable_metrics'] is False
        assert monitoring_config['enable_tracing'] is False