# REST API Canary Deployment Guide

This guide explains how to use the REST API Gateway canary deployment functionality for gradual traffic shifting between old and new implementations.

## Overview

The REST API canary deployment system allows you to:
- Deploy new implementations alongside existing ones
- Gradually shift traffic from old to new implementations
- Monitor performance and error rates during deployment
- Automatically rollback if issues are detected
- Promote successful deployments to full traffic

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway REST API                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Production Stage (prod)                                    │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   Main Traffic  │    │      Canary Traffic             │ │
│  │   (90% default) │    │      (10% default)              │ │
│  │                 │    │                                 │ │
│  │  ┌─────────────┐│    │  ┌─────────────────────────────┐│ │
│  │  │ Old Lambda  ││    │  │     New Lambda              ││ │
│  │  │ Function    ││    │  │     Function                ││ │
│  │  └─────────────┘│    │  └─────────────────────────────┘│ │
│  └─────────────────┘    └─────────────────────────────────┘ │
│                                                             │
│  Staging Stage (staging)                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Testing Environment                        │ │
│  │  ┌─────────────────────────────────────────────────────┐│ │
│  │  │            New Lambda Function                      ││ │
│  │  └─────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Terraform Variables

Configure canary deployment in `terraform/terraform.tfvars`:

```hcl
# Enable canary deployment
canary_enabled = true

# Initial traffic percentage to canary (0-100)
canary_traffic_percentage = 10

# API throttling settings
rest_api_throttle_rate_limit = 500
rest_api_throttle_burst_limit = 1000

# Cache TTL for responses
rest_api_cache_ttl = 300
```

### Environment Variables

Lambda functions receive these environment variables:
- `IMPLEMENTATION`: "new" or "old" to identify the implementation
- `LOG_LEVEL`: Logging level for the function
- `RESULTS_TABLE_NAME`: DynamoDB table name for results

## Deployment Process

### 1. Initial Deployment

Deploy the infrastructure with canary disabled:

```bash
cd terraform
terraform apply -var="canary_enabled=false"
```

### 2. Enable Canary Deployment

Enable canary with initial traffic percentage:

```bash
terraform apply -var="canary_enabled=true" -var="canary_traffic_percentage=10"
```

### 3. Gradual Traffic Shifting

Use the management script to gradually increase traffic:

```bash
# Check current status
./scripts/manage-canary-deployment.py --api-name provider-comparison-dev-rest-api status

# Gradually shift to 25% traffic
./scripts/manage-canary-deployment.py --api-name provider-comparison-dev-rest-api shift --target 25

# Shift to 50% traffic with custom step size and wait time
./scripts/manage-canary-deployment.py --api-name provider-comparison-dev-rest-api shift --target 50 --step 10 --wait 3

# Promote to full deployment (100%)
./scripts/manage-canary-deployment.py --api-name provider-comparison-dev-rest-api promote
```

### 4. Rollback if Needed

If issues are detected, rollback immediately:

```bash
./scripts/manage-canary-deployment.py --api-name provider-comparison-dev-rest-api rollback
```

## Monitoring and Validation

### CloudWatch Dashboards

Access the canary deployment dashboard:
- Dashboard name: `provider-comparison-dev-rest-api-canary`
- Metrics include: request count, error rates, latency, Lambda metrics

### CloudWatch Alarms

The following alarms are configured:
- **High Error Rate**: Triggers when 4XX errors exceed 10 in 10 minutes
- **High Latency**: Triggers when average latency exceeds 5 seconds
- **Lambda Errors (New)**: Monitors errors in new implementation
- **Lambda Errors (Old)**: Monitors errors in old implementation
- **Rollback Trigger**: Automatically suggests rollback on high error rates

### Validation Script

Run comprehensive validation:

```bash
# Validate canary deployment setup
./scripts/validate-rest-api-canary.py --api-name provider-comparison-dev-rest-api

# Save results to file
./scripts/validate-rest-api-canary.py --api-name provider-comparison-dev-rest-api --output validation-results.json
```

The validation script checks:
- ✅ API endpoint availability
- ✅ CORS configuration
- ✅ Canary deployment settings
- ✅ CloudWatch monitoring setup
- ✅ Load testing performance

## API Endpoints

### Production Endpoints
- **Main API**: `https://{api-id}.execute-api.eu-central-1.amazonaws.com/prod`
- **Share API**: `https://{api-id}.execute-api.eu-central-1.amazonaws.com/prod/share/{token}`

