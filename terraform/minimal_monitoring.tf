# Minimal CloudWatch monitoring configuration for cost optimization
# This file implements essential monitoring only to stay within student budget (15-20 EUR/month)

# Essential CloudWatch dashboard with key metrics only
resource "aws_cloudwatch_dashboard" "minimal_essential_dashboard" {
  dashboard_name = "${var.project_name}-${var.environment}-essential"

  dashboard_body = jsonencode({
    widgets = [
      # API Gateway essential metrics
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", "provider-comparison-websocket"],
            [".", "4XXError", ".", "."],
            [".", "5XXError", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "API Gateway - Essential Metrics"
          period  = 300
          stat    = "Sum"
        }
      },
      # Lambda essential metrics
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", "provider-comparison-connect-handler"],
            [".", "Duration", ".", "."],
            ["AWS/Lambda", "Errors", "FunctionName", "provider-comparison-results-handler"],
            [".", "Duration", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda - Essential Metrics"
          period  = 300
          stat    = "Average"
        }
      },
      # DynamoDB essential metrics
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "provider-comparison-connections"],
            [".", "ConsumedWriteCapacityUnits", ".", "."],
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "provider-comparison-results"],
            [".", "ConsumedWriteCapacityUnits", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "DynamoDB - Essential Metrics"
          period  = 300
          stat    = "Sum"
        }
      },
      # Cost tracking widget
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "Currency", "USD"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"  # Billing metrics only available in us-east-1
          title   = "Estimated Monthly Charges"
          period  = 86400  # Daily
          stat    = "Maximum"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Critical alarm: API Gateway error rate > 10%
resource "aws_cloudwatch_metric_alarm" "api_gateway_critical_error_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-api-critical-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = "10"  # 10% error rate
  alarm_description   = "Critical: API Gateway error rate exceeds 10%"
  insufficient_data_actions = []
  
  metric_query {
    id = "error_rate"
    return_data = true
    
    metric {
      metric_name = "4XXError"
      namespace   = "AWS/ApiGateway"
      period      = 300
      stat        = "Sum"
      
      dimensions = {
        ApiName = "provider-comparison-websocket"
      }
    }
  }
  
  metric_query {
    id = "total_requests"
    return_data = false
    
    metric {
      metric_name = "Count"
      namespace   = "AWS/ApiGateway"
      period      = 300
      stat        = "Sum"
      
      dimensions = {
        ApiName = "provider-comparison-websocket"
      }
    }
  }
  
  metric_query {
    id = "error_percentage"
    expression = "(error_rate / total_requests) * 100"
    return_data = false
  }

  alarm_actions = [aws_sns_topic.critical_alerts.arn]
  ok_actions    = [aws_sns_topic.critical_alerts.arn]

  tags = merge(local.common_tags, {
    Severity = "Critical"
    Type     = "ErrorRate"
  })
}

# Critical alarm: Lambda function high error rate
resource "aws_cloudwatch_metric_alarm" "lambda_critical_errors" {
  for_each = toset([
    "provider-comparison-connect-handler",
    "provider-comparison-results-handler",
    "provider-comparison-search-handler"
  ])

  alarm_name          = "${var.project_name}-${var.environment}-lambda-${each.key}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"  # 5 errors in 10 minutes
  alarm_description   = "Critical: Lambda function ${each.key} has high error rate"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = each.key
  }

  alarm_actions = [aws_sns_topic.critical_alerts.arn]

  tags = merge(local.common_tags, {
    Severity     = "Critical"
    Type         = "LambdaErrors"
    FunctionName = each.key
  })
}

# Critical alarm: High latency (> 10 seconds)
resource "aws_cloudwatch_metric_alarm" "api_gateway_high_latency" {
  alarm_name          = "${var.project_name}-${var.environment}-api-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "IntegrationLatency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000"  # 10 seconds in milliseconds
  alarm_description   = "Critical: API Gateway latency exceeds 10 seconds"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = "provider-comparison-websocket"
  }

  alarm_actions = [aws_sns_topic.critical_alerts.arn]

  tags = merge(local.common_tags, {
    Severity = "Critical"
    Type     = "HighLatency"
  })
}

# SNS topic for critical alerts only
resource "aws_sns_topic" "critical_alerts" {
  name = "${var.project_name}-${var.environment}-critical-alerts"

  tags = merge(local.common_tags, {
    Purpose = "CriticalAlerting"
  })
}

# CloudWatch Logs Insights saved queries for cost-effective log analysis
resource "aws_cloudwatch_query_definition" "websocket_connection_analysis" {
  name = "${var.project_name}-websocket-connection-analysis"

  log_group_names = [
    "/aws/lambda/provider-comparison-connect-handler",
    "/aws/lambda/provider-comparison-results-handler"
  ]

  query_string = <<EOF
fields @timestamp, @message, @requestId
| filter @message like /connection/
| stats count() by bin(5m)
| sort @timestamp desc
EOF
}

resource "aws_cloudwatch_query_definition" "error_analysis" {
  name = "${var.project_name}-error-analysis"

  log_group_names = [
    "/aws/lambda/provider-comparison-connect-handler",
    "/aws/lambda/provider-comparison-results-handler",
    "/aws/lambda/provider-comparison-search-handler"
  ]

  query_string = <<EOF
fields @timestamp, @message, @requestId, @type
| filter @type = "ERROR" or @message like /ERROR/
| stats count() by bin(5m)
| sort @timestamp desc
| limit 100
EOF
}

resource "aws_cloudwatch_query_definition" "performance_analysis" {
  name = "${var.project_name}-performance-analysis"

  log_group_names = [
    "/aws/lambda/provider-comparison-connect-handler",
    "/aws/lambda/provider-comparison-results-handler",
    "/aws/lambda/provider-comparison-search-handler"
  ]

  query_string = <<EOF
fields @timestamp, @duration, @billedDuration, @requestId
| filter @type = "REPORT"
| stats avg(@duration), max(@duration), min(@duration) by bin(5m)
| sort @timestamp desc
EOF
}

# Log groups with minimal retention (7 days for cost optimization)
resource "aws_cloudwatch_log_group" "minimal_lambda_logs" {
  for_each = toset([
    "/aws/lambda/provider-comparison-connect-handler",
    "/aws/lambda/provider-comparison-results-handler",
    "/aws/lambda/provider-comparison-search-handler",
    "/aws/lambda/provider-comparison-authorizer"
  ])

  name              = each.key
  retention_in_days = 7  # Minimal retention for cost savings
  
  # Use AWS managed encryption instead of custom KMS keys for cost savings
  kms_key_id = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].arn : null

  tags = merge(local.common_tags, {
    Purpose   = "MinimalLogging"
    Retention = "7days"
  })
}

# API Gateway log group with minimal retention
resource "aws_cloudwatch_log_group" "api_gateway_minimal_logs" {
  name              = "API-Gateway-Execution-Logs_${aws_apigatewayv2_api.websocket_api.id}/prod"
  retention_in_days = 7  # Minimal retention for cost savings
  
  kms_key_id = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].arn : null

  tags = merge(local.common_tags, {
    Purpose   = "MinimalLogging"
    Retention = "7days"
  })
}