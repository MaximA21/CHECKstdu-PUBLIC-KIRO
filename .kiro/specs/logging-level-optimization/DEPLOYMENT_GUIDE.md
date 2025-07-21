# Logging Level Optimization Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the optimized logging system across all Lambda functions, including environment variable configuration and validation procedures.

## Pre-Deployment Checklist

- [ ] Verify all Lambda functions have been updated with new logging patterns
- [ ] Confirm centralized logging configuration is deployed
- [ ] Test logging behavior in development environment
- [ ] Review current CloudWatch log volume and costs
- [ ] Prepare rollback plan for each function

## Environment Variable Configuration

### Setting LOG_LEVEL for Lambda Functions

#### Option 1: Terraform Configuration

Add the LOG_LEVEL environment variable to your Lambda function configurations:

```hcl
resource "aws_lambda_function" "address_normalizer" {
  # ... other configuration ...
  
  environment {
    variables = {
      LOG_LEVEL = "INFO"  # or "DEBUG", "WARNING", "ERROR"
      # ... other environment variables ...
    }
  }
}
```

Apply the changes:
```bash
cd terraform
terraform plan
terraform apply
```

#### Option 2: AWS CLI

Set environment variables for individual functions:

```bash
# Set INFO level (recommended for production)
aws lambda update-function-configuration \
  --function-name address_normalizer \
  --environment Variables='{LOG_LEVEL=INFO}'

# Set DEBUG level (for troubleshooting)
aws lambda update-function-configuration \
  --function-name address_normalizer \
  --environment Variables='{LOG_LEVEL=DEBUG}'
```

#### Option 3: AWS Console

1. Navigate to AWS Lambda console
2. Select the function to configure
3. Go to "Configuration" tab
4. Select "Environment variables"
5. Add or edit `LOG_LEVEL` variable
6. Set value to `DEBUG`, `INFO`, `WARNING`, or `ERROR`
7. Save changes

### Recommended Log Levels by Environment

#### Production Environment
```bash
LOG_LEVEL=INFO
```
- Provides essential operational information
- Minimizes log volume and costs
- Includes errors, warnings, and key business metrics

#### Staging Environment
```bash
LOG_LEVEL=INFO
```
- Same as production for realistic testing
- Can temporarily set to DEBUG for issue investigation

#### Development Environment
```bash
LOG_LEVEL=DEBUG
```
- Maximum visibility for development and debugging
- Shows all log messages including detailed event data

#### Troubleshooting
```bash
LOG_LEVEL=DEBUG
```
- Temporarily enable for specific functions experiencing issues
- Remember to revert to INFO after troubleshooting

## Deployment Strategy

### Phase 1: Non-Critical Functions (Low Risk)
Deploy to functions with minimal business impact first:

1. **ping_perfect_signer**
   ```bash
   aws lambda update-function-configuration \
     --function-name ping_perfect_signer \
     --environment Variables='{LOG_LEVEL=INFO}'
   ```

2. **connect_handler**
   ```bash
   aws lambda update-function-configuration \
     --function-name connect_handler \
     --environment Variables='{LOG_LEVEL=INFO}'
   ```

3. **Monitor for 24 hours**
   - Check CloudWatch logs for proper log levels
   - Verify no errors in function execution
   - Monitor log volume changes

### Phase 2: Medium-Critical Functions
Deploy to functions with moderate business impact:

1. **address_normalizer**
2. **search_handler**
3. **authorizer**

### Phase 3: High-Critical Functions
Deploy to business-critical functions last:

1. **results_handler**
2. **requestor_handler**
3. **share_api**

### Validation Steps for Each Phase

After deploying to each function:

1. **Verify Environment Variable**
   ```bash
   aws lambda get-function-configuration \
     --function-name FUNCTION_NAME \
     --query 'Environment.Variables.LOG_LEVEL'
   ```

2. **Test Function Execution**
   ```bash
   aws lambda invoke \
     --function-name FUNCTION_NAME \
     --payload '{}' \
     response.json
   ```

3. **Check CloudWatch Logs**
   ```bash
   aws logs describe-log-groups \
     --log-group-name-prefix "/aws/lambda/FUNCTION_NAME"
   
   aws logs get-log-events \
     --log-group-name "/aws/lambda/FUNCTION_NAME" \
     --log-stream-name LATEST_STREAM
   ```

4. **Verify Log Levels**
   - Confirm INFO messages appear for key operations
   - Verify DEBUG messages are filtered out (unless LOG_LEVEL=DEBUG)
   - Check ERROR messages include proper context

## Rollback Procedures

### Individual Function Rollback

If issues occur with a specific function:

1. **Revert Environment Variable**
   ```bash
   aws lambda update-function-configuration \
     --function-name FUNCTION_NAME \
     --environment Variables='{LOG_LEVEL=INFO}'
   ```

2. **Deploy Previous Function Version** (if needed)
   ```bash
   aws lambda update-function-code \
     --function-name FUNCTION_NAME \
     --zip-file fileb://previous_version.zip
   ```

