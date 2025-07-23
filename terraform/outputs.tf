# WebSocket API Gateway Outputs
output "websocket_api_id" {
  description = "ID of the WebSocket API Gateway"
  value       = aws_apigatewayv2_api.websocket_api.id
}

output "websocket_api_endpoint" {
  description = "WebSocket API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.websocket_api.api_endpoint
}

output "websocket_api_execution_arn" {
  description = "Execution ARN of the WebSocket API Gateway"
  value       = aws_apigatewayv2_api.websocket_api.execution_arn
}

# Production Stage Outputs
output "websocket_prod_stage_url" {
  description = "Production stage WebSocket URL"
  value       = "${replace(aws_apigatewayv2_api.websocket_api.api_endpoint, "wss://", "")}/${aws_apigatewayv2_stage.prod.name}"
}

output "websocket_prod_stage_invoke_url" {
  description = "Production stage WebSocket invoke URL"
  value       = "wss://${replace(aws_apigatewayv2_api.websocket_api.api_endpoint, "wss://", "")}/${aws_apigatewayv2_stage.prod.name}"
}

# Staging Stage Outputs
output "websocket_staging_stage_url" {
  description = "Staging stage WebSocket URL"
  value       = "${replace(aws_apigatewayv2_api.websocket_api.api_endpoint, "wss://", "")}/${aws_apigatewayv2_stage.staging.name}"
}

output "websocket_staging_stage_invoke_url" {
  description = "Staging stage WebSocket invoke URL"
  value       = "wss://${replace(aws_apigatewayv2_api.websocket_api.api_endpoint, "wss://", "")}/${aws_apigatewayv2_stage.staging.name}"
}

# Connection Router Outputs
output "connection_router_function_name" {
  description = "Name of the connection router Lambda function"
  value       = aws_lambda_function.connection_router.function_name
}

output "connection_router_function_arn" {
  description = "ARN of the connection router Lambda function"
  value       = aws_lambda_function.connection_router.arn
}

# Connection Routing Table Outputs
output "connection_routing_table_name" {
  description = "Name of the connection routing DynamoDB table"
  value       = aws_dynamodb_table.connection_routing.name
}

output "connection_routing_table_arn" {
  description = "ARN of the connection routing DynamoDB table"
  value       = aws_dynamodb_table.connection_routing.arn
}

# Connection Limit Enforcer Outputs
output "connection_limit_enforcer_function_name" {
  description = "Name of the connection limit enforcer Lambda function"
  value       = aws_lambda_function.connection_limit_enforcer.function_name
}

output "connection_limit_enforcer_function_arn" {
  description = "ARN of the connection limit enforcer Lambda function"
  value       = aws_lambda_function.connection_limit_enforcer.arn
}

# CloudWatch Dashboard Outputs
output "websocket_traffic_dashboard_url" {
  description = "URL of the WebSocket traffic distribution CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.websocket_traffic_distribution.dashboard_name}"
}

# API Logs Outputs
output "api_logs_group_name" {
  description = "Name of the API Gateway logs CloudWatch log group"
  value       = aws_cloudwatch_log_group.api_logs.name
}

output "api_logs_group_arn" {
  description = "ARN of the API Gateway logs CloudWatch log group"
  value       = aws_cloudwatch_log_group.api_logs.arn
}

# Traffic Distribution Configuration
output "traffic_split_percentage" {
  description = "Percentage of traffic routed to new implementation"
  value       = "50"
}

output "old_implementation_functions" {
  description = "Lambda functions for old implementation"
  value = {
    connect_handler = aws_lambda_function.connect_handler_old.function_name
    search_handler  = aws_lambda_function.search_handler_old.function_name
  }
}

output "new_implementation_functions" {
  description = "Lambda functions for new implementation"
  value = {
    connect_handler = aws_lambda_function.connect_handler.function_name
    search_handler  = aws_lambda_function.search_handler.function_name
  }
}

# Shared Resources Outputs
output "dynamodb_tables" {
  description = "DynamoDB table information"
  value = {
    provider_results = {
      name = aws_dynamodb_table.provider_results.name
      arn  = aws_dynamodb_table.provider_results.arn
    }
    analytics = {
      name = aws_dynamodb_table.analytics.name
      arn  = aws_dynamodb_table.analytics.arn
    }
  }
}

