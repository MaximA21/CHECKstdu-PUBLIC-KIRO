# WebSocket API Gateway Configuration Guide

This guide explains the WebSocket API Gateway configuration with 50/50 traffic distribution between old and new implementations in AWS eu-central-1.

## Overview

The WebSocket API Gateway is configured to:
- Route WebSocket connections to eu-central-1 region
- Distribute traffic 50/50 between old and new implementations
- Track connections and enforce limits (2 minutes OR 5 results)
- Provide comprehensive monitoring and logging
- Support both production and staging environments

## Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   WebSocket     │    │   Connection Router  │    │  Implementation     │
│   Client        │───▶│   Lambda Function    │───▶│  Selection          │
└─────────────────┘    └──────────────────────┘    └─────────────────────┘
                                │                            │
                                ▼                            ▼
                       ┌─────────────────┐         ┌─────────────────┐
                       │   DynamoDB      │         │   Old/New       │
                       │   Connection    │         │   Lambda        │
                       │   Tracking      │         │   Functions     │
                       └─────────────────┘         └─────────────────┘
```

## Components

### 1. API Gateway WebSocket API

**Resource**: `aws_apigatewayv2_api.websocket_api`

- **Protocol**: WebSocket
- **Region**: eu-central-1
- **Route Selection**: `$request.body.action`
- **Stages**: Production (`prod`) and Staging (`staging`)

**Key Features**:
- Traffic distribution enabled
- Connection tracking enabled
- Detailed CloudWatch metrics
- Access logging for monitoring

### 2. Connection Router Lambda

**Resource**: `aws_lambda_function.connection_router`

- **Handler**: `connection_router.lambda_handler`
- **Runtime**: Python 3.9
- **Architecture**: ARM64
- **Memory**: 512 MB
- **Timeout**: 15 seconds

**Functionality**:
- Hash-based routing for 50/50 traffic split
- Connection state tracking in DynamoDB
- Route consistency across WebSocket messages
- Activity tracking for limit enforcement

### 3. Connection Routing DynamoDB Table

**Resource**: `aws_dynamodb_table.connection_routing`

- **Billing Mode**: Pay-per-request
- **Hash Key**: `connection_id`
- **TTL**: Enabled (3 hours)

**Indexes**:
- `implementation-index`: Query by implementation type
- `status-index`: Query by connection status

**Fields**:
- `connection_id`: Unique WebSocket connection identifier
- `implementation`: "old" or "new"
- `created_at`: Connection creation timestamp
- `result_count`: Number of results delivered
- `last_activity`: Last activity timestamp
- `status`: Connection status ("active", "closed")
- `ttl`: Time-to-live for automatic cleanup

### 4. Connection Limit Enforcer Lambda

**Resource**: `aws_lambda_function.connection_limit_enforcer`

- **Handler**: `connection_limit_enforcer.lambda_handler`
- **Runtime**: Python 3.9
- **Memory**: 512 MB
- **Timeout**: 60 seconds
- **Trigger**: EventBridge (every minute)

**Functionality**:
- Enforces 2-minute connection timeout
- Enforces 5-result limit per connection
- Automatic connection cleanup
- CloudWatch metrics reporting

### 5. Traffic Distribution Logic

The connection router uses hash-based routing to achieve consistent 50/50 traffic distribution:

```python
def hash_based_routing(connection_id: str) -> str:
    hash_value = hashlib.md5(connection_id.encode()).hexdigest()
    hash_int = int(hash_value[:8], 16)
    
    if hash_int % 100 < 50:  # 50% threshold
        return 'new'
    else:
        return 'old'
