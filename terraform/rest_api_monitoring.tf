# CloudWatch monitoring and alarms for REST API canary deployment

# CloudWatch dashboard for REST API monitoring
resource "aws_cloudwatch_dashboard" "rest_api_canary_dashboard" {
  dashboard_name = "${var.project_name}-${var.environment}-rest-api-canary"

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
            ["AWS/ApiGateway", "Count", "ApiName", aws_api_gateway_rest_api.rest_api.name, "Stage", "prod"],
            [".", "4XXError", ".", ".", ".", "."],
            [".", "5XXError", ".", ".", ".", "."],
            ["AWS/ApiGateway", "Count", "ApiName", aws_api_gateway_rest_api.rest_api.name, "Stage", "staging"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "API Gateway Request Count and Errors"
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
            ["AWS/ApiGateway", "Latency", "ApiName", aws_api_gateway_rest_api.rest_api.name, "Stage", "prod"],
            ["AWS/ApiGateway", "Latency", "ApiName", aws_api_gateway_rest_api.rest_api.name, "Stage", "staging"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "API Gateway Latency"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.share_api_new.function_name],
            [".", "Errors", ".", "."],
            [".", "Invocations", ".", "."],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.share_api_old.function_name],
            [".", "Errors", ".", "."],
            [".", "Invocations", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Function Metrics (New vs Old)"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", aws_lambda_function.share_api_new.function_name],
            ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", aws_lambda_function.share_api_old.function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Concurrent Executions"
          period  = 300
        }
      }
    ]
  })


}

# CloudWatch alarm for high error rate in production
resource "aws_cloudwatch_metric_alarm" "rest_api_high_error_rate" {
  alarm_name          = "${var.project_name}-${var.environment}-rest-api-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors REST API 4XX error rate"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]

  dimensions = {
    ApiName = aws_api_gateway_rest_api.rest_api.name
    Stage   = "prod"
  }

  tags = {
    Name        = "${var.project_name}-rest-api-high-error-rate"
    Environment = var.environment
  }
}

# CloudWatch alarm for high latency
resource "aws_cloudwatch_metric_alarm" "rest_api_high_latency" {
  alarm_name          = "${var.project_name}-${var.environment}-rest-api-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = "300"
  statistic           = "Average"
  threshold           = "5000" # 5 seconds
  alarm_description   = "This metric monitors REST API latency"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]

  dimensions = {
    ApiName = aws_api_gateway_rest_api.rest_api.name
    Stage   = "prod"
  }

  tags = {
    Name        = "${var.project_name}-rest-api-high-latency"
    Environment = var.environment
  }
}

# CloudWatch alarm for Lambda function errors (new implementation)
resource "aws_cloudwatch_metric_alarm" "share_api_new_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-share-api-new-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors errors in new share API implementation"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.share_api_new.function_name
  }

  tags = {
    Name           = "${var.project_name}-share-api-new-errors"
    Environment    = var.environment
    Implementation = "new"
  }
}

# CloudWatch alarm for Lambda function errors (old implementation)
resource "aws_cloudwatch_metric_alarm" "share_api_old_errors" {
  alarm_name          = "${var.project_name}-${var.environment}-share-api-old-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "This metric monitors errors in old share API implementation"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.share_api_old.function_name
  }

  tags = {
    Name           = "${var.project_name}-share-api-old-errors"
    Environment    = var.environment
    Implementation = "old"
  }
}

# SNS topic for deployment alerts
resource "aws_sns_topic" "deployment_alerts" {
  name = "${var.project_name}-${var.environment}-deployment-alerts"

  tags = {
    Name        = "${var.project_name}-deployment-alerts"
    Environment = var.environment
  }
}

# Custom CloudWatch metric for canary deployment tracking
resource "aws_cloudwatch_log_metric_filter" "canary_traffic_split" {
  name           = "${var.project_name}-canary-traffic-split"
  log_group_name = aws_cloudwatch_log_group.rest_api_logs.name
  pattern        = "[timestamp, request_id, ip, request_time, http_method, resource_path, status, protocol, response_length, stage, error_message, canary_stage, implementation, traffic_split]"

  metric_transformation {
    name      = "CanaryTrafficSplit"
    namespace = "Custom/APIGateway"
    value     = "$traffic_split"
  }
}

# Custom CloudWatch metric for implementation tracking
resource "aws_cloudwatch_log_metric_filter" "implementation_requests" {
  name           = "${var.project_name}-implementation-requests"
  log_group_name = aws_cloudwatch_log_group.rest_api_logs.name
  pattern        = "[timestamp, request_id, ip, request_time, http_method, resource_path, status, protocol, response_length, stage, error_message, canary_stage, implementation=\"new\", traffic_split]"

  metric_transformation {
    name      = "NewImplementationRequests"
    namespace = "Custom/APIGateway"
    value     = "1"
  }
}

# CloudWatch alarm for canary deployment rollback trigger
resource "aws_cloudwatch_metric_alarm" "canary_rollback_trigger" {
  alarm_name          = "${var.project_name}-${var.environment}-canary-rollback-trigger"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "3"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "Trigger rollback if new implementation has too many errors"
  alarm_actions       = [aws_sns_topic.deployment_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.share_api_new.function_name
  }

  tags = {
    Name        = "${var.project_name}-canary-rollback-trigger"
    Environment = var.environment
    Purpose     = "rollback-trigger"
  }
}