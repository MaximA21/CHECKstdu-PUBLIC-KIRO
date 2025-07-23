# Shared AWS Resources Configuration Guide

This guide documents the shared AWS resources configuration for the production deployment pipeline in the eu-central-1 region.

## Overview

The shared resources include:
- **DynamoDB Tables**: Data storage with backup and encryption
- **SQS Queues**: Message queuing with dead letter queues
- **Step Functions**: Workflow orchestration
- **CloudWatch**: Logging, monitoring, and alerting
- **AWS Backup**: Automated backup and disaster recovery
- **KMS**: Encryption key management

## Region Configuration

All resources are configured for deployment in **eu-central-1** (Frankfurt) region as specified in the requirements.

### Region Validation
```bash
# Verify current region configuration
terraform output region_configuration
```

## DynamoDB Tables

### Provider Results Table
- **Name**: `{project_name}-{environment}-results`
- **Purpose**: Store search results and provider responses
- **Billing Mode**: Pay-per-request (serverless)
- **Encryption**: Server-side encryption enabled
- **Backup**: Point-in-time recovery enabled
- **TTL**: Automatic cleanup using `expires_at` attribute

**Global Secondary Indexes:**
- `ShareTokenIndex`: For share link functionality
- `SessionIndex`: For user session tracking
- `AnalyticsIndex`: For analytics and reporting

### Analytics Table
- **Name**: `{project_name}-{environment}-analytics`
- **Purpose**: Store aggregated analytics data
- **Billing Mode**: Pay-per-request (serverless)
- **Encryption**: Server-side encryption enabled
- **Backup**: Point-in-time recovery enabled

## SQS Queues

### Request Queue
- **Name**: `{project_name}-{environment}-request-queue`
- **Purpose**: Handle incoming search requests
- **Message Retention**: 24 hours
- **Visibility Timeout**: 5 minutes
- **Encryption**: KMS encryption enabled
- **Dead Letter Queue**: After 5 failed attempts

### Results Queue
- **Name**: `{project_name}-{environment}-results-queue`
- **Purpose**: Handle provider API responses
- **Message Retention**: 24 hours
- **Visibility Timeout**: 5 minutes
- **Encryption**: KMS encryption enabled
- **Dead Letter Queue**: After 3 failed attempts

### Dead Letter Queues
- **Request DLQ**: 14-day retention for analysis
- **Results DLQ**: 14-day retention for analysis
- **Monitoring**: CloudWatch alarms for message accumulation

## Step Functions

### Provider Workflow
- **Name**: `{project_name}-{environment}-provider-workflow`
- **Purpose**: Orchestrate parallel provider API calls
- **Logging**: Full execution logging enabled
- **Tracing**: X-Ray tracing enabled
- **Error Handling**: Comprehensive retry and error handling

**Supported Providers:**
- ByteMe
- VerbynDich
- Servus Speed
- WebWunder
- Ping Perfect

## CloudWatch Configuration

### Log Groups
All log groups are configured with:
- **Encryption**: KMS encryption using dedicated logs key
- **Retention**: Configurable retention periods
- **Monitoring**: Automated log analysis and alerting

**Log Groups:**
- API Gateway logs: `/aws/apigateway/{api_name}`
- Lambda function logs: `/aws/lambda/{function_name}`
- Step Functions logs: `/aws/stepfunctions/{state_machine_name}`

### Retention Policies
- **API Gateway Logs**: 30 days (configurable via `log_retention_days`)
- **Lambda Logs**: 14 days (configurable via `lambda_log_retention_days`)
- **Step Functions Logs**: 7 days (configurable via `step_functions_log_retention_days`)

### Monitoring Dashboard
- **Name**: `{project_name}-{environment}-shared-resources`
- **Metrics**: DynamoDB capacity, SQS queue depths, Step Functions execution metrics
- **Real-time**: 5-minute refresh intervals

### CloudWatch Alarms
- **DynamoDB Throttling**: Alerts on any throttled requests
- **SQS DLQ Messages**: Alerts when dead letter queues accumulate messages
- **SQS Message Age**: Alerts when messages age beyond thresholds
- **Step Functions Failures**: Alerts on execution failures

## Backup and Disaster Recovery

### AWS Backup Configuration
- **Backup Vault**: Encrypted with dedicated KMS key
- **Backup Plans**: Daily and weekly backup schedules
- **Retention**: 365 days for daily, 3 years for weekly
- **Cold Storage**: Move to cold storage after 30/90 days

### Point-in-Time Recovery
- **DynamoDB PITR**: Enabled for all tables
- **Recovery Window**: 35 days
- **Granularity**: Second-level recovery precision

### Backup Schedule
- **Daily Backups**: 2:00 AM UTC
- **Weekly Backups**: Sunday 3:00 AM UTC
- **Automated**: No manual intervention required

## Security Configuration

### Encryption
- **DynamoDB**: Server-side encryption with AWS managed keys
- **SQS**: KMS encryption with AWS managed keys
- **CloudWatch Logs**: KMS encryption with dedicated key
- **Backup**: KMS encryption with dedicated backup key
- **Kinesis**: KMS encryption for log streaming