### Complete System Rollback

If system-wide issues occur:

1. **Revert All Environment Variables**
   ```bash
   # Script to revert all functions
   for function in address_normalizer authorizer connect_handler ping_perfect_signer requestor_handler results_handler search_handler share_api; do
     aws lambda update-function-configuration \
       --function-name $function \
       --environment Variables='{LOG_LEVEL=INFO}'
   done
   ```

2. **Deploy Previous Code Versions**
   - Use your deployment pipeline to revert to previous versions
   - Or manually deploy previous ZIP files

## Post-Deployment Monitoring

### Immediate Monitoring (First 24 Hours)

1. **Function Health**
   - Monitor error rates in CloudWatch
   - Check function execution duration
   - Verify successful invocations

2. **Log Volume**
   - Compare log volume before/after deployment
   - Monitor CloudWatch costs
   - Check for log message completeness

3. **Application Functionality**
   - Test critical user flows
   - Verify API responses
   - Check downstream system integration

### Ongoing Monitoring (First Week)

1. **Performance Impact**
   - Monitor function execution times
   - Check memory usage patterns
   - Verify no performance degradation

2. **Log Quality**
   - Review log messages for clarity
   - Ensure error logs provide sufficient context
   - Validate monitoring alerts still work

3. **Cost Impact**
   - Monitor CloudWatch log ingestion costs
   - Compare costs with previous period
   - Adjust log levels if costs are excessive

## Environment-Specific Configurations

### Production Configuration
```bash
# Terraform variables
variable "log_level_production" {
  default = "INFO"
}

# Apply to all Lambda functions
environment {
  variables = {
    LOG_LEVEL = var.log_level_production
  }
}
```

### Development Configuration
```bash
# Terraform variables
variable "log_level_development" {
  default = "DEBUG"
}
```

### Staging Configuration
```bash
# Terraform variables
variable "log_level_staging" {
  default = "INFO"
}
```

## Troubleshooting Deployment Issues

### Common Issues and Solutions

#### Issue: Environment Variable Not Set
**Symptoms**: Function uses default INFO level despite configuration
**Solution**: 
```bash
# Verify environment variable is set
aws lambda get-function-configuration --function-name FUNCTION_NAME

# Re-apply environment variable
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --environment Variables='{LOG_LEVEL=DEBUG}'
```

#### Issue: Invalid Log Level Value
**Symptoms**: Function logs show warning about invalid log level
**Solution**:
```bash
# Set to valid value (DEBUG, INFO, WARNING, ERROR)
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --environment Variables='{LOG_LEVEL=INFO}'
```

#### Issue: No Log Output
**Symptoms**: No logs appearing in CloudWatch
**Solution**:
1. Check Lambda execution role has CloudWatch permissions
2. Verify function is actually executing
3. Check CloudWatch log group exists

#### Issue: Too Many Debug Logs
**Symptoms**: Excessive log volume and costs
**Solution**:
```bash
# Reduce log level to INFO
aws lambda update-function-configuration \
  --function-name FUNCTION_NAME \
  --environment Variables='{LOG_LEVEL=INFO}'
```

## Validation Scripts

### Log Level Verification Script
```bash
#!/bin/bash
# verify_log_levels.sh

FUNCTIONS=("address_normalizer" "authorizer" "connect_handler" "ping_perfect_signer" "requestor_handler" "results_handler" "search_handler" "share_api")

echo "Verifying LOG_LEVEL environment variables..."
for func in "${FUNCTIONS[@]}"; do
  level=$(aws lambda get-function-configuration \
    --function-name $func \
    --query 'Environment.Variables.LOG_LEVEL' \
    --output text 2>/dev/null)
  
  if [ "$level" = "None" ] || [ -z "$level" ]; then
    echo "❌ $func: LOG_LEVEL not set"
  else
    echo "✅ $func: LOG_LEVEL=$level"
  fi
done
```

### Function Health Check Script
```bash
#!/bin/bash
# health_check.sh

FUNCTIONS=("address_normalizer" "authorizer" "connect_handler" "ping_perfect_signer" "requestor_handler" "results_handler" "search_handler" "share_api")

echo "Checking function health..."
for func in "${FUNCTIONS[@]}"; do
  # Test function invocation
  aws lambda invoke \
    --function-name $func \
    --payload '{}' \
    /tmp/response.json >/dev/null 2>&1
  
  if [ $? -eq 0 ]; then
    echo "✅ $func: Healthy"
  else
    echo "❌ $func: Failed"
  fi
done
```

## Success Criteria

Deployment is considered successful when:

- [ ] All Lambda functions have LOG_LEVEL environment variable set
- [ ] Functions execute without errors
- [ ] Log messages appear at appropriate levels
- [ ] CloudWatch costs remain within acceptable range
- [ ] Monitoring and alerting systems continue to work
- [ ] No degradation in application functionality
- [ ] Rollback procedures tested and documented