```

## Configuration

### Environment Variables

**Connection Router**:
- `ROUTING_TABLE_NAME`: DynamoDB table name
- `OLD_CONNECT_LAMBDA`: Old implementation connect handler
- `NEW_CONNECT_LAMBDA`: New implementation connect handler
- `OLD_SEARCH_LAMBDA`: Old implementation search handler
- `NEW_SEARCH_LAMBDA`: New implementation search handler
- `TRAFFIC_SPLIT_PERCENTAGE`: Traffic split percentage (50)
- `CONNECTION_TIMEOUT_MINUTES`: Connection timeout (2)
- `MAX_RESULTS_PER_CONNECTION`: Result limit (5)

**Connection Limit Enforcer**:
- `ROUTING_TABLE_NAME`: DynamoDB table name
- `WEBSOCKET_API_ENDPOINT`: WebSocket API endpoint
- `CONNECTION_TIMEOUT_MINUTES`: Connection timeout (2)
- `MAX_RESULTS_PER_CONNECTION`: Result limit (5)

### Terraform Variables

```hcl
variable "aws_region" {
  default = "eu-central-1"
}

variable "project_name" {
  default = "provider-comparison"
}

variable "environment" {
  default = "dev"
}
```

## Deployment

### Prerequisites

1. AWS CLI configured with appropriate permissions
2. Terraform >= 1.0 installed
3. Lambda packages built and available in `lambda_packages/`

### Deployment Steps

1. **Build Lambda packages**:
   ```bash
   bash scripts/build-lambda-packages.sh
   ```

2. **Deploy infrastructure**:
   ```bash
   bash scripts/deploy-websocket-api.sh
   ```

3. **Validate deployment**:
   ```bash
   bash scripts/deploy-websocket-api.sh validate
   ```

### Manual Deployment

```bash
cd terraform
terraform init
terraform plan -var="aws_region=eu-central-1"
terraform apply
```

## Monitoring

### CloudWatch Dashboards

**WebSocket Traffic Distribution Dashboard**:
- Lambda function invocations (old vs new)
- Error rates by implementation
- Response times and duration
- Connection metrics

### CloudWatch Alarms

- **Error Rate Monitoring**: Alerts when error rate exceeds threshold
- **Connection Limit Breaches**: Monitors connection limit enforcement
- **Traffic Distribution Imbalance**: Alerts on significant traffic imbalance

### Metrics

**Custom Metrics** (Namespace: `WebSocket/ConnectionLimits`):
- `ConnectionsChecked`: Number of connections checked
- `ConnectionsDisconnected`: Connections closed due to limits
- `EnforcementErrors`: Errors during limit enforcement

**API Gateway Metrics**:
- `IntegrationLatency`: Response time from Lambda functions
- `Count`: Number of API calls
- `4XXError` / `5XXError`: Error rates

### Logging

**API Gateway Access Logs**:
```json
{
  "requestId": "$context.requestId",
  "ip": "$context.identity.sourceIp",
  "requestTime": "$context.requestTime",
  "routeKey": "$context.routeKey",
  "status": "$context.status",
  "connectionId": "$context.connectionId",
  "error": "$context.error.message",
  "integrationLatency": "$context.integrationLatency",
  "responseLength": "$context.responseLength",
  "userAgent": "$context.identity.userAgent",
  "protocol": "$context.protocol",
  "stage": "$context.stage"
}
```

## Testing

### Connection Testing

```bash
# Set environment variables
export WEBSOCKET_URL="wss://your-api-id.execute-api.eu-central-1.amazonaws.com/prod"
export ROUTING_TABLE_NAME="provider-comparison-dev-connection-routing"

# Run validation
python3 scripts/validate-websocket-api.py
```

### Manual Testing

```javascript
// JavaScript WebSocket client example
const ws = new WebSocket('wss://your-api-id.execute-api.eu-central-1.amazonaws.com/prod');

