# Troubleshooting Guide: Enterprise Architecture

This guide provides solutions for common issues encountered when deploying and operating the enterprise architecture with dependency injection and clean architecture patterns.

## Quick Diagnosis

### Health Check Commands

```bash
# Check overall system health
curl http://localhost:8000/health

# Check DI container health
curl http://localhost:8000/health/di

# Check individual service health
python -c "
from src.shared.dependency_injection.bootstrap import bootstrap_container
container = bootstrap_container()
print(container.get_health_status())
"

# Validate configuration
python -m src.shared.dependency_injection.validate_config
```

### Log Analysis

```bash
# Check application logs
tail -f /var/log/enterprise-app/application.log

# Check Lambda logs
aws logs tail /aws/lambda/search_handler --follow

# Check container logs
docker logs enterprise-app --follow

# Search for specific errors
grep -r "ERROR" /var/log/enterprise-app/
```

## Configuration Issues

### Issue 1: Invalid Configuration Format

**Symptoms:**
- Application fails to start
- Error: "Configuration validation failed"
- Missing or invalid JSON in config files

**Diagnosis:**
```bash
# Validate JSON syntax
python -m json.tool config/production.json

# Check configuration schema
python -c "
from src.infrastructure.config.validator import ConfigValidator
validator = ConfigValidator()
validator.validate_file('config/production.json')
"
```

**Solutions:**

1. **Fix JSON Syntax Errors:**
```json
// Bad - trailing comma
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb",
  }
}

// Good - no trailing comma
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb"
  }
}
```

2. **Add Missing Required Fields:**
```json
{
  "environment": "production",
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1"  // Required for AWS
  },
  "messaging": {
    "provider": "aws_sqs",
    "region": "us-east-1"  // Required for AWS
  }
}
```

3. **Use Configuration Template:**
```bash
# Copy from working template
cp config/default.json config/production.json
# Edit production-specific values
```

### Issue 2: Environment Variable Conflicts

**Symptoms:**
- Wrong configuration loaded
- Services using incorrect implementations
- Environment detection failures

**Diagnosis:**
```bash
# Check environment variables
env | grep -E "(CONFIG_ENV|AWS_|DATABASE_|LOGGING_)"

# Check configuration loading
python -c "
from src.infrastructure.config.loader import ConfigLoader
loader = ConfigLoader()
print(f'Environment: {loader.get_environment()}')
print(f'Config file: {loader.get_config_file_path()}')
"
```

**Solutions:**

1. **Set Correct Environment Variable:**
```bash
# For Lambda
export CONFIG_ENV=production

# For containers
docker run -e CONFIG_ENV=production enterprise-app

# For systemd service
echo "Environment=CONFIG_ENV=production" >> /etc/systemd/system/enterprise-app.service
```

2. **Check Environment Priority:**
```python
# Environment detection order:
1. CONFIG_ENV environment variable
2. AWS_LAMBDA_FUNCTION_NAME (auto-detects Lambda)
3. KUBERNETES_SERVICE_HOST (auto-detects K8s)
4. Default to "development"
```

### Issue 3: Missing Configuration Files

**Symptoms:**
- FileNotFoundError for config files
- Application defaults to development mode
- Services not configured properly

**Diagnosis:**
```bash
# Check config file existence
ls -la config/
find . -name "*.json" -path "*/config/*"

# Check file permissions
ls -la config/production.json
```

**Solutions:**

1. **Create Missing Config Files:**
```bash
# Create from template
cp config/default.json config/production.json

# Set proper permissions
chmod 644 config/production.json
chown app:app config/production.json
```

2. **Use Environment-Specific Paths:**
```bash
# For Docker
COPY config/ /app/config/

# For Lambda
# Include config/ in deployment package
```

## Dependency Injection Issues

### Issue 4: Service Registration Failures

**Symptoms:**
- "Service not registered" errors
- DI container initialization failures
- Missing dependency errors

**Diagnosis:**
```python
# Check service registration
from src.shared.dependency_injection.bootstrap import bootstrap_container
container = bootstrap_container()
print(container.list_registered_services())

# Check specific service
try:
    service = container.get(ISearchResultRepository)
    print(f"Service found: {type(service)}")
except Exception as e:
    print(f"Service not found: {e}")
```

**Solutions:**

1. **Check Service Registration Order:**
```python
# Problem: Dependency registered after dependent service
container.register(IServiceA, ServiceA)  # Depends on IServiceB
container.register(IServiceB, ServiceB)  # Should be registered first

# Solution: Register dependencies first
container.register(IServiceB, ServiceB)
container.register(IServiceA, ServiceA)
```