### Staging Endpoints
- **Staging API**: `https://{api-id}.execute-api.eu-central-1.amazonaws.com/staging`
- **Share API**: `https://{api-id}.execute-api.eu-central-1.amazonaws.com/staging/share/{token}`

## Traffic Distribution Logic

### Request Routing
1. **Main Traffic**: Routes to old implementation (stable)
2. **Canary Traffic**: Routes to new implementation (testing)
3. **Distribution**: Based on percentage configuration (e.g., 90%/10%)

### Stage Variables
- `implementation`: Identifies which implementation is handling the request
- `traffic_split`: Current traffic percentage to canary

### Headers and Tracing
- **X-Ray Tracing**: Enabled for both implementations
- **CORS Headers**: Properly configured for cross-origin requests
- **Custom Headers**: Implementation identifier in response headers

## Best Practices

### Deployment Strategy
1. **Start Small**: Begin with 5-10% canary traffic
2. **Monitor Closely**: Watch metrics for 5-10 minutes between increases
3. **Gradual Increase**: Increase by 10-25% increments
4. **Health Checks**: Validate error rates and latency at each step
5. **Quick Rollback**: Be prepared to rollback immediately if issues arise

### Monitoring Guidelines
- **Error Rate Threshold**: Keep below 5% for healthy deployment
- **Latency Threshold**: Maintain under 5 seconds average response time
- **Success Rate**: Aim for >95% success rate during canary deployment

### Testing Recommendations
- **Load Testing**: Run load tests before production deployment
- **Functional Testing**: Validate all API endpoints work correctly
- **CORS Testing**: Ensure cross-origin requests work properly
- **Error Handling**: Test error scenarios and response codes

## Troubleshooting

### Common Issues

#### High Error Rates
```bash
# Check CloudWatch logs
aws logs filter-log-events --log-group-name "/aws/apigateway/provider-comparison-dev-rest-api" --start-time $(date -d '1 hour ago' +%s)000

# Rollback immediately
./scripts/manage-canary-deployment.py --api-name provider-comparison-dev-rest-api rollback
```

#### High Latency
```bash
# Check Lambda function metrics
aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Duration --dimensions Name=FunctionName,Value=provider-comparison-dev-share-api-new --start-time $(date -d '1 hour ago' --iso-8601) --end-time $(date --iso-8601) --period 300 --statistics Average
```

#### CORS Issues
```bash
# Test CORS configuration
curl -X OPTIONS -H "Origin: https://example.com" -H "Access-Control-Request-Method: GET" https://{api-id}.execute-api.eu-central-1.amazonaws.com/prod/share/test
```

### Log Analysis

#### API Gateway Logs
```bash
# View access logs
aws logs filter-log-events --log-group-name "/aws/apigateway/provider-comparison-dev-rest-api" --filter-pattern "ERROR"
```

#### Lambda Function Logs
```bash
# New implementation logs
aws logs filter-log-events --log-group-name "/aws/lambda/provider-comparison-dev-share-api-new"

# Old implementation logs
aws logs filter-log-events --log-group-name "/aws/lambda/provider-comparison-dev-share-api-old"
```

## Security Considerations

### IAM Permissions
- Lambda functions have minimal required permissions
- API Gateway uses resource-based policies
- CloudWatch logs have appropriate retention policies

### Network Security
- API Gateway uses HTTPS only
- CORS configured for specific origins in production
- Rate limiting and throttling enabled

### Data Protection
- No sensitive data logged in access logs
- X-Ray tracing excludes sensitive parameters
- DynamoDB access is read-only for share API

## Performance Optimization

### Caching Strategy
- Response caching enabled in production (5-minute TTL)
- Cache keys based on share token
- Cache invalidation on deployment

### Throttling Configuration
- Rate limiting: 500 requests/second (configurable)
- Burst limit: 1000 requests (configurable)
- Per-method throttling enabled

### Lambda Optimization
- ARM64 architecture for better price/performance
- Appropriate memory allocation (256MB)
- Connection pooling for DynamoDB
- X-Ray tracing for performance monitoring

## Maintenance

### Regular Tasks
- Monitor CloudWatch dashboards weekly
- Review error logs monthly
- Update Lambda runtime versions quarterly
- Test rollback procedures monthly

### Capacity Planning
- Monitor request patterns and adjust throttling
- Scale Lambda concurrency if needed
- Review cache hit rates and adjust TTL

### Cost Optimization
- Monitor API Gateway request costs
- Optimize Lambda memory allocation
- Review CloudWatch log retention policies