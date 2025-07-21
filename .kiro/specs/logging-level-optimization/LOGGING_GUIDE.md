# Logging Level Optimization Guide

## Overview

This guide provides comprehensive documentation for the optimized logging system implemented across all Lambda functions. The system uses environment-based log level configuration with consistent patterns for improved monitoring and debugging.

## Logging Patterns and Level Usage Guidelines

### Log Level Classification

#### DEBUG Level
Use DEBUG level for detailed information that is only useful during development or troubleshooting:

```python
# Event data logging
logger.debug(f"Event received: {json.dumps(event)}")

# Internal processing steps
logger.debug(f"Processing step 1: validating input data")

# Cache operations details
logger.debug(f"Cache hit for key: {cache_key}")

# Configuration values
logger.debug(f"Using configuration: {config_dict}")

# Detailed performance timing
logger.debug(f"Database query took {query_time}ms")
```

#### INFO Level
Use INFO level for important business events and operational information:

```python
# Function startup/completion
logger.info(f"Address normalizer started")
logger.info(f"Processing completed successfully")

# Key business metrics
logger.info(f"Processed {offer_count} offers in {execution_time:.1f}ms")

# Important state changes
logger.info(f"Connection established for session {session_id}")

# External service results
logger.info(f"API call to service completed with status: {status}")
```

#### WARNING Level
Use WARNING level for recoverable issues that need attention:

```python
# Recoverable errors with fallback
logger.warning(f"Primary service unavailable, using fallback")

# Performance degradation
logger.warning(f"Processing time exceeded threshold: {time}ms > {threshold}ms")

# Missing optional configurations
logger.warning(f"Optional config {key} not found, using default")
```

#### ERROR Level
Use ERROR level for critical issues that prevent normal operation:

```python
# Unrecoverable errors
logger.error(f"Failed to process request: {str(e)}")

# Critical configuration missing
logger.error(f"Required environment variable {var_name} not set")

# Data corruption or validation failures
logger.error(f"Data validation failed: {validation_errors}")
```

### Standard Logging Patterns

#### Lambda Handler Pattern
```python
import logging
from services.logging_config import configure_logger

logger = configure_logger(__name__)

def lambda_handler(event, context):
    logger.info(f"{context.function_name} started")
    logger.debug(f"Event received: {json.dumps(event)}")
    
    try:
        # Business logic here
        result = process_request(event)
        logger.info("Operation completed successfully")
        return result
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        raise
```

#### Performance Logging Pattern
```python
import time

start_time = time.time()
# ... processing ...
execution_time = (time.time() - start_time) * 1000

# Key metrics at INFO level
logger.info(f"Processing completed in {execution_time:.1f}ms")

# Detailed timing at DEBUG level
logger.debug(f"Breakdown - validation: {val_time}ms, processing: {proc_time}ms")
```

#### Error Handling Pattern
```python
try:
    result = external_api_call()
    logger.info(f"External API call successful")
    return result
except APIException as e:
    logger.error(f"API call failed: {e.message}", extra={
        'error_code': e.code,
        'endpoint': e.endpoint
    })
    raise
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    raise
```

## Environment Configuration

### LOG_LEVEL Environment Variable

The system supports the following log levels via the `LOG_LEVEL` environment variable:

- `DEBUG`: Shows all log messages (most verbose)
- `INFO`: Shows INFO, WARNING, and ERROR messages (default for production)
- `WARNING`: Shows WARNING and ERROR messages only
- `ERROR`: Shows ERROR messages only

### Default Behavior

- **Production**: Defaults to `INFO` level if `LOG_LEVEL` is not set
- **Development**: Can be set to `DEBUG` for detailed troubleshooting
- **Invalid values**: Falls back to `INFO` level with a warning

## Centralized Logger Configuration

All Lambda functions use the centralized logger configuration from `services/logging_config.py`:

```python
from services.logging_config import configure_logger

# Configure logger for your function
logger = configure_logger(__name__)
```

The centralized configuration provides:
- Environment-based log level setting
- Consistent formatting across all functions
- Structured logging support
- Safe error handling for logging operations

## Function-Specific Guidelines

### Address Normalizer
- INFO: Processing completion, offer counts, execution time
- DEBUG: Event details, validation steps, individual offer processing