2. **Verify Interface Imports:**
```python
# Problem: Wrong interface import
from wrong.module import ISearchResultRepository

# Solution: Correct interface import
from src.application.interfaces.repositories import ISearchResultRepository
```

3. **Check Configuration-Based Registration:**
```json
{
  "database": {
    "provider": "aws_dynamodb"  // Must match registered provider
  }
}
```

### Issue 5: Circular Dependencies

**Symptoms:**
- "Circular dependency detected" errors
- Stack overflow during service resolution
- Infinite recursion in constructors

**Diagnosis:**
```python
# Generate dependency graph
python -c "
from src.shared.dependency_injection.bootstrap import bootstrap_container
container = bootstrap_container()
container.generate_dependency_graph()
"
```

**Solutions:**

1. **Use Factory Pattern:**
```python
# Problem: Direct circular dependency
class ServiceA:
    def __init__(self, service_b: IServiceB):
        self.service_b = service_b

class ServiceB:
    def __init__(self, service_a: IServiceA):
        self.service_a = service_a

# Solution: Factory pattern
class ServiceA:
    def __init__(self, service_b_factory: Callable[[], IServiceB]):
        self._service_b_factory = service_b_factory
    
    @property
    def service_b(self):
        return self._service_b_factory()
```

2. **Interface Segregation:**
```python
# Problem: Large interface causing circular dependency
class ILargeService:
    def method_a(self): pass
    def method_b(self): pass

# Solution: Split into smaller interfaces
class IServiceA:
    def method_a(self): pass

class IServiceB:
    def method_b(self): pass
```

### Issue 6: Service Lifetime Issues

**Symptoms:**
- Memory leaks with singleton services
- State pollution between requests
- Performance issues with transient services

**Diagnosis:**
```python
# Check service lifetimes
container = bootstrap_container()
lifetimes = container.get_service_lifetimes()
for service, lifetime in lifetimes.items():
    print(f"{service}: {lifetime}")
```

**Solutions:**

1. **Fix Singleton State Issues:**
```python
# Problem: Mutable state in singleton
class SingletonService:
    def __init__(self):
        self.request_data = {}  # Shared across requests!

# Solution: Stateless singleton
class SingletonService:
    def process_request(self, request_data):
        # Process without storing state
        return self._process(request_data)
```

2. **Optimize Service Lifetimes:**
```json
{
  "di_container": {
    "service_lifetimes": {
      "ISearchResultRepository": "singleton",    // Database connections
      "ILogger": "singleton",                    // Logging services
      "IProviderService": "transient",           // Stateful operations
      "SearchOffersUseCase": "transient"         // Business logic
    }
  }
}
```

## AWS Integration Issues

### Issue 7: AWS Credentials Problems

**Symptoms:**
- "Unable to locate credentials" errors
- AWS service access denied
- Lambda function permission errors

**Diagnosis:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check Lambda execution role
aws lambda get-function --function-name search_handler

# Check IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/lambda-execution-role \
  --action-names dynamodb:GetItem \
  --resource-arns arn:aws:dynamodb:us-east-1:123456789012:table/search_results
```

**Solutions:**

1. **Configure AWS Credentials:**
```bash
# For local development
aws configure

# For Lambda (use execution role)
# Attach policies to Lambda execution role

# For containers (use IAM roles for tasks)
# Configure task role in ECS/Fargate
```

2. **Fix IAM Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/search_results*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage"
      ],
      "Resource": "arn:aws:sqs:*:*:search-*"
    }
  ]
}
```

### Issue 8: DynamoDB Connection Issues

**Symptoms:**
- Connection timeouts to DynamoDB
- "Table does not exist" errors
- Throttling errors

**Diagnosis:**
```python
# Test DynamoDB connection
import boto3
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
try:
    table = dynamodb.Table('search_results')
    response = table.describe_table()
    print(f"Table status: {response['Table']['TableStatus']}")
except Exception as e:
    print(f"DynamoDB error: {e}")
```

**Solutions:**

1. **Check Table Configuration:**
```bash
# Verify table exists
aws dynamodb describe-table --table-name search_results

# Check table status
aws dynamodb list-tables
```

2. **Configure Connection Settings:**
```json
{
  "database": {
    "provider": "aws_dynamodb",
    "region": "us-east-1",
    "table_prefix": "prod_",
    "connection_timeout": 30,
    "retry_attempts": 3,
    "max_connections": 10
  }
}
```

