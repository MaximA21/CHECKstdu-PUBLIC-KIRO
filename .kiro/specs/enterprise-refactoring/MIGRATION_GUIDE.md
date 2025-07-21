# Migration Guide: From Legacy to Enterprise Architecture

This guide provides step-by-step instructions for migrating from the legacy Lambda-based architecture to the new enterprise architecture with dependency injection and clean architecture principles.

## Overview

The migration transforms the application from:
- **Legacy**: Direct AWS service dependencies, flat folder structure, hardcoded service instantiation
- **Enterprise**: Dependency injection, clean architecture layers, cloud-agnostic interfaces

## Pre-Migration Assessment

### Current Architecture Analysis

Before starting migration, assess your current setup:

```bash
# Check current Lambda functions
ls lambda_functions/
# Expected: address_normalizer, authorizer, connect_handler, etc.

# Check services folder structure
ls services/
# Expected: aws_storage.py, mock_storage.py, logging_config.py

# Check direct AWS dependencies
grep -r "boto3" lambda_functions/
grep -r "import boto3" src/
```

### Backup Current System

```bash
# Create backup branch
git checkout -b backup-legacy-architecture
git add .
git commit -m "Backup legacy architecture before migration"

# Create migration branch
git checkout -b enterprise-migration
```

## Migration Strategy

### Phase 1: Foundation Setup (Low Risk)
- Set up new folder structure alongside existing code
- Implement dependency injection container
- Create configuration management system

### Phase 2: Interface Implementation (Medium Risk)
- Implement new interfaces and adapters
- Create mock implementations for testing
- Set up comprehensive test suite

### Phase 3: Gradual Function Migration (High Risk)
- Migrate Lambda functions one by one
- Maintain backward compatibility during transition
- Implement rollback procedures

### Phase 4: Cleanup and Optimization (Low Risk)
- Remove legacy code
- Optimize performance
- Update documentation

## Step-by-Step Migration

### Step 1: Set Up New Architecture Foundation

#### 1.1 Create New Folder Structure

```bash
# Create new directory structure
mkdir -p src/domain/{entities,value_objects,services}
mkdir -p src/application/{use_cases,interfaces,dto}
mkdir -p src/infrastructure/{persistence,messaging,external_services,logging,config}
mkdir -p src/presentation/{lambda_handlers,http_controllers,websocket_handlers}
mkdir -p src/shared/{dependency_injection,exceptions,middleware,monitoring}
```

#### 1.2 Initialize Core Files

```bash
# Create __init__.py files
find src/ -type d -exec touch {}/__init__.py \;

# Copy existing domain logic
cp services/aws_storage.py src/infrastructure/persistence/legacy_aws_storage.py
cp services/mock_storage.py src/infrastructure/persistence/legacy_mock_storage.py
cp services/logging_config.py src/infrastructure/logging/legacy_logging_config.py
```

#### 1.3 Set Up Configuration System

```bash
# Create configuration files
cp config/default.json config/migration.json
# Edit migration.json to include new architecture settings
```

### Step 2: Implement Core Interfaces

#### 2.1 Create Application Interfaces

The new interfaces are already implemented in:
- `src/application/interfaces/repositories.py`
- `src/application/interfaces/messaging.py`
- `src/application/interfaces/connections.py`
- `src/application/interfaces/providers.py`
- `src/application/interfaces/logging.py`

#### 2.2 Implement Infrastructure Adapters

The adapters are already implemented in:
- `src/infrastructure/persistence/aws_dynamodb_repository.py`
- `src/infrastructure/messaging/aws_sqs_adapter.py`
- `src/infrastructure/messaging/aws_websocket_adapter.py`
- `src/infrastructure/external_services/`

### Step 3: Set Up Dependency Injection

#### 3.1 Configure DI Container

The DI container is implemented in `src/shared/dependency_injection/container.py`. Configure it for migration:

```python
# src/shared/dependency_injection/migration_container.py
from .container import DIContainer
from src.infrastructure.persistence.legacy_aws_storage import LegacyAWSStorage
from src.infrastructure.persistence.aws_dynamodb_repository import DynamoDBSearchResultRepository

class MigrationDIContainer(DIContainer):
    def _configure_services(self):
        # Use legacy services initially
        if self.config.migration_mode:
            self._register_legacy_services()
        else:
            self._register_new_services()
    
    def _register_legacy_services(self):
        # Register legacy implementations
        self.register_singleton(IStorageService, LegacyAWSStorage)
        
    def _register_new_services(self):
        # Register new implementations
        self.register_singleton(ISearchResultRepository, DynamoDBSearchResultRepository)
```

