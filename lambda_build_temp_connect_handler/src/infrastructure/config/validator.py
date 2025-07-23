"""Configuration validation utilities."""

from typing import List, Dict, Any, Optional
from .models import AppConfig, Environment, DatabaseProvider, MessagingProvider, LoggingProvider


class ConfigValidator:
    """Validates configuration settings and provides recommendations."""
    
    @staticmethod
    def validate_environment_consistency(config: AppConfig) -> List[str]:
        """Validate that configuration is consistent with the environment."""
        warnings = []
        
        if config.environment == Environment.PRODUCTION:
            # Production warnings
            if config.debug:
                warnings.append("Debug mode is enabled in production")
            
            if config.database.provider == DatabaseProvider.MOCK:
                warnings.append("Using mock database in production")
            
            if config.messaging.provider == MessagingProvider.MOCK:
                warnings.append("Using mock messaging in production")
            
            if config.logging.provider == LoggingProvider.CONSOLE:
                warnings.append("Using console logging in production")
            
            if config.logging.level == "DEBUG":
                warnings.append("Debug logging enabled in production")
        
        elif config.environment == Environment.DEVELOPMENT:
            # Development recommendations
            if not config.debug:
                warnings.append("Debug mode is disabled in development")
            
            if config.database.provider != DatabaseProvider.MOCK:
                warnings.append("Consider using mock database in development")
            
            if config.messaging.provider != MessagingProvider.MOCK:
                warnings.append("Consider using mock messaging in development")
        
        elif config.environment == Environment.TESTING:
            # Testing requirements
            if config.database.provider != DatabaseProvider.MOCK:
                warnings.append("Tests should use mock database")
            
            if config.messaging.provider != MessagingProvider.MOCK:
                warnings.append("Tests should use mock messaging")
            
            if config.logging.provider != LoggingProvider.CONSOLE:
                warnings.append("Tests should use console logging")
        
        return warnings
    
    @staticmethod
    def validate_aws_configuration(config: AppConfig) -> List[str]:
        """Validate AWS-specific configuration."""
        errors = []
        
        aws_services = []
        
        if config.database.provider == DatabaseProvider.AWS_DYNAMODB:
            aws_services.append("DynamoDB")
            if not config.database.region:
                errors.append("DynamoDB requires region configuration")
        
        if config.messaging.provider == MessagingProvider.AWS_SQS:
            aws_services.append("SQS")
            if not config.messaging.region:
                errors.append("SQS requires region configuration")
        
        if config.logging.provider == LoggingProvider.AWS_CLOUDWATCH:
            aws_services.append("CloudWatch")
            if not config.logging.region:
                errors.append("CloudWatch requires region configuration")
            if not config.logging.log_group:
                errors.append("CloudWatch requires log group configuration")
        
        # Check for region consistency
        regions = set()
        if config.database.region:
            regions.add(config.database.region)
        if config.messaging.region:
            regions.add(config.messaging.region)
        if config.logging.region:
            regions.add(config.logging.region)
        
        if len(regions) > 1:
            errors.append(f"Multiple AWS regions configured: {regions}. Consider using the same region for all services.")
        
        return errors
    
    @staticmethod
    def validate_provider_configuration(config: AppConfig) -> List[str]:
        """Validate external provider configuration."""
        warnings = []
        
        required_providers = ["byteme", "verbyndich", "webwunder", "pingperfect"]
        configured_providers = set(config.provider_configs.keys())
        
        missing_providers = set(required_providers) - configured_providers
        if missing_providers:
            warnings.append(f"Missing provider configurations: {missing_providers}")
        
        for name, provider_config in config.provider_configs.items():
            if not provider_config.enabled and config.environment == Environment.PRODUCTION:
                warnings.append(f"Provider '{name}' is disabled in production")
            
            if provider_config.timeout_seconds > 60:
                warnings.append(f"Provider '{name}' has high timeout ({provider_config.timeout_seconds}s)")
            
            if provider_config.retry_attempts > 5:
                warnings.append(f"Provider '{name}' has high retry attempts ({provider_config.retry_attempts})")
        
        return warnings
    
    @staticmethod
    def get_all_validation_results(config: AppConfig) -> Dict[str, List[str]]:
        """Get all validation results for a configuration."""
        return {
            "environment_warnings": ConfigValidator.validate_environment_consistency(config),
            "aws_errors": ConfigValidator.validate_aws_configuration(config),
            "provider_warnings": ConfigValidator.validate_provider_configuration(config)
        }