### Authorizer
- INFO: Authorization results, address validation outcomes
- DEBUG: Event details, detailed validation information
- ERROR: Authorization failures with context

### Connect Handler
- INFO: Connection establishment success
- DEBUG: Connection details, session information
- ERROR: Connection failures

### Search Handler
- INFO: Search request processing, cache configuration issues
- DEBUG: Event details, cache operation details
- ERROR: Search processing failures

### Results Handler
- INFO: Performance metrics, processing summaries
- DEBUG: Detailed timing, individual result processing
- ERROR: Result processing failures

### Share API
- INFO: API response success/failure, key metrics
- DEBUG: Detailed processing logs, request/response details
- ERROR: API failures with context

## Best Practices

### Do's
- Use appropriate log levels for different types of information
- Include relevant context in error messages
- Log key business metrics at INFO level
- Use structured logging for complex data when helpful
- Include timing information for performance monitoring

### Don'ts
- Don't log sensitive information (passwords, tokens, PII)
- Don't use INFO level for detailed debugging information
- Don't log large payloads at INFO level in production
- Don't ignore exceptions without logging them
- Don't use string concatenation for log messages (use f-strings or .format())

### Performance Considerations
- DEBUG level logging has minimal performance impact when disabled
- Avoid expensive operations in log message generation
- Use lazy evaluation for complex log message formatting
- Consider log volume impact on CloudWatch costs

## Migration from Old Logging

### Before (Old Pattern)
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Everything logged at INFO level
logger.info(f"Event: {json.dumps(event)}")  # Should be DEBUG
logger.info(f"Processing step 1")           # Should be DEBUG
logger.info(f"Operation completed")         # Correct at INFO
```

### After (New Pattern)
```python
from services.logging_config import configure_logger
logger = configure_logger(__name__)

# Appropriate levels
logger.debug(f"Event: {json.dumps(event)}")  # DEBUG for details
logger.debug(f"Processing step 1")           # DEBUG for steps
logger.info(f"Operation completed")          # INFO for completion
```
#
# Troubleshooting Guide

### Common Logging Configuration Issues

#### Issue: Logs Not Appearing at Expected Level
**Symptoms**: DEBUG messages showing when LOG_LEVEL=INFO, or INFO messages missing
**Diagnosis**:
```python
# Add this to your function to debug log level
import os
import logging
logger = logging.getLogger(__name__)
logger.info(f"Current log level: {logger.level}")
logger.info(f"LOG_LEVEL env var: {os.environ.get('LOG_LEVEL', 'Not set')}")
```

**Solutions**:
1. Verify LOG_LEVEL environment variable is set correctly
2. Check if logger configuration is being called properly
3. Ensure no other code is overriding log levels

#### Issue: Logger Configuration Errors
**Symptoms**: Function fails to start or logging doesn't work
**Diagnosis**:
```python
try:
    from services.logging_config import configure_logger
    logger = configure_logger(__name__)
    logger.info("Logger configured successfully")
except Exception as e:
    print(f"Logger configuration failed: {e}")
    # Fallback to basic logging
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
```

**Solutions**:
1. Verify `services/logging_config.py` is deployed with the function
2. Check for import errors or missing dependencies
3. Use fallback logging configuration if needed

#### Issue: JSON Serialization Errors in Debug Logs
**Symptoms**: Function crashes when trying to log complex objects
**Solution**:
```python
import json

# Safe JSON logging
def safe_json_log(obj, logger, message="Object"):
    try:
        logger.debug(f"{message}: {json.dumps(obj)}")
    except (TypeError, ValueError) as e:
        logger.debug(f"{message}: <non-serializable object> - {type(obj)}")
```

#### Issue: Performance Impact from Logging
**Symptoms**: Function execution time increased after logging changes
**Diagnosis**:
```python
import time

# Measure logging overhead
start = time.time()
logger.debug(f"Large object: {json.dumps(large_object)}")
logging_time = (time.time() - start) * 1000
logger.info(f"Logging took {logging_time:.2f}ms")
```

**Solutions**:
1. Reduce log level to INFO in production
2. Use lazy evaluation for expensive log operations
3. Avoid logging large objects at DEBUG level

### Environment Variable Troubleshooting

#### Verify Environment Variables
```bash
# Check if LOG_LEVEL is set for a function
aws lambda get-function-configuration \
  --function-name FUNCTION_NAME \
  --query 'Environment.Variables.LOG_LEVEL'

