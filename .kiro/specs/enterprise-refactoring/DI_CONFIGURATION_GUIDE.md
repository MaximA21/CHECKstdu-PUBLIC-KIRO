# Dependency Injection Configuration Guide

This guide covers the configuration and usage of the dependency injection system in the enterprise architecture, including environment-specific configurations and service registration patterns.

## Overview

The dependency injection (DI) system provides:
- **Service Lifecycle Management**: Singleton, transient, and scoped service lifetimes
- **Environment-Aware Configuration**: Automatic service selection based on environment
- **Interface-Based Design**: Loose coupling through interface abstractions
- **Configuration-Driven Setup**: JSON-based service configuration

## DI Container Architecture

### Core Components

```
src/shared/dependency_injection/
├── container.py          # Main DI container implementation
├── factory.py           # Service factory patterns
├── bootstrap.py         # Container initialization and configuration
└── README.md           # DI system documentation
```

### Container Lifecycle

```python
# Container initialization flow
1. Load configuration from environment-specific JSON files
2. Register services based on configuration
3. Resolve dependencies and create service instances
4. Manage service lifetimes (singleton, transient, scoped)
5. Provide services to application components
```

## Configuration Structure

### Environment Configuration Files

```
config/
├── default.json         # Base configuration
├── development.json     # Development overrides
├── staging.json         # Staging overrides
├── production.json      # Production overrides
├── testing.json         # Testing overrides
└── container.json       # Container-specific overrides
```

### Configuration Schema

```json
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "prod_",
    "connection_timeout": 30,
    "retry_attempts": 3
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "us-east-1",
    "queue_prefix": "prod_",
    "visibility_timeout": 300,
    "max_receive_count": 3
  },
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "INFO",
    "structured": true,
    "log_group_prefix": "/aws/lambda/prod"
  },
  "external_services": {
    "byteme": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3
    },
    "verbyndich": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3
    },
    "webwunder": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3
    },
    "ping_perfect": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3
    }
  },
  "di_container": {
    "enable_caching": true,
    "preload_services": [
      "ISearchResultRepository",
      "ILogger",
      "IProviderService"
    ],
    "service_lifetimes": {
      "ISearchResultRepository": "singleton",
      "IConnectionRepository": "singleton",
      "IMessageQueue": "singleton",
      "ILogger": "singleton",
      "IProviderService": "transient"
    }
  }
}
```

## Service Registration

### Interface-Implementation Mapping

The DI container automatically registers services based on configuration:

```python
# src/shared/dependency_injection/container.py
class DIContainer:
    def _register_services_by_environment(self):
        """Register services based on environment configuration"""
        
        # Database services
        if self.config.database.provider == "aws_dynamodb":
            self.register_singleton(ISearchResultRepository, DynamoDBSearchResultRepository)
            self.register_singleton(IConnectionRepository, DynamoDBConnectionRepository)
        elif self.config.database.provider == "mock":
            self.register_singleton(ISearchResultRepository, MockSearchResultRepository)
            self.register_singleton(IConnectionRepository, MockConnectionRepository)
        
        # Messaging services
        if self.config.messaging.provider == "aws_sqs":
            self.register_singleton(IMessageQueue, AWSSQSAdapter)
            self.register_singleton(IWorkflowOrchestrator, AWSStepFunctionsAdapter)
        elif self.config.messaging.provider == "mock":
            self.register_singleton(IMessageQueue, MockMessageQueue)
            self.register_singleton(IWorkflowOrchestrator, MockWorkflowOrchestrator)
        
        # Logging services
        if self.config.logging.provider == "aws_cloudwatch":
            self.register_singleton(ILoggerFactory, CloudWatchLoggerFactory)
        elif self.config.logging.provider == "console":
            self.register_singleton(ILoggerFactory, ConsoleLoggerFactory)
        
        # External provider services
        self._register_provider_services()
```

### Custom Service Registration