### IAM Roles and Policies
- **Backup Role**: Service role for AWS Backup operations
- **Log Destination Role**: Role for CloudWatch log streaming
- **Least Privilege**: All roles follow least privilege principle

### Key Management
- **Logs KMS Key**: Dedicated key for CloudWatch logs encryption
- **Backup KMS Key**: Dedicated key for backup encryption
- **Key Rotation**: Automatic key rotation enabled
- **Key Policies**: Restricted access with service-specific permissions

## Monitoring and Alerting

### SNS Topic
- **Name**: `{project_name}-{environment}-alerts`
- **Purpose**: Central alerting for all CloudWatch alarms
- **Integration**: All alarms send notifications to this topic

### Alarm Thresholds
- **Request Queue DLQ**: > 10 messages
- **Results Queue DLQ**: > 5 messages
- **Message Age**: > 15 minutes (request), > 10 minutes (results)
- **DynamoDB Throttles**: > 0 throttled requests
- **Step Functions Failures**: > 5 failed executions

### Log Streaming
- **Kinesis Stream**: Real-time log streaming for analysis
- **Retention**: 24 hours in stream
- **Encryption**: KMS encrypted
- **Monitoring**: Stream metrics and alarms

## Configuration Variables

### Required Variables
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

### Optional Variables
```hcl
variable "log_retention_days" {
  default = 30
}

variable "lambda_log_retention_days" {
  default = 14
}

variable "step_functions_log_retention_days" {
  default = 7
}

variable "backup_retention_days" {
  default = 365
}

variable "backup_cold_storage_days" {
  default = 30
}
```

## Validation and Testing

### Validation Script
Use the provided validation script to verify resource configuration:

```bash
# Run validation
python3 scripts/validate-shared-resources.py

# With custom parameters
python3 scripts/validate-shared-resources.py \
  --region eu-central-1 \
  --project provider-comparison \
  --environment dev \
  --output validation-results.json
```

### Terraform Validation
```bash
# Validate configuration
cd terraform
terraform validate

# Plan deployment
terraform plan

# Apply changes
terraform apply
```

## Outputs

The configuration provides comprehensive outputs for integration:

```hcl
# DynamoDB table information
output "dynamodb_tables" {
  value = {
    provider_results = { name, arn }
    analytics = { name, arn }
  }
}

# SQS queue information
output "sqs_queues" {
  value = {
    request_queue = { name, url, arn }
    results_queue = { name, url, arn }
    request_dlq = { name, url, arn }
    results_dlq = { name, url, arn }
  }
}

# Backup configuration
output "backup_configuration" {
  value = {
    backup_vault_name
    backup_plan_id
    kms_key_id
  }
}

# Monitoring configuration
output "monitoring_configuration" {
  value = {
    sns_topic_arn
    dashboard_url
    log_stream_name
    logs_kms_key_id
  }
}
```

## Troubleshooting

### Common Issues

1. **Region Mismatch**
   - Verify `aws_region` variable is set to `eu-central-1`
   - Check AWS provider configuration

2. **Permission Errors**
   - Ensure AWS credentials have sufficient permissions
   - Verify IAM roles and policies are correctly configured

3. **Resource Conflicts**
   - Check for existing resources with same names
   - Verify unique naming conventions

4. **Backup Failures**
   - Check backup vault permissions
   - Verify KMS key policies allow backup service access

### Validation Commands
```bash
# Check resource status
aws dynamodb describe-table --table-name provider-comparison-dev-results --region eu-central-1
aws sqs get-queue-attributes --queue-url <queue-url> --attribute-names All --region eu-central-1
aws stepfunctions describe-state-machine --state-machine-arn <arn> --region eu-central-1

# Check backup status
aws backup describe-backup-vault --backup-vault-name provider-comparison-dev-dynamodb-backup-vault --region eu-central-1
aws backup list-backup-plans --region eu-central-1
```

## Maintenance

### Regular Tasks
- Monitor CloudWatch alarms and dashboards
- Review backup success/failure reports
- Analyze DLQ messages for patterns
- Update retention policies as needed
- Review and rotate access keys

### Scaling Considerations
- DynamoDB auto-scaling with pay-per-request
- SQS queues scale automatically
- Step Functions concurrent execution limits
- CloudWatch log ingestion limits

### Cost Optimization
- Review log retention periods
- Monitor backup storage costs
- Analyze DynamoDB usage patterns
- Consider reserved capacity for predictable workloads

## Compliance and Governance

### Data Protection
- Encryption at rest and in transit
- Access logging and auditing
- Data retention policies
- Backup and recovery procedures

### Monitoring and Alerting
- Real-time monitoring of all resources
- Automated alerting for anomalies
- Performance metrics tracking
- Security event monitoring

### Documentation
- Infrastructure as code documentation
- Operational runbooks
- Disaster recovery procedures
- Security incident response plans