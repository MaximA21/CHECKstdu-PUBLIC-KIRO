# Dependency Injection System

This module provides a comprehensive dependency injection container and configuration system for the enterprise refactoring project.

## Features

- **Service Registration**: Register services with different lifetimes (singleton, transient, scoped)
- **Automatic Dependency Resolution**: Automatically resolve constructor dependencies
- **Environment-Aware Configuration**: Load configuration based on environment variables and files
- **Service Factories**: Environment-specific service implementations (AWS, Mock, Container)
- **Thread-Safe**: Safe for concurrent access in multi-threaded environments

## Quick Start

```python
from src.shared.dependency_injection import initialize_application, get_container, get_config

# Initialize the application
container = initialize_application()

# Get configuration
config = get_config()
print(f"Environment: {config.environment.value}")

# Resolve services
service = container.resolve(IMyService)
```

## Configuration

### Environment Variables

The system supports the following environment variables:

- `APP_ENVIRONMENT`: Application environment (development, testing, staging, production)
- `DB_PROVIDER`: Database provider (aws_dynamodb, mock)
- `DB_REGION`: Database region
- `DB_TABLE_PREFIX`: Database table prefix
- `MSG_PROVIDER`: Messaging provider (aws_sqs, mock)
- `MSG_REGION`: Messaging region
- `LOG_PROVIDER`: Logging provider (aws_cloudwatch, console)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `DEBUG`: Debug mode (true/false)

### Configuration Files

Configuration files are loaded from the `config/` directory:

- `config/default.json`: Default configuration
- `config/development.json`: Development environment
- `config/testing.json`: Testing environment
- `config/staging.json`: Staging environment
- `config/production.json`: Production environment

Example configuration:

```json
{
  "database": {
    "provider": "aws_dynamodb",
    "region": "eu-central-1",
    "table_prefix": "prod_"
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "eu-central-1",
    "queue_prefix": "prod_"
  },
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "INFO",
    "structured": true
  }
}
```

## Service Registration

### Basic Registration

```python
from src.shared.dependency_injection import DIContainer, ServiceLifetime

container = DIContainer()

# Register transient service (new instance each time)
container.register(IMyService, MyServiceImpl)

# Register singleton service (same instance each time)
container.register_singleton(IMyService, MyServiceImpl)

# Register specific instance
instance = MyServiceImpl()
container.register_instance(IMyService, instance)
```

### Automatic Dependency Injection

The container automatically resolves constructor dependencies:

```python
class MyService:
    def __init__(self, repository: IRepository, logger: ILogger):
        self.repository = repository
        self.logger = logger

# Register dependencies
container.register(IRepository, RepositoryImpl)
container.register(ILogger, LoggerImpl)
container.register(MyService, MyService)

# Resolve with automatic dependency injection
service = container.resolve(MyService)
```

## Service Factories

Service factories provide environment-specific implementations:

```python
from src.shared.dependency_injection.factory import ServiceFactoryProvider

# Get appropriate factory for configuration
factory = ServiceFactoryProvider.get_factory(config)

# Create configured container
container = factory.create_container(config)
```

### Available Factories

- **AWSServiceFactory**: AWS-based implementations (DynamoDB, SQS, CloudWatch)
- **MockServiceFactory**: Mock implementations for testing
- **ContainerServiceFactory**: Container-based deployments

## Error Handling

The system provides specific exceptions for different error scenarios:

```python
from src.shared.dependency_injection import (
    ServiceNotRegisteredException,
    ServiceResolutionException
)

try:
    service = container.resolve(IMyService)
except ServiceNotRegisteredException:
    print("Service not registered")
except ServiceResolutionException:
    print("Failed to resolve service")
```

## Thread Safety

The DI container is thread-safe and can be used in multi-threaded environments:

- Service registration is protected by locks
- Singleton creation uses double-checked locking
- Container state is safely managed across threads

## Testing

The system includes comprehensive test coverage:

```bash
python3 -m pytest tests/test_dependency_injection.py -v
```

## Examples

See `examples/di_usage_example.py` for a complete usage example.

## Architecture

The dependency injection system follows these principles:

1. **Inversion of Control**: Dependencies are injected rather than created
2. **Dependency Inversion**: Depend on abstractions, not concretions
3. **Single Responsibility**: Each component has a single, well-defined purpose
4. **Open/Closed**: Open for extension, closed for modification

This enables:

- **Testability**: Easy to mock dependencies for testing
- **Flexibility**: Easy to swap implementations
- **Maintainability**: Clear separation of concerns
- **Scalability**: Support for different deployment patterns