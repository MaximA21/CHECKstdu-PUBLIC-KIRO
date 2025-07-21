# Configuration Management Guide

This guide explains how to configure the application for different environments and deployment scenarios.

## Overview

The application uses a hierarchical configuration system that supports:
- Environment-specific configuration files
- Environment variable overrides
- Automatic service selection based on environment
- Configuration validation and error handling

## Configuration Structure

### Configuration Files

Configuration files are located in the `config/` directory:

```
config/
├── default.json      # Base configuration
├── development.json  # Development environment
├── testing.json      # Testing environment
├── staging.json      # Staging environment
└── production.json   # Production environment
```

### Environment Selection

The environment is determined by the `APP_ENVIRONMENT` environment variable:

```bash
export APP_ENVIRONMENT=production
```

Supported environments:
- `development` (default)
- `testing`
- `staging`
- `production`

## Configuration Sections

### Database Configuration

```json
{
  "database": {
    "provider": "aws_dynamodb",
    "region": "eu-central-1",
    "table_prefix": "prod_",
    "timeout_seconds": 30
  }
}
```

**Providers:**
- `aws_dynamodb` - AWS DynamoDB
- `azure_cosmos` - Azure Cosmos DB (future)
- `mock` - In-memory mock (testing only)

**Environment Variables:**
- `DB_PROVIDER` - Override database provider
- `DB_REGION` - Override database region
- `DB_TABLE_PREFIX` - Override table prefix

### Messaging Configuration

```json
{
  "messaging": {
    "provider": "aws_sqs",
    "region": "eu-central-1",
    "queue_prefix": "prod_",
    "timeout_seconds": 30
  }
}
```

**Providers:**
- `aws_sqs` - AWS SQS + Step Functions
- `azure_servicebus` - Azure Service Bus (future)
- `mock` - In-memory mock (testing only)

**Environment Variables:**
- `MSG_PROVIDER` - Override messaging provider
- `MSG_REGION` - Override messaging region
- `MSG_QUEUE_PREFIX` - Override queue prefix

### Logging Configuration

```json
{
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "INFO",
    "structured": true,
    "log_group": "/aws/lambda/webwunder-prod",
    "region": "eu-central-1"
  }
}
```

**Providers:**
- `aws_cloudwatch` - AWS CloudWatch Logs
- `azure_monitor` - Azure Monitor (future)
- `console` - Console output

**Log Levels:**
- `DEBUG` - Detailed debugging information
- `INFO` - General information
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical errors

**Environment Variables:**
- `LOG_PROVIDER` - Override logging provider
- `LOG_LEVEL` - Override log level
- `LOG_GROUP` - Override CloudWatch log group

### Provider Configuration

```json
{
  "providers": {
    "byteme": {
      "enabled": true,
      "timeout_seconds": 30,
      "retry_attempts": 3,
      "config": {
        "base_url": "https://api.byteme.com"
      }
    }
  }
}
```

**Common Settings:**
- `enabled` - Enable/disable provider
- `timeout_seconds` - Request timeout
- `retry_attempts` - Number of retry attempts
- `config` - Provider-specific configuration

### Container Configuration

```json
{
  "container": {
    "http_port": 8080,
    "websocket_port": 8081,
    "cors_enabled": true,
    "request_timeout_seconds": 30,
    "max_connections": 1000,
    "health_check_interval": 30
  }
}
```

## Environment-Specific Configurations

### Development Environment

**Characteristics:**
- Uses mock services for fast development
- Debug mode enabled
- Console logging
- Reduced timeouts for faster feedback

**Configuration:**
```json
{
  "database": {"provider": "mock"},
  "messaging": {"provider": "mock"},
  "logging": {"provider": "console", "level": "DEBUG"},
  "debug": true
}
```

### Testing Environment

**Characteristics:**
- All services use mocks
- Fast timeouts
- Minimal logging
- Providers disabled

**Configuration:**
```json
{
  "database": {"provider": "mock"},
  "messaging": {"provider": "mock"},
  "logging": {"provider": "console", "level": "DEBUG", "structured": false},
  "providers": {"byteme": {"enabled": false}}
}
```