### Step 4: Migrate Lambda Functions

#### 4.1 Migration Order

Migrate functions in this order to minimize risk:

1. **Low Risk**: `address_normalizer` (simple, isolated)
2. **Medium Risk**: `authorizer` (authentication, but stateless)
3. **Medium Risk**: `connect_handler`, `disconnect_handler` (connection management)
4. **High Risk**: `search_handler` (core business logic)
5. **High Risk**: `results_handler` (complex provider integration)
6. **High Risk**: `share_api` (data persistence)
7. **High Risk**: `requestor_handler` (workflow orchestration)

#### 4.2 Migration Template

For each Lambda function, follow this pattern:

```python
# Before (legacy): lambda_functions/search_handler/search_handler.py
import boto3
import json
from services.aws_storage import AWSStorage
from services.logging_config import setup_logging

def lambda_handler(event, context):
    # Direct service instantiation
    storage = AWSStorage()
    logger = setup_logging()
    
    # Business logic mixed with infrastructure
    dynamodb = boto3.resource('dynamodb')
    # ... rest of function

# After (enterprise): src/presentation/lambda_handlers/search_handler.py
from src.shared.dependency_injection.bootstrap import bootstrap_container
from src.application.use_cases.search_offers_use_case import SearchOffersUseCase

def lambda_handler(event, context):
    # Dependency injection
    container = bootstrap_container()
    use_case = container.get(SearchOffersUseCase)
    
    # Clean business logic
    try:
        result = await use_case.execute(event)
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        logger = container.get(ILogger)
        logger.error(f"Search failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
```

#### 4.3 Gradual Migration Process

For each function:

1. **Create new handler** alongside legacy handler
2. **Deploy both versions** with different function names
3. **Route small percentage** of traffic to new version
4. **Monitor and compare** performance and errors
5. **Gradually increase** traffic to new version
6. **Switch completely** once confident
7. **Remove legacy** handler

```bash
# Deploy new version alongside legacy
terraform apply -var="deploy_new_search_handler=true"

# Route 10% traffic to new version
aws lambda put-provisioned-concurrency-config \
  --function-name search_handler_new \
  --qualifier '$LATEST' \
  --provisioned-concurrency-config ProvisionedConcurrencyConfig=10

# Monitor both versions
aws logs tail /aws/lambda/search_handler --follow &
aws logs tail /aws/lambda/search_handler_new --follow &
```

### Step 5: Data Migration

#### 5.1 Database Schema Migration

The new architecture uses the same DynamoDB tables but with improved access patterns:

```python
# Migration script: scripts/migrate_data.py
import asyncio
from src.shared.dependency_injection.bootstrap import bootstrap_container
from src.infrastructure.persistence.legacy_aws_storage import LegacyAWSStorage
from src.infrastructure.persistence.aws_dynamodb_repository import DynamoDBSearchResultRepository

async def migrate_search_results():
    container = bootstrap_container()
    legacy_storage = LegacyAWSStorage()
    new_repository = container.get(DynamoDBSearchResultRepository)
    
    # Migrate existing data
    legacy_results = await legacy_storage.get_all_results()
    for result in legacy_results:
        # Transform to new format if needed
        await new_repository.save_result(result)
    
    print(f"Migrated {len(legacy_results)} search results")

if __name__ == "__main__":
    asyncio.run(migrate_search_results())
```

#### 5.2 Configuration Migration

```bash
# Migrate configuration files
python scripts/migrate_config.py \
  --source config/production.json \
  --target config/production_enterprise.json
```

### Step 6: Testing Migration

#### 6.1 Comprehensive Testing

```bash
# Run migration tests
python -m pytest tests/migration/ -v

# Run integration tests with new architecture
python run_comprehensive_tests.py --architecture enterprise

# Compare performance
python tests/performance/test_architecture_comparison.py
```

#### 6.2 Load Testing

```bash
# Test Lambda functions under load
artillery run tests/load/lambda_load_test.yml

# Test container deployment
artillery run tests/load/container_load_test.yml
```

### Step 7: Production Deployment

#### 7.1 Blue-Green Deployment