# List all environment variables
aws lambda get-function-configuration \
  --function-name FUNCTION_NAME \
  --query 'Environment.Variables'
```

#### Test Different Log Levels
```bash
# Set to DEBUG for troubleshooting
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --environment Variables='{LOG_LEVEL=DEBUG}'

# Test function
aws lambda invoke \
  --function-name FUNCTION_NAME \
  --payload '{}' \
  response.json

# Check logs
aws logs get-log-events \
  --log-group-name "/aws/lambda/FUNCTION_NAME" \
  --log-stream-name $(aws logs describe-log-streams \
    --log-group-name "/aws/lambda/FUNCTION_NAME" \
    --order-by LastEventTime \
    --descending \
    --limit 1 \
    --query 'logStreams[0].logStreamName' \
    --output text)

# Revert to INFO
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --environment Variables='{LOG_LEVEL=INFO}'
```

### CloudWatch Logs Troubleshooting

#### Missing Log Groups
**Issue**: No logs appearing in CloudWatch
**Solutions**:
1. Check Lambda execution role has CloudWatch permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "logs:CreateLogGroup",
           "logs:CreateLogStream",
           "logs:PutLogEvents"
         ],
         "Resource": "arn:aws:logs:*:*:*"
       }
     ]
   }
   ```

2. Verify log group exists:
   ```bash
   aws logs describe-log-groups \
     --log-group-name-prefix "/aws/lambda/FUNCTION_NAME"
   ```

#### Log Retention and Costs
**Issue**: High CloudWatch costs due to log retention
**Solutions**:
1. Set appropriate log retention:
   ```bash
   aws logs put-retention-policy \
     --log-group-name "/aws/lambda/FUNCTION_NAME" \
     --retention-in-days 30
   ```

2. Monitor log volume:
   ```bash
   aws logs describe-log-groups \
     --log-group-name-prefix "/aws/lambda/" \
     --query 'logGroups[*].[logGroupName,storedBytes]' \
     --output table
   ```

## Monitoring and Alerting Recommendations

### CloudWatch Metrics and Alarms

#### Log Level Distribution Monitoring
Create custom metrics to track log level usage:

```python
import boto3

def publish_log_metrics(level, function_name):
    """Publish custom metrics for log level usage"""
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_data(
        Namespace='Lambda/Logging',
        MetricData=[
            {
                'MetricName': f'{level}LogCount',
                'Dimensions': [
                    {
                        'Name': 'FunctionName',
                        'Value': function_name
                    }
                ],
                'Value': 1,
                'Unit': 'Count'
            }
        ]
    )
```

#### Error Rate Monitoring
Set up alarms for increased error logging:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda-High-Error-Rate" \
  --alarm-description "Alert when error rate is high" \
  --metric-name "Errors" \
  --namespace "AWS/Lambda" \
  --statistic "Sum" \
  --period 300 \
  --threshold 5 \
  --comparison-operator "GreaterThanThreshold" \
  --evaluation-periods 2
```

### Log-Based Metrics

#### Create Metric Filters for Different Log Levels
```bash
# ERROR level metric filter
aws logs put-metric-filter \
  --log-group-name "/aws/lambda/FUNCTION_NAME" \
  --filter-name "ErrorCount" \
  --filter-pattern "[timestamp, request_id, level=\"ERROR\", ...]" \
  --metric-transformations \
    metricName=ErrorCount,metricNamespace=Lambda/Logs,metricValue=1

# WARNING level metric filter
aws logs put-metric-filter \
  --log-group-name "/aws/lambda/FUNCTION_NAME" \
  --filter-name "WarningCount" \
  --filter-pattern "[timestamp, request_id, level=\"WARNING\", ...]" \
  --metric-transformations \
    metricName=WarningCount,metricNamespace=Lambda/Logs,metricValue=1
```

#### Performance Monitoring
Create filters for performance-related logs:

```bash
# Slow execution metric filter
aws logs put-metric-filter \
  --log-group-name "/aws/lambda/FUNCTION_NAME" \
  --filter-name "SlowExecution" \
  --filter-pattern "[timestamp, request_id, level, message=\"*completed in*ms*\", duration>5000]" \
  --metric-transformations \
    metricName=SlowExecutions,metricNamespace=Lambda/Performance,metricValue=1