```python
# Custom service registration in application code
from src.shared.dependency_injection.bootstrap import bootstrap_container

def configure_custom_services():
    container = bootstrap_container()
    
    # Register custom implementations
    container.register_singleton(ICustomService, CustomServiceImpl)
    
    # Register with factory function
    container.register_factory(IComplexService, lambda: ComplexService(
        dependency1=container.get(IDependency1),
        dependency2=container.get(IDependency2)
    ))
    
    # Register with configuration
    container.register_configured(IConfigurableService, ConfigurableService, {
        'setting1': 'value1',
        'setting2': 'value2'
    })
    
    return container
```

## Environment-Specific Configurations

### Development Environment

```json
{
  "environment": "development",
  "database": {
    "provider": "mock",
    "connection_string": null
  },
  "messaging": {
    "provider": "mock",
    "connection_string": null
  },
  "logging": {
    "provider": "console",
    "level": "DEBUG",
    "structured": false
  },
  "external_services": {
    "byteme": {"enabled": false},
    "verbyndich": {"enabled": false},
    "webwunder": {"enabled": false},
    "ping_perfect": {"enabled": false}
  },
  "di_container": {
    "enable_caching": false,
    "preload_services": [],
    "service_lifetimes": {
      "IProviderService": "transient"
    }
  }
}
```

### Testing Environment

```json
{
  "environment": "testing",
  "database": {
    "provider": "mock",
    "connection_string": null,
    "enable_cleanup": true
  },
  "messaging": {
    "provider": "mock",
    "connection_string": null,
    "enable_cleanup": true
  },
  "logging": {
    "provider": "console",
    "level": "ERROR",
    "structured": true
  },
  "external_services": {
    "byteme": {"enabled": true, "mock_responses": true},
    "verbyndich": {"enabled": true, "mock_responses": true},
    "webwunder": {"enabled": true, "mock_responses": true},
    "ping_perfect": {"enabled": true, "mock_responses": true}
  },
  "di_container": {
    "enable_caching": false,
    "preload_services": [],
    "service_lifetimes": {
      "IProviderService": "transient"
    }
  }
}
```

### Production Environment

```json
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "prod_",
    "connection_timeout": 30,
    "retry_attempts": 3,
    "enable_point_in_time_recovery": true
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "us-east-1",
    "queue_prefix": "prod_",
    "visibility_timeout": 300,
    "max_receive_count": 3,
    "enable_dead_letter_queue": true
  },
  "logging": {
    "provider": "aws_cloudwatch",
    "level": "INFO",
    "structured": true,
    "log_group_prefix": "/aws/lambda/prod",
    "retention_days": 30
  },
  "external_services": {
    "byteme": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3,
      "circuit_breaker": {
        "failure_threshold": 5,
        "recovery_timeout": 60
      }
    },
    "verbyndich": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3,
      "circuit_breaker": {
        "failure_threshold": 5,
        "recovery_timeout": 60
      }
    }
  },
  "di_container": {
    "enable_caching": true,
    "preload_services": [
      "ISearchResultRepository",
      "IConnectionRepository",
      "ILogger",
      "IMessageQueue"
    ],
    "service_lifetimes": {
      "ISearchResultRepository": "singleton",
      "IConnectionRepository": "singleton",
      "IMessageQueue": "singleton",
      "IWorkflowOrchestrator": "singleton",
      "ILogger": "singleton",
      "IProviderService": "transient"
    },
    "performance": {
      "enable_metrics": true,
      "track_resolution_time": true,
      "cache_resolution_results": true
    }
  }
}
```

## Service Lifetimes

### Singleton Services

Services created once and reused throughout the application lifecycle:

```python
# Singleton registration
container.register_singleton(ISearchResultRepository, DynamoDBSearchResultRepository)

# Usage - same instance returned every time
repo1 = container.get(ISearchResultRepository)
repo2 = container.get(ISearchResultRepository)
assert repo1 is repo2  # True
```