```bash
# Deploy new architecture to staging
terraform workspace select staging
terraform apply -var="architecture=enterprise"

# Run smoke tests
python tests/smoke/test_enterprise_architecture.py

# Deploy to production with blue-green
terraform workspace select production
terraform apply -var="blue_green_deployment=true"
```

#### 7.2 Monitoring and Rollback

```bash
# Monitor key metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=search_handler_new

# Rollback if needed
terraform apply -var="rollback_to_legacy=true"
```

## Migration Checklist

### Pre-Migration
- [ ] Backup current system
- [ ] Set up monitoring and alerting
- [ ] Create rollback procedures
- [ ] Test migration scripts in development

### During Migration
- [ ] Migrate functions in low-risk order
- [ ] Monitor performance and errors
- [ ] Maintain backward compatibility
- [ ] Document any issues encountered

### Post-Migration
- [ ] Remove legacy code
- [ ] Update documentation
- [ ] Train team on new architecture
- [ ] Optimize performance

## Common Migration Issues

### Issue 1: Import Path Changes

**Problem**: Legacy imports fail after migration
```python
# Legacy import
from services.aws_storage import AWSStorage

# New import
from src.infrastructure.persistence.aws_dynamodb_repository import DynamoDBSearchResultRepository
```

**Solution**: Use import mapping during transition
```python
# src/shared/migration/import_compatibility.py
from src.infrastructure.persistence.legacy_aws_storage import LegacyAWSStorage as AWSStorage
```

### Issue 2: Configuration Format Changes

**Problem**: Legacy configuration format incompatible
```json
// Legacy format
{
  "aws_region": "us-east-1",
  "dynamodb_table": "search_results"
}

// New format
{
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "prod_"
  }
}
```

**Solution**: Configuration adapter
```python
# src/shared/migration/config_adapter.py
def adapt_legacy_config(legacy_config):
    return {
        "database": {
            "provider": "aws_dynamodb",
            "region": legacy_config.get("aws_region"),
            "table_prefix": legacy_config.get("table_prefix", "")
        }
    }
```

### Issue 3: Performance Regression

**Problem**: New architecture slower than legacy
**Solution**: 
- Profile dependency injection overhead
- Optimize container initialization
- Cache frequently used services
- Use connection pooling

### Issue 4: Memory Usage Increase

**Problem**: Lambda functions use more memory
**Solution**:
- Optimize DI container memory usage
- Lazy load services
- Adjust Lambda memory allocation
- Monitor cold start performance

## Rollback Procedures

### Emergency Rollback

```bash
# Immediate rollback to legacy
terraform apply -var="emergency_rollback=true"

# Restore legacy Lambda functions
aws lambda update-function-code \
  --function-name search_handler \
  --zip-file fileb://lambda_packages/search_handler_legacy.zip
```

### Partial Rollback

```bash
# Rollback specific function
terraform apply -var="rollback_search_handler=true"

# Keep other migrated functions
terraform apply -var="keep_migrated_functions=true"
```

## Post-Migration Optimization

### Performance Tuning

```python
# Optimize DI container
container.enable_caching()
container.preload_services(['ISearchResultRepository', 'ILogger'])

# Connection pooling
container.configure_connection_pool(
    max_connections=10,
    connection_timeout=30
)
```

### Monitoring Setup

```python
# Enhanced monitoring
from src.shared.monitoring.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor()
monitor.track_migration_metrics()
monitor.compare_architectures()
```

## Success Criteria

Migration is considered successful when:

- [ ] All Lambda functions migrated and working
- [ ] Performance equal or better than legacy
- [ ] Error rates within acceptable limits
- [ ] All tests passing
- [ ] Team trained on new architecture
- [ ] Documentation updated
- [ ] Legacy code removed

## Support and Troubleshooting

For issues during migration:

1. Check the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
2. Review migration logs in CloudWatch
3. Compare metrics between legacy and new architecture
4. Use rollback procedures if critical issues occur

## Next Steps After Migration

1. **Optimize Performance**: Fine-tune DI container and service configurations
2. **Enhance Monitoring**: Set up comprehensive observability
3. **Team Training**: Ensure team understands new architecture
4. **Documentation**: Update all technical documentation
5. **Continuous Improvement**: Gather feedback and iterate

The migration to enterprise architecture provides a solid foundation for future enhancements and multi-cloud deployment capabilities.