output "sqs_queues" {
  description = "SQS queue information"
  value = {
    request_queue = {
      name = aws_sqs_queue.request_queue.name
      url  = aws_sqs_queue.request_queue.url
      arn  = aws_sqs_queue.request_queue.arn
    }
    results_queue = {
      name = aws_sqs_queue.results_queue.name
      url  = aws_sqs_queue.results_queue.url
      arn  = aws_sqs_queue.results_queue.arn
    }
    request_dlq = {
      name = aws_sqs_queue.request_dlq.name
      url  = aws_sqs_queue.request_dlq.url
      arn  = aws_sqs_queue.request_dlq.arn
    }
    results_dlq = {
      name = aws_sqs_queue.results_dlq.name
      url  = aws_sqs_queue.results_dlq.url
      arn  = aws_sqs_queue.results_dlq.arn
    }
  }
}

output "step_functions" {
  description = "Step Functions information"
  value = {
    provider_workflow = {
      name = aws_sfn_state_machine.provider_workflow.name
      arn  = aws_sfn_state_machine.provider_workflow.arn
    }
  }
}

output "backup_configuration" {
  description = "Backup and disaster recovery configuration"
  value = var.enable_aws_backup ? {
    backup_vault_name = aws_backup_vault.dynamodb_backup_vault[0].name
    backup_plan_id    = aws_backup_plan.dynamodb_backup_plan[0].id
    kms_key_id        = var.enable_custom_kms_keys ? aws_kms_key.backup_key[0].key_id : null
    retention_days    = var.backup_retention_days
    } : {
    backup_vault_name = "disabled"
    backup_plan_id    = "disabled"
    kms_key_id        = "disabled"
    retention_days    = 0
  }
}

output "monitoring_configuration" {
  description = "Monitoring and alerting configuration"
  value = {
    sns_topic_arn   = aws_sns_topic.alerts.arn
    dashboard_url   = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.shared_resources.dashboard_name}"
    log_stream_name = var.enable_kinesis_stream ? aws_kinesis_stream.log_stream[0].name : "disabled"
    logs_kms_key_id = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].key_id : "aws-managed"
  }
}

# Security and audit configuration output
output "security_configuration" {
  description = "Security and audit configuration details"
  value = {
    cloudtrail_name    = aws_cloudtrail.basic_trail.name
    cloudtrail_bucket  = aws_s3_bucket.cloudtrail_logs.bucket
    kms_encryption     = var.enable_custom_kms_keys ? "custom" : "aws-managed"
    audit_logging      = "enabled"
    log_retention_days = var.log_retention_days
    backup_enabled     = var.enable_aws_backup
    cost_optimized     = !var.enable_custom_kms_keys && !var.enable_aws_backup && !var.enable_kinesis_stream
  }
}

output "region_configuration" {
  description = "AWS region configuration validation"
  value = {
    configured_region = var.aws_region
    actual_region     = data.aws_region.current.name
    region_validated  = var.aws_region == data.aws_region.current.name
  }
}

# GitHub OIDC Configuration Outputs
output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role for OIDC authentication"
  value       = aws_iam_role.github_actions_role.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC identity provider"
  value       = aws_iam_openid_connect_provider.github_actions.arn
}

output "deployment_artifacts_bucket_name" {
  description = "Name of the S3 bucket for deployment artifacts"
  value       = aws_s3_bucket.deployment_artifacts.bucket
}

output "github_oidc_configuration" {
  description = "Complete GitHub OIDC configuration for repository setup"
  value = {
    role_arn           = aws_iam_role.github_actions_role.arn
    oidc_provider_arn  = aws_iam_openid_connect_provider.github_actions.arn
    deployment_bucket  = aws_s3_bucket.deployment_artifacts.bucket
    trusted_repository = var.github_repository
    aws_region         = var.aws_region
    setup_instructions = "See docs/GITHUB_OIDC_SETUP.md for configuration steps"
  }
}