### Staging Environment

**Characteristics:**
- Uses real AWS services
- Debug logging enabled
- Staging API endpoints
- Production-like configuration

**Configuration:**
```json
{
  "database": {"provider": "aws_dynamodb", "region": "eu-central-1"},
  "messaging": {"provider": "aws_sqs", "region": "eu-central-1"},
  "logging": {"provider": "aws_cloudwatch", "level": "DEBUG"},
  "debug": true
}
```

### Production Environment

**Characteristics:**
- Real AWS services
- Optimized for performance
- Structured logging
- All providers enabled

**Configuration:**
```json
{
  "database": {"provider": "aws_dynamodb", "region": "eu-central-1"},
  "messaging": {"provider": "aws_sqs", "region": "eu-central-1"},
  "logging": {"provider": "aws_cloudwatch", "level": "INFO"},
  "debug": false
}
```

## Configuration Validation

The system performs automatic validation:

### Basic Validation
- Required fields are present
- Provider types are valid
- Numeric values are within acceptable ranges
- Log levels are valid

### Environment-Specific Validation
- Production environments should not use mock services
- AWS services require region configuration
- Testing environments should use mocks

### Runtime Validation
- Port conflicts are detected
- Timeout values are positive
- Provider configurations are complete

## Service Selection

Services are automatically selected based on configuration:

```python
from src.infrastructure.config.service_selector import ServiceSelector

selector = ServiceSelector(config)

# Automatically selects AWS or mock implementation
repository = selector.get_search_result_repository()
message_queue = selector.get_message_queue()
logger_factory = selector.get_logger_factory()
```

## Error Handling

### Configuration Errors

**ConfigurationError**: General configuration loading errors
```python
try:
    config = loader.load_config()
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

**ConfigurationValidationError**: Validation-specific errors
```python
try:
    config = loader.load_config()
except ConfigurationValidationError as e:
    print(f"Validation failed: {e}")
    for error in e.errors:
        print(f"  - {error}")
```

### Fallback Behavior

When configuration files are missing:
1. Falls back to `default.json`
2. If no config files exist, uses minimal defaults
3. Environment variables can override any setting

## Best Practices

### Development
- Use mock services for faster development
- Enable debug mode and detailed logging
- Use shorter timeouts for quick feedback

### Testing
- Always use mock services
- Disable external providers
- Use minimal logging to reduce noise

### Staging
- Mirror production configuration
- Enable debug logging for troubleshooting
- Use staging API endpoints

### Production
- Use real cloud services
- Disable debug mode
- Use structured logging
- Monitor configuration warnings

## Troubleshooting

### Common Issues

**Missing Region Configuration**
```
Error: AWS DynamoDB requires region configuration
Solution: Add "region": "eu-central-1" to database config
```

**Port Conflicts**
```
Error: HTTP and WebSocket ports cannot be the same
Solution: Use different ports (e.g., 8080 and 8081)
```

**Invalid Provider**
```
Error: Invalid database provider: invalid_provider
Solution: Use one of: aws_dynamodb, azure_cosmos, mock
```

### Validation Warnings

Use the configuration validator to check for issues:

```python
from src.infrastructure.config.validator import ConfigValidator

warnings = ConfigValidator.validate_environment_consistency(config)
for warning in warnings:
    print(f"Warning: {warning}")
```

### Environment Variables

Override any configuration with environment variables:

```bash
# Override database provider
export DB_PROVIDER=mock

# Override log level
export LOG_LEVEL=DEBUG

# Enable debug mode
export DEBUG=true
```

## Migration Guide

### From Old Configuration

If migrating from the old configuration system:

1. Move service configurations to appropriate sections
2. Update provider names to use enum values
3. Add environment-specific files
4. Update import paths to use new config loader

### Adding New Environments

1. Create new JSON file in `config/` directory
2. Add environment to `Environment` enum
3. Update validation rules if needed
4. Test configuration loading and validation

## Security Considerations

- Never commit sensitive data to configuration files
- Use environment variables for secrets
- Validate all configuration inputs
- Use different prefixes for different environments
- Monitor configuration changes in production