**Best for**: Database connections, loggers, configuration services, caches

### Transient Services

New instance created for each request:

```python
# Transient registration
container.register_transient(IProviderService, ByteMeProviderService)

# Usage - new instance each time
provider1 = container.get(IProviderService)
provider2 = container.get(IProviderService)
assert provider1 is not provider2  # True
```

**Best for**: Use cases, domain services, stateful operations

### Scoped Services

Services with request-specific lifetime (for web applications):

```python
# Scoped registration (for HTTP requests)
container.register_scoped(IRequestContext, RequestContext)

# Usage within request scope
with container.create_scope() as scope:
    context1 = scope.get(IRequestContext)
    context2 = scope.get(IRequestContext)
    assert context1 is context2  # True within scope
```

**Best for**: Request-specific data, user context, transaction scopes

## Usage Patterns

### Lambda Handler Usage

```python
# src/presentation/lambda_handlers/search_handler.py
from src.shared.dependency_injection.bootstrap import bootstrap_container
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase

# Global container for Lambda reuse
_container = None

def lambda_handler(event, context):
    global _container
    
    # Initialize container once per Lambda instance
    if _container is None:
        _container = bootstrap_container()
    
    # Get services from container
    use_case = _container.get(SearchOffersUseCase)
    logger = _container.get(ILogger)
    
    try:
        result = await use_case.execute(event)
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
```

### HTTP Server Usage

```python
# src/presentation/http_server.py
from fastapi import FastAPI, Depends
from src.shared.dependency_injection.bootstrap import bootstrap_container

app = FastAPI()
container = bootstrap_container()

def get_search_use_case():
    return container.get(SearchOffersUseCase)

@app.post("/search")
async def search_offers(
    request: SearchRequest,
    use_case: SearchOffersUseCase = Depends(get_search_use_case)
):
    return await use_case.execute(request)
```

### Use Case Usage

```python
# src/application/use_cases/search_offers_use_case.py
from src.application.interfaces.repositories import ISearchResultRepository
from src.application.interfaces.providers import IProviderService
from src.application.interfaces.logging import ILogger

class SearchOffersUseCase:
    def __init__(
        self,
        result_repository: ISearchResultRepository,
        provider_services: List[IProviderService],
        logger: ILogger
    ):
        self._result_repository = result_repository
        self._provider_services = provider_services
        self._logger = logger
    
    async def execute(self, request: SearchRequest) -> SearchResult:
        self._logger.info("Starting search", {"address": request.address})
        
        # Use injected dependencies
        offers = []
        for provider in self._provider_services:
            try:
                provider_offers = await provider.get_offers(request.address)
                offers.extend(provider_offers)
            except Exception as e:
                self._logger.error(f"Provider {provider.provider_name} failed", {"error": str(e)})
        
        result = SearchResult(
            request_id=request.request_id,
            address=request.address,
            offers=offers
        )
        
        await self._result_repository.save_result(result)
        return result
```

## Advanced Configuration

### Conditional Service Registration

```python
# Register services based on feature flags
if self.config.features.enable_caching:
    container.register_singleton(ICacheService, RedisCacheService)
else:
    container.register_singleton(ICacheService, InMemoryCacheService)

# Register services based on environment
if self.config.environment == "production":
    container.register_singleton(IMetricsService, CloudWatchMetricsService)
elif self.config.environment == "development":
    container.register_singleton(IMetricsService, ConsoleMetricsService)
```

### Service Decorators

```python
# Add cross-cutting concerns through decorators
from src.shared.middleware.retry_handler import with_retry
from src.shared.middleware.circuit_breaker import with_circuit_breaker

# Decorate services with middleware
container.register_singleton(
    IProviderService,
    with_circuit_breaker(
        with_retry(ByteMeProviderService, max_attempts=3),
        failure_threshold=5
    )
)
```

### Configuration Validation