3. **Handle Throttling:**
```python
# Configure exponential backoff
import boto3
from botocore.config import Config

config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)
dynamodb = boto3.resource('dynamodb', config=config)
```

## Performance Issues

### Issue 9: Slow Service Resolution

**Symptoms:**
- High latency in Lambda cold starts
- Slow application startup
- DI container performance issues

**Diagnosis:**
```python
# Profile service resolution
import time
from src.shared.dependency_injection.bootstrap import bootstrap_container

start_time = time.time()
container = bootstrap_container()
init_time = time.time() - start_time

start_time = time.time()
service = container.get(ISearchResultRepository)
resolution_time = time.time() - start_time

print(f"Container init: {init_time:.3f}s")
print(f"Service resolution: {resolution_time:.3f}s")
```

**Solutions:**

1. **Enable Container Caching:**
```json
{
  "di_container": {
    "enable_caching": true,
    "preload_services": [
      "ISearchResultRepository",
      "ILogger",
      "IMessageQueue"
    ]
  }
}
```

2. **Optimize Lambda Cold Starts:**
```python
# Global container initialization
_container = None

def lambda_handler(event, context):
    global _container
    if _container is None:
        _container = bootstrap_container()
    
    # Use cached container
    use_case = _container.get(SearchOffersUseCase)
```

3. **Use Lazy Loading:**
```python
# Lazy service registration
container.register_lazy(IExpensiveService, lambda: ExpensiveService())
```

### Issue 10: Memory Usage Issues

**Symptoms:**
- High memory consumption
- Out of memory errors in Lambda
- Memory leaks in long-running processes

**Diagnosis:**
```python
# Monitor memory usage
import psutil
import gc

def check_memory():
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"RSS: {memory_info.rss / 1024 / 1024:.2f} MB")
    print(f"VMS: {memory_info.vms / 1024 / 1024:.2f} MB")
    print(f"Objects: {len(gc.get_objects())}")

# Check before and after service resolution
check_memory()
container = bootstrap_container()
check_memory()
```

**Solutions:**

1. **Optimize Service Lifetimes:**
```json
{
  "di_container": {
    "service_lifetimes": {
      "IProviderService": "transient",  // Don't cache stateful services
      "ILogger": "singleton"            // Cache stateless services
    }
  }
}
```

2. **Configure Lambda Memory:**
```bash
# Increase Lambda memory allocation
aws lambda update-function-configuration \
  --function-name search_handler \
  --memory-size 512
```

3. **Implement Cleanup:**
```python
# Cleanup in long-running processes
def cleanup_services():
    container.dispose_transient_services()
    gc.collect()
```

## External Service Issues

### Issue 11: Provider Service Failures

**Symptoms:**
- External API timeouts
- Provider service unavailable errors
- Inconsistent provider responses

**Diagnosis:**
```python
# Test individual providers
from src.infrastructure.external_services.byteme_adapter import ByteMeAdapter

adapter = ByteMeAdapter()
try:
    offers = await adapter.get_offers(test_address)
    print(f"ByteMe: {len(offers)} offers")
except Exception as e:
    print(f"ByteMe error: {e}")
```

**Solutions:**

1. **Configure Circuit Breaker:**
```json
{
  "external_services": {
    "byteme": {
      "enabled": true,
      "timeout": 30,
      "retry_attempts": 3,
      "circuit_breaker": {
        "failure_threshold": 5,
        "recovery_timeout": 60
      }
    }
  }
}
```

2. **Implement Fallback Logic:**
```python
class ProviderAggregator:
    async def get_offers(self, address):
        offers = []
        for provider in self.providers:
            try:
                provider_offers = await provider.get_offers(address)
                offers.extend(provider_offers)
            except Exception as e:
                self.logger.warning(f"Provider {provider.name} failed: {e}")
                # Continue with other providers
        return offers
```

3. **Add Health Checks:**
```python
@app.get("/health/providers")
async def provider_health():
    health_status = {}
    for provider in providers:
        try:
            await provider.health_check()
            health_status[provider.name] = "healthy"
        except Exception as e:
            health_status[provider.name] = f"unhealthy: {e}"
    return health_status
```

## Deployment Issues

### Issue 12: Container Deployment Failures

**Symptoms:**
- Container fails to start
- Port binding errors
- Environment variable issues

**Diagnosis:**
```bash
# Check container logs
docker logs enterprise-app

# Check port usage
netstat -tulpn | grep :8000

# Check environment variables
docker exec enterprise-app env
```

**Solutions:**

