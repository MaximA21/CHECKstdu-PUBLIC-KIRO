# shared_resources.tf - Shared AWS resources configuration for eu-central-1

# KMS key for CloudWatch logs encryption (conditional for cost optimization)
resource "aws_kms_key" "logs_key" {
  count = var.enable_custom_kms_keys ? 1 : 0

  description             = "KMS key for CloudWatch logs encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-logs-key"
  })
}

resource "aws_kms_alias" "logs_key_alias" {
  count = var.enable_custom_kms_keys ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-logs-key"
  target_key_id = aws_kms_key.logs_key[0].key_id
}

# Lambda function log groups with proper retention and encryption
resource "aws_cloudwatch_log_group" "lambda_logs" {
  for_each = toset([
    "connect_handler",
    "disconnect_handler",
    "search_handler",
    "results_handler",
    "requestor_handler",
    "share_api",
    "authorizer",
    "address_normalizer",
    "ping_perfect_signer",
    "connection_limit_enforcer",
    "connection_router"
  ])

  name              = "/aws/lambda/${var.project_name}-${var.environment}-${each.key}"
  retention_in_days = var.lambda_log_retention_days
  kms_key_id        = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].arn : null

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-${each.key}-logs"
    Function = each.key
  })
}

# CloudWatch dashboard for shared resources monitoring
resource "aws_cloudwatch_dashboard" "shared_resources" {
  dashboard_name = "${var.project_name}-${var.environment}-shared-resources"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.provider_results.name],
            [".", "ConsumedWriteCapacityUnits", ".", "."],
            [".", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.analytics.name],
            [".", "ConsumedWriteCapacityUnits", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "DynamoDB Capacity Consumption"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfVisibleMessages", "QueueName", aws_sqs_queue.request_queue.name],
            [".", ".", ".", aws_sqs_queue.results_queue.name],
            [".", ".", ".", aws_sqs_queue.request_dlq.name],
            [".", ".", ".", aws_sqs_queue.results_dlq.name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "SQS Queue Depths"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 24
        height = 6

        properties = {
          metrics = [
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", aws_sfn_state_machine.provider_workflow.arn],
            [".", "ExecutionsSucceeded", ".", "."],
            [".", "ExecutionTime", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Step Functions Execution Metrics"
          period  = 300
        }
      }
    ]
  })
}

# CloudWatch alarms for shared resources (conditional for cost optimization)
resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  for_each = var.minimal_cloudwatch_alarms ? [] : toset([
    aws_dynamodb_table.provider_results.name,
    aws_dynamodb_table.analytics.name
  ])

  alarm_name          = "${var.project_name}-${var.environment}-dynamodb-throttles-${each.key}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ThrottledRequests"
  namespace           = "AWS/DynamoDB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors DynamoDB throttling for ${each.key}"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    TableName = each.key
  }

  tags = local.common_tags
}

# Essential alarm for Step Functions failures (always enabled)
resource "aws_cloudwatch_metric_alarm" "step_functions_failures" {
  alarm_name          = "${var.project_name}-${var.environment}-step-functions-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10" # Higher threshold for cost optimization
  alarm_description   = "This metric monitors Step Functions execution failures"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.provider_workflow.arn
  }

  tags = local.common_tags
}

# Essential cost monitoring alarm
resource "aws_cloudwatch_metric_alarm" "monthly_cost_alarm" {
  alarm_name          = "${var.project_name}-${var.environment}-monthly-cost-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = var.monthly_cost_alert_threshold
  alarm_description   = "Monthly AWS cost exceeded threshold of $${var.monthly_cost_alert_threshold}"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    Currency = "USD"
  }

  tags = local.common_tags
}

# Data retention policy for CloudWatch Insights (conditional - expensive Kinesis stream)
# Kinesis stream disabled by default for cost optimization (saves ~$28/month)
resource "aws_cloudwatch_log_destination" "log_destination" {
  count = var.enable_kinesis_stream ? 1 : 0

  name       = "${var.project_name}-${var.environment}-log-destination"
  role_arn   = aws_iam_role.log_destination_role[0].arn
  target_arn = aws_kinesis_stream.log_stream[0].arn

  tags = local.common_tags
}

resource "aws_kinesis_stream" "log_stream" {
  count = var.enable_kinesis_stream ? 1 : 0

  name             = "${var.project_name}-${var.environment}-log-stream"
  shard_count      = 1
  retention_period = 24

  encryption_type = "KMS"
  kms_key_id      = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].arn : "alias/aws/kinesis"

  tags = local.common_tags
}

resource "aws_iam_role" "log_destination_role" {
  count = var.enable_kinesis_stream ? 1 : 0

  name = "${var.project_name}-${var.environment}-log-destination-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "logs.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "log_destination_policy" {
  count = var.enable_kinesis_stream ? 1 : 0

  name = "${var.project_name}-${var.environment}-log-destination-policy"
  role = aws_iam_role.log_destination_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord",
          "kinesis:PutRecords"
        ]
        Resource = aws_kinesis_stream.log_stream[0].arn
      }
    ]
  })
}