```python
# src/shared/dependency_injection/validation.py
from pydantic import BaseModel, validator

class DatabaseConfig(BaseModel):
    provider: str
    region: str = None
    table_prefix: str = ""
    
    @validator('provider')
    def validate_provider(cls, v):
        allowed = ['aws_dynamodb', 'azure_cosmos', 'mock']
        if v not in allowed:
            raise ValueError(f'Provider must be one of {allowed}')
        return v

class DIConfig(BaseModel):
    database: DatabaseConfig
    messaging: MessagingConfig
    logging: LoggingConfig
    
    def validate(self):
        """Validate configuration consistency"""
        if self.database.provider == "aws_dynamodb" and not self.database.region:
            raise ValueError("AWS DynamoDB requires region configuration")
```

## Performance Optimization

### Container Caching

```json
{
  "di_container": {
    "enable_caching": true,
    "cache_settings": {
      "max_cache_size": 1000,
      "cache_ttl_seconds": 3600,
      "enable_cache_metrics": true
    }
  }
}
```

### Service Preloading

```json
{
  "di_container": {
    "preload_services": [
      "ISearchResultRepository",
      "ILogger",
      "IProviderService"
    ],
    "preload_on_startup": true,
    "preload_timeout_seconds": 30
  }
}
```

### Lazy Loading

```python
# Lazy service registration
container.register_lazy(IExpensiveService, lambda: ExpensiveService())

# Service only created when first requested
service = container.get(IExpensiveService)  # Created here
```

## Monitoring and Debugging

### DI Container Metrics

```python
# Enable container metrics
container.enable_metrics()

# Get container statistics
stats = container.get_statistics()
print(f"Services registered: {stats.services_registered}")
print(f"Services resolved: {stats.services_resolved}")
print(f"Average resolution time: {stats.avg_resolution_time_ms}ms")
```

### Debug Mode

```json
{
  "di_container": {
    "debug_mode": true,
    "log_service_resolution": true,
    "validate_dependencies": true,
    "track_service_lifecycle": true
  }
}
```

### Service Health Checks

```python
# Health check for DI container
@app.get("/health/di")
async def di_health_check():
    container = bootstrap_container()
    
    health_status = {
        "container_initialized": container.is_initialized(),
        "services_healthy": await container.check_service_health(),
        "configuration_valid": container.validate_configuration()
    }
    
    return health_status
```

## Troubleshooting

### Common Issues

1. **Circular Dependencies**
   ```python
   # Problem: Service A depends on Service B, Service B depends on Service A
   # Solution: Use factory pattern or interface segregation
   ```

2. **Missing Dependencies**
   ```python
   # Problem: Service not registered in container
   # Solution: Check configuration and registration order
   ```

3. **Configuration Errors**
   ```python
   # Problem: Invalid configuration values
   # Solution: Use configuration validation
   ```

4. **Performance Issues**
   ```python
   # Problem: Slow service resolution
   # Solution: Enable caching and preloading
   ```

### Debug Commands

```bash
# Validate DI configuration
python -m src.shared.dependency_injection.validate_config

# Test service resolution
python -m src.shared.dependency_injection.test_resolution

# Generate dependency graph
python -m src.shared.dependency_injection.generate_graph
```

## Best Practices

### Configuration Management
- Use environment-specific configuration files
- Validate configuration on startup
- Use type-safe configuration models
- Document configuration options

### Service Design
- Design services with single responsibility
- Use interfaces for all external dependencies
- Avoid circular dependencies
- Keep service constructors simple

### Performance
- Use singleton lifetime for expensive services
- Enable caching for frequently used services
- Preload critical services
- Monitor resolution performance

### Testing
- Use mock implementations for testing
- Create test-specific DI configurations
- Test service registration and resolution
- Validate service behavior in isolation

The dependency injection system provides a robust foundation for managing service dependencies across different environments and deployment patterns, enabling clean architecture principles and testable code.