1. **Fix Port Conflicts:**
```yaml
# docker-compose.yml
services:
  app:
    ports:
      - "8080:8000"  # Use different host port
      - "8081:8001"
```

2. **Configure Environment Variables:**
```yaml
services:
  app:
    environment:
      - CONFIG_ENV=production
      - AWS_REGION=us-east-1
      - DATABASE_PROVIDER=aws_dynamodb
```

3. **Add Health Checks:**
```yaml
services:
  app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Issue 13: Lambda Deployment Issues

**Symptoms:**
- Lambda function update failures
- Package size too large
- Import errors in Lambda

**Diagnosis:**
```bash
# Check package size
ls -lh lambda_packages/

# Check Lambda configuration
aws lambda get-function-configuration --function-name search_handler

# Test Lambda locally
sam local invoke search_handler -e test_event.json
```

**Solutions:**

1. **Optimize Package Size:**
```bash
# Remove unnecessary files
find lambda_packages/ -name "*.pyc" -delete
find lambda_packages/ -name "__pycache__" -type d -exec rm -rf {} +

# Use Lambda layers for common dependencies
aws lambda publish-layer-version \
  --layer-name common-dependencies \
  --zip-file fileb://common_layer.zip
```

2. **Fix Import Paths:**
```python
# Add to Lambda handler
import sys
sys.path.append('/opt/python')  # For Lambda layers
sys.path.append('.')            # For local imports
```

## Monitoring and Debugging

### Debug Mode Configuration

```json
{
  "di_container": {
    "debug_mode": true,
    "log_service_resolution": true,
    "validate_dependencies": true,
    "track_service_lifecycle": true
  },
  "logging": {
    "level": "DEBUG",
    "structured": true
  }
}
```

### Comprehensive Health Check

```python
@app.get("/health/comprehensive")
async def comprehensive_health_check():
    container = bootstrap_container()
    
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "environment": container.config.environment,
        "services": {},
        "dependencies": {},
        "configuration": {}
    }
    
    # Check DI container
    health_status["services"]["di_container"] = {
        "status": "healthy" if container.is_initialized() else "unhealthy",
        "services_registered": len(container.list_registered_services()),
        "services_resolved": container.get_resolution_count()
    }
    
    # Check database
    try:
        repo = container.get(ISearchResultRepository)
        await repo.health_check()
        health_status["dependencies"]["database"] = "healthy"
    except Exception as e:
        health_status["dependencies"]["database"] = f"unhealthy: {e}"
    
    # Check external providers
    provider_aggregator = container.get(ProviderAggregator)
    health_status["dependencies"]["providers"] = await provider_aggregator.health_check()
    
    return health_status
```

### Performance Monitoring

```python
# Add performance monitoring
from src.shared.monitoring.performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor()

@monitor.track_performance
async def search_offers(request):
    # Business logic here
    pass

# View performance metrics
@app.get("/metrics/performance")
async def performance_metrics():
    return monitor.get_metrics()
```

## Emergency Procedures

### Rollback to Legacy Architecture

```bash
# Emergency rollback
git checkout backup-legacy-architecture
terraform apply -var="emergency_rollback=true"

# Restore Lambda functions
for func in search_handler results_handler share_api; do
    aws lambda update-function-code \
        --function-name $func \
        --zip-file fileb://legacy_packages/${func}.zip
done
```

### Service Isolation

```python
# Isolate failing service
container.disable_service(IProviderService, "byteme")

# Use fallback implementation
container.register_fallback(IProviderService, MockProviderService)
```

### Emergency Configuration

```json
{
  "emergency_mode": true,
  "external_services": {
    "byteme": {"enabled": false},
    "verbyndich": {"enabled": false},
    "webwunder": {"enabled": false},
    "ping_perfect": {"enabled": false}
  },
  "logging": {
    "level": "ERROR"
  }
}
```

## Getting Help

### Support Channels

1. **Check Documentation**: Review deployment and configuration guides
2. **Search Logs**: Use structured logging to identify issues
3. **Run Diagnostics**: Use built-in health checks and validation tools
4. **Test Components**: Isolate and test individual services
5. **Check Configuration**: Validate all configuration files and environment variables

### Useful Commands

```bash
# Quick system check
python -m src.shared.diagnostics.system_check

# Validate all configurations
python -m src.shared.diagnostics.config_validator

# Test all services
python -m src.shared.diagnostics.service_tester

# Generate diagnostic report
python -m src.shared.diagnostics.generate_report
```

This troubleshooting guide covers the most common issues encountered in the enterprise architecture. For specific issues not covered here, use the diagnostic tools and health checks to gather more information about the problem.