ws.onopen = function() {
    console.log('Connected to WebSocket');
    
    // Send search request
    ws.send(JSON.stringify({
        action: 'search',
        data: {
            address: 'Test Address',
            providers: ['test']
        }
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    console.log('Implementation:', data.implementation);
};
```

## Connection Limits

### Timeout Enforcement

Connections are automatically closed after **2 minutes** regardless of activity.

### Result Limit Enforcement

Connections are automatically closed after delivering **5 results**.

### Enforcement Schedule

- **Connection Limit Enforcer**: Runs every minute via EventBridge
- **Connection Cleanup**: Runs every 5 minutes for stale connection cleanup
- **DynamoDB TTL**: Automatic cleanup after 3 hours

## Traffic Distribution

### Hash-Based Routing

- Uses MD5 hash of connection ID for consistent routing
- Achieves approximately 50/50 distribution over time
- Maintains routing consistency for the same connection

### Implementation Selection

- **New Implementation**: Refactored code with dependency injection
- **Old Implementation**: Legacy code for comparison
- **Fallback**: Defaults to new implementation on errors

### Monitoring Distribution

Check the CloudWatch dashboard for:
- Invocation counts by implementation
- Error rates comparison
- Performance metrics comparison

## Troubleshooting

### Common Issues

1. **Connection Failures**:
   - Check Lambda function logs
   - Verify IAM permissions
   - Check API Gateway configuration

2. **Traffic Imbalance**:
   - Monitor hash distribution
   - Check connection router logs
   - Verify routing table entries

3. **Connection Limits Not Enforced**:
   - Check EventBridge rule status
   - Verify connection limit enforcer logs
   - Check DynamoDB table permissions

### Debug Commands

```bash
# Check API Gateway logs
aws logs describe-log-groups --log-group-name-prefix "/aws/apigateway"

# Check Lambda function logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda"

# Query connection routing table
aws dynamodb scan --table-name provider-comparison-dev-connection-routing

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace "WebSocket/ConnectionLimits" \
  --metric-name "ConnectionsDisconnected" \
  --start-time "2024-01-01T00:00:00Z" \
  --end-time "2024-01-01T23:59:59Z" \
  --period 3600 \
  --statistics Sum
```

## Security Considerations

### IAM Permissions

- Lambda functions have minimal required permissions
- API Gateway uses least privilege access
- DynamoDB access restricted to specific tables

### Network Security

- WebSocket API uses WSS (secure WebSocket)
- All traffic encrypted in transit
- VPC configuration available if needed

### Data Protection

- Connection data stored temporarily in DynamoDB
- Automatic cleanup via TTL
- No sensitive data logged

## Performance Optimization

### Lambda Configuration

- ARM64 architecture for better price/performance
- Appropriate memory allocation (512 MB)
- Connection pooling for DynamoDB

### DynamoDB Optimization

- Pay-per-request billing for variable workloads
- Global secondary indexes for efficient queries
- TTL for automatic cleanup

### API Gateway Optimization

- Throttling configured to prevent abuse
- Detailed metrics enabled for monitoring
- Access logging optimized for performance analysis

## Maintenance

### Regular Tasks

1. **Monitor CloudWatch dashboards** for traffic distribution
2. **Review connection limit metrics** for enforcement effectiveness
3. **Check error rates** and investigate anomalies
4. **Update Lambda packages** as needed
5. **Review and adjust** traffic split percentage if required

### Scaling Considerations

- Lambda functions auto-scale based on demand
- DynamoDB scales automatically with pay-per-request
- API Gateway handles high connection volumes
- Consider reserved capacity for predictable workloads

## Cost Optimization

### Current Configuration

- **Lambda**: Pay-per-invocation with ARM64 pricing
- **DynamoDB**: Pay-per-request with automatic scaling
- **API Gateway**: Pay-per-connection and message
- **CloudWatch**: Standard logging and metrics pricing

### Cost Monitoring

- Set up billing alerts for unexpected costs
- Monitor Lambda invocation counts
- Track DynamoDB read/write units
- Review API Gateway usage metrics

## Future Enhancements

### Planned Improvements

1. **Advanced Traffic Routing**: Implement weighted routing with gradual traffic shifts
2. **Connection Pooling**: Optimize connection reuse for better performance
3. **Enhanced Monitoring**: Add custom business metrics and alerting
4. **Auto-scaling**: Implement predictive scaling based on usage patterns
5. **Multi-region Support**: Extend to multiple AWS regions for global deployment

### Configuration Updates

The traffic distribution can be adjusted by modifying the `TRAFFIC_SPLIT_PERCENTAGE` environment variable in the connection router Lambda function. This allows for gradual migration between implementations without infrastructure changes.