```

### Alerting Strategies by Log Level

#### ERROR Level Alerts (Immediate Response)
- **Threshold**: Any ERROR log
- **Response Time**: Immediate (0-5 minutes)
- **Escalation**: Page on-call engineer
- **Actions**: 
  - Send SNS notification
  - Create incident ticket
  - Trigger automated diagnostics

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda-Critical-Errors" \
  --alarm-description "Critical errors in Lambda functions" \
  --metric-name "ErrorCount" \
  --namespace "Lambda/Logs" \
  --statistic "Sum" \
  --period 60 \
  --threshold 1 \
  --comparison-operator "GreaterThanOrEqualToThreshold" \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:region:account:critical-alerts"
```

#### WARNING Level Alerts (Monitoring)
- **Threshold**: 5+ WARNING logs in 5 minutes
- **Response Time**: 15-30 minutes
- **Escalation**: Email team
- **Actions**:
  - Send email notification
  - Log to monitoring dashboard
  - Schedule investigation

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda-Warning-Threshold" \
  --alarm-description "High warning rate in Lambda functions" \
  --metric-name "WarningCount" \
  --namespace "Lambda/Logs" \
  --statistic "Sum" \
  --period 300 \
  --threshold 5 \
  --comparison-operator "GreaterThanThreshold" \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:region:account:warning-alerts"
```

#### Performance Alerts
- **Threshold**: Execution time > 5 seconds
- **Response Time**: 1 hour
- **Actions**: Performance investigation

### Dashboard Configuration

#### CloudWatch Dashboard for Logging Metrics
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["Lambda/Logs", "ErrorCount"],
          [".", "WarningCount"],
          ["AWS/Lambda", "Errors"],
          [".", "Duration"]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Lambda Logging Metrics"
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/aws/lambda/address_normalizer' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20",
        "region": "us-east-1",
        "title": "Recent Errors"
      }
    }
  ]
}
```

### Log Analysis and Insights

#### CloudWatch Insights Queries

**Find all ERROR logs across functions:**
```sql
fields @timestamp, @logStream, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

**Performance analysis:**
```sql
fields @timestamp, @message
| filter @message like /completed in/
| parse @message /completed in (?<duration>\d+\.?\d*)ms/
| stats avg(duration), max(duration), min(duration) by bin(5m)
```

**Log level distribution:**
```sql
fields @timestamp, @message
| filter @message like /INFO|DEBUG|WARNING|ERROR/
| parse @message /(?<level>INFO|DEBUG|WARNING|ERROR)/
| stats count() by level
```

### Cost Monitoring

#### Log Volume Tracking
```bash
# Monitor log ingestion costs
aws logs describe-log-groups \
  --query 'logGroups[*].[logGroupName,storedBytes]' \
  --output table

# Calculate estimated monthly costs
# (storedBytes / 1024 / 1024 / 1024) * $0.50 per GB
```

#### Cost Optimization Recommendations
1. **Set appropriate log retention periods** (7-30 days for most use cases)
2. **Use INFO level in production** to balance visibility and cost
3. **Monitor DEBUG level usage** - only enable when troubleshooting
4. **Archive old logs to S3** for long-term retention at lower cost

### Automated Monitoring Setup

#### Terraform Configuration for Monitoring
```hcl
# CloudWatch Log Metric Filters
resource "aws_cloudwatch_log_metric_filter" "error_count" {
  for_each = var.lambda_functions
  
  name           = "${each.key}-error-count"
  log_group_name = "/aws/lambda/${each.key}"
  pattern        = "[timestamp, request_id, level=\"ERROR\", ...]"

  metric_transformation {
    name      = "ErrorCount"
    namespace = "Lambda/Logs"
    value     = "1"
  }
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = var.lambda_functions
  
  alarm_name          = "${each.key}-error-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ErrorCount"
  namespace           = "Lambda/Logs"
  period              = "300"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "This metric monitors ${each.key} error count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    FunctionName = each.key
  }
}
```

This comprehensive monitoring and alerting setup ensures that:
- Critical issues are detected immediately
- Performance problems are identified quickly
- Log costs are controlled and monitored
- Teams have visibility into system health
- Automated responses can be triggered for common issues