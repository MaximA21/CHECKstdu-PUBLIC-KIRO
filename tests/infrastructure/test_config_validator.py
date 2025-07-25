"""Unit tests for configuration validator."""

import pytest

from src.infrastructure.config.models import (
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
from src.infrastructure.config.validator import ConfigValidator


class TestConfigValidator:
    """Test cases for ConfigValidator."""

    def test_validate_environment_consistency_production_warnings(self):
        """Test environment consistency validation for production."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE, level="DEBUG"),
            debug=True,
        )

        warnings = ConfigValidator.validate_environment_consistency(config)

        assert any("Debug mode is enabled in production" in warning for warning in warnings)
        assert any("Using mock database in production" in warning for warning in warnings)
        assert any("Using mock messaging in production" in warning for warning in warnings)
        assert any("Using console logging in production" in warning for warning in warnings)
        assert any("Debug logging enabled in production" in warning for warning in warnings)

    def test_validate_environment_consistency_development_recommendations(self):
        """Test environment consistency validation for development."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            debug=False,
        )

        warnings = ConfigValidator.validate_environment_consistency(config)

        assert any("Debug mode is disabled in development" in warning for warning in warnings)
        assert any("Consider using mock database in development" in warning for warning in warnings)
        assert any("Consider using mock messaging in development" in warning for warning in warnings)

    def test_validate_environment_consistency_testing_requirements(self):
        """Test environment consistency validation for testing."""
        config = AppConfig(
            environment=Environment.TESTING,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS),
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH),
        )

        warnings = ConfigValidator.validate_environment_consistency(config)

        assert any("Tests should use mock database" in warning for warning in warnings)
        assert any("Tests should use mock messaging" in warning for warning in warnings)
        assert any("Tests should use console logging" in warning for warning in warnings)

    def test_validate_environment_consistency_no_warnings(self):
        """Test environment consistency validation with proper configuration."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            debug=True,
        )

        warnings = ConfigValidator.validate_environment_consistency(config)

        assert len(warnings) == 0

    def test_validate_aws_configuration_success(self):
        """Test AWS configuration validation with valid setup."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB, region="us-east-1"),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS, region="us-east-1"),
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH, region="us-east-1", log_group="test-log-group"),
        )

        errors = ConfigValidator.validate_aws_configuration(config)

        assert len(errors) == 0

    def test_validate_aws_configuration_missing_regions(self):
        """Test AWS configuration validation with missing regions."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB),  # Missing region
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS),  # Missing region
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH),  # Missing region and log group
        )

        errors = ConfigValidator.validate_aws_configuration(config)

        assert any("DynamoDB requires region configuration" in error for error in errors)
        assert any("SQS requires region configuration" in error for error in errors)
        assert any("CloudWatch requires region configuration" in error for error in errors)
        assert any("CloudWatch requires log group configuration" in error for error in errors)

    def test_validate_aws_configuration_multiple_regions_warning(self):
        """Test AWS configuration validation with multiple regions."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB, region="us-east-1"),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS, region="us-west-2"),  # Different region
            logging=LoggingConfig(
                provider=LoggingProvider.AWS_CLOUDWATCH,
                region="eu-west-1",  # Another different region
                log_group="test-log-group",
            ),
        )

        errors = ConfigValidator.validate_aws_configuration(config)

        assert any("Multiple AWS regions configured" in error for error in errors)
        assert any("us-east-1" in error and "us-west-2" in error and "eu-west-1" in error for error in errors)

    def test_validate_aws_configuration_non_aws_providers(self):
        """Test AWS configuration validation with non-AWS providers."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
        )

        errors = ConfigValidator.validate_aws_configuration(config)

        assert len(errors) == 0  # No AWS services, no errors

    def test_validate_provider_configuration_missing_providers(self):
        """Test provider configuration validation with missing providers."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            provider_configs={
                "byteme": ProviderConfig(name="byteme", enabled=True),
                "webwunder": ProviderConfig(name="webwunder", enabled=True),
                # Missing verbyndich and pingperfect
            },
        )

        warnings = ConfigValidator.validate_provider_configuration(config)

        assert any("Missing provider configurations" in warning for warning in warnings)
        assert any("verbyndich" in warning and "pingperfect" in warning for warning in warnings)

    def test_validate_provider_configuration_disabled_in_production(self):
        """Test provider configuration validation with disabled providers in production."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.AWS_DYNAMODB),
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS),
            logging=LoggingConfig(provider=LoggingProvider.AWS_CLOUDWATCH),
            provider_configs={
                "byteme": ProviderConfig(name="byteme", enabled=False),
                "verbyndich": ProviderConfig(name="verbyndich", enabled=True),
                "webwunder": ProviderConfig(name="webwunder", enabled=False),
                "pingperfect": ProviderConfig(name="pingperfect", enabled=True),
            },
        )

        warnings = ConfigValidator.validate_provider_configuration(config)

        assert any("Provider 'byteme' is disabled in production" in warning for warning in warnings)
        assert any("Provider 'webwunder' is disabled in production" in warning for warning in warnings)
        # Should not warn about enabled providers
        assert not any("verbyndich" in warning and "disabled" in warning for warning in warnings)
        assert not any("pingperfect" in warning and "disabled" in warning for warning in warnings)

    def test_validate_provider_configuration_high_timeouts_and_retries(self):
        """Test provider configuration validation with high timeouts and retries."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            provider_configs={
                "high_timeout": ProviderConfig(name="high_timeout", enabled=True, timeout_seconds=120),  # High timeout
                "high_retries": ProviderConfig(name="high_retries", enabled=True, retry_attempts=10),  # High retry attempts
                "normal_provider": ProviderConfig(name="normal_provider", enabled=True, timeout_seconds=30, retry_attempts=3),
            },
        )

        warnings = ConfigValidator.validate_provider_configuration(config)

        assert any("Provider 'high_timeout' has high timeout (120s)" in warning for warning in warnings)
        assert any("Provider 'high_retries' has high retry attempts (10)" in warning for warning in warnings)
        # Should not warn about normal provider
        assert not any("normal_provider" in warning for warning in warnings)

    def test_validate_provider_configuration_all_providers_present(self):
        """Test provider configuration validation with all required providers."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE, level="DEBUG"),
            provider_configs={
                "byteme": ProviderConfig(name="byteme", enabled=True, timeout_seconds=30, retry_attempts=3),
                "verbyndich": ProviderConfig(name="verbyndich", enabled=True, timeout_seconds=30, retry_attempts=3),
                "webwunder": ProviderConfig(name="webwunder", enabled=True, timeout_seconds=30, retry_attempts=3),
                "pingperfect": ProviderConfig(name="pingperfect", enabled=True, timeout_seconds=30, retry_attempts=3),
            },
            debug=True,
        )

        warnings = ConfigValidator.validate_provider_configuration(config)

        assert len(warnings) == 0

    def test_get_all_validation_results_comprehensive(self):
        """Test getting all validation results for comprehensive validation."""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),  # Should warn in production
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS),  # Missing region
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),  # Should warn in production
            provider_configs={
                "byteme": ProviderConfig(name="byteme", enabled=False, timeout_seconds=120),  # Disabled + high timeout
                # Missing other providers
            },
            debug=True,  # Should warn in production
        )

        results = ConfigValidator.get_all_validation_results(config)

        assert "environment_warnings" in results
        assert "aws_errors" in results
        assert "provider_warnings" in results

        # Check that we have warnings/errors in each category
        assert len(results["environment_warnings"]) > 0
        assert len(results["aws_errors"]) > 0
        assert len(results["provider_warnings"]) > 0

        # Verify specific issues are caught
        env_warnings = results["environment_warnings"]
        assert any("Debug mode is enabled in production" in warning for warning in env_warnings)
        assert any("Using mock database in production" in warning for warning in env_warnings)

        aws_errors = results["aws_errors"]
        assert any("SQS requires region configuration" in error for error in aws_errors)

        provider_warnings = results["provider_warnings"]
        assert any("Provider 'byteme' is disabled in production" in warning for warning in provider_warnings)
        assert any("Missing provider configurations" in warning for warning in provider_warnings)

    def test_get_all_validation_results_clean_config(self):
        """Test getting all validation results for a clean configuration."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE, level="INFO"),
            provider_configs={
                "byteme": ProviderConfig(name="byteme", enabled=True, timeout_seconds=30, retry_attempts=3),
                "verbyndich": ProviderConfig(name="verbyndich", enabled=True, timeout_seconds=30, retry_attempts=3),
                "webwunder": ProviderConfig(name="webwunder", enabled=True, timeout_seconds=30, retry_attempts=3),
                "pingperfect": ProviderConfig(name="pingperfect", enabled=True, timeout_seconds=30, retry_attempts=3),
            },
            debug=True,
        )

        results = ConfigValidator.get_all_validation_results(config)

        # Should have no warnings or errors for a properly configured development environment
        assert len(results["environment_warnings"]) == 0
        assert len(results["aws_errors"]) == 0
        assert len(results["provider_warnings"]) == 0

    def test_validate_aws_configuration_mixed_providers(self):
        """Test AWS configuration validation with mixed AWS and non-AWS providers."""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),  # Non-AWS
            messaging=MessagingConfig(provider=MessagingProvider.AWS_SQS, region="us-east-1"),  # AWS
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),  # Non-AWS
        )

        errors = ConfigValidator.validate_aws_configuration(config)

        # Should only validate AWS services
        assert len(errors) == 0  # SQS has region, so no errors

    def test_validate_provider_configuration_edge_cases(self):
        """Test provider configuration validation edge cases."""
        config = AppConfig(
            environment=Environment.STAGING,  # Not production, so no disabled provider warnings
            database=DatabaseConfig(provider=DatabaseProvider.MOCK),
            messaging=MessagingConfig(provider=MessagingProvider.MOCK),
            logging=LoggingConfig(provider=LoggingProvider.CONSOLE),
            provider_configs={
                "edge_case_1": ProviderConfig(
                    name="edge_case_1",
                    enabled=False,  # Disabled but not in production
                    timeout_seconds=60,  # Exactly at boundary
                    retry_attempts=5,  # Exactly at boundary
                ),
                "edge_case_2": ProviderConfig(
                    name="edge_case_2",
                    enabled=True,
                    timeout_seconds=61,  # Just over boundary
                    retry_attempts=6,  # Just over boundary
                ),
            },
        )

        warnings = ConfigValidator.validate_provider_configuration(config)

        # Should not warn about disabled provider in non-production
        assert not any("edge_case_1" in warning and "disabled" in warning for warning in warnings)

        # Should warn about high values
        assert any("edge_case_2" in warning and "high timeout" in warning for warning in warnings)
        assert any("edge_case_2" in warning and "high retry attempts" in warning for warning in warnings)

        # Should still warn about missing required providers
        assert any("Missing provider configurations" in warning for warning in warnings)
