# Cost-aware alerting and monitoring for student budget (15-20 EUR/month)
# This configuration implements AWS Budget alerts and cost anomaly detection

# AWS Budget for monthly cost monitoring (15 EUR threshold)
resource "aws_budgets_budget" "monthly_student_budget" {
  name         = "${var.project_name}-${var.environment}-monthly-budget"
  budget_type  = "COST"
  limit_amount = "15"  # 15 EUR monthly limit
  limit_unit   = "EUR"
  time_unit    = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  cost_filter {
    dimension {
      key           = "Service"
      values        = [
        "Amazon API Gateway",
        "AWS Lambda",
        "Amazon DynamoDB",
        "Amazon CloudWatch",
        "Amazon Simple Notification Service",
        "Amazon Simple Queue Service",
        "AWS Step Functions"
      ]
      match_options = ["EQUALS"]
    }
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 80  # Alert at 80% of budget (12 EUR)
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 100  # Alert at 100% of budget (15 EUR)
    threshold_type            = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                 = 120  # Critical alert at 120% (18 EUR)
    threshold_type            = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
    subscriber_sns_topic_arns  = [aws_sns_topic.cost_alerts.arn]
  }

  tags = merge(local.common_tags, {
    Purpose = "CostControl"
    Budget  = "StudentBudget"
  })
}

# Cost anomaly detection for unexpected spikes
resource "aws_ce_anomaly_detector" "cost_anomaly_detector" {
  name         = "${var.project_name}-${var.environment}-cost-anomaly"
  monitor_type = "DIMENSIONAL"

  specification = jsonencode({
    Dimension = "SERVICE"
    MatchOptions = ["EQUALS"]
    Values = [
      "Amazon API Gateway",
      "AWS Lambda", 
      "Amazon DynamoDB",
      "Amazon CloudWatch"
    ]
  })

  tags = merge(local.common_tags, {
    Purpose = "CostAnomalyDetection"
  })
}

# Cost anomaly subscription for alerts
resource "aws_ce_anomaly_subscription" "cost_anomaly_subscription" {
  name      = "${var.project_name}-${var.environment}-cost-anomaly-alerts"
  frequency = "DAILY"
  
  monitor_arn_list = [
    aws_ce_anomaly_detector.cost_anomaly_detector.arn
  ]
  
  subscriber {
    type    = "EMAIL"
    address = var.budget_alert_email
  }
  
  subscriber {
    type    = "SNS"
    address = aws_sns_topic.cost_alerts.arn
  }

  threshold_expression {
    and {
      dimension {
        key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
        values        = ["5"]  # Alert on anomalies > 5 EUR
        match_options = ["GREATER_THAN_OR_EQUAL"]
      }
    }
  }

  tags = merge(local.common_tags, {
    Purpose = "CostAnomalyAlerts"
  })
}

# SNS topic for cost alerts
resource "aws_sns_topic" "cost_alerts" {
  name = "${var.project_name}-${var.environment}-cost-alerts"

  tags = merge(local.common_tags, {
    Purpose = "CostAlerting"
  })
}

# SNS topic subscription for cost alerts
resource "aws_sns_topic_subscription" "cost_alerts_email" {
  topic_arn = aws_sns_topic.cost_alerts.arn
  protocol  = "email"
  endpoint  = var.budget_alert_email
}

# CloudWatch alarm for estimated charges (backup to AWS Budget)
resource "aws_cloudwatch_metric_alarm" "estimated_charges_alarm" {
  alarm_name          = "${var.project_name}-${var.environment}-estimated-charges"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"  # Daily
  statistic           = "Maximum"
  threshold           = "15"  # 15 EUR threshold
  alarm_description   = "Estimated charges exceed 15 EUR monthly budget"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Currency = "EUR"
  }

  alarm_actions = [aws_sns_topic.cost_alerts.arn]

  tags = merge(local.common_tags, {
    Purpose  = "CostMonitoring"
    Severity = "High"
  })
}

# CloudWatch alarm for service-specific cost spikes
resource "aws_cloudwatch_metric_alarm" "lambda_cost_spike" {
  alarm_name          = "${var.project_name}-${var.environment}-lambda-cost-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = "5"  # 5 EUR for Lambda specifically
  alarm_description   = "Lambda costs exceed expected threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Currency    = "EUR"
    ServiceName = "AWSLambda"
  }

  alarm_actions = [aws_sns_topic.cost_alerts.arn]

  tags = merge(local.common_tags, {
    Purpose     = "ServiceCostMonitoring"
    ServiceName = "Lambda"
  })
}

# CloudWatch alarm for API Gateway cost spikes
resource "aws_cloudwatch_metric_alarm" "api_gateway_cost_spike" {
  alarm_name          = "${var.project_name}-${var.environment}-apigateway-cost-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = "86400"
  statistic           = "Maximum"
  threshold           = "3"  # 3 EUR for API Gateway
  alarm_description   = "API Gateway costs exceed expected threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Currency    = "EUR"
    ServiceName = "AmazonApiGateway"
  }

  alarm_actions = [aws_sns_topic.cost_alerts.arn]

  tags = merge(local.common_tags, {
    Purpose     = "ServiceCostMonitoring"
    ServiceName = "APIGateway"
  })
}

# Cost optimization dashboard
resource "aws_cloudwatch_dashboard" "cost_optimization_dashboard" {
  dashboard_name = "${var.project_name}-${var.environment}-cost-optimization"

  dashboard_body = jsonencode({
    widgets = [
      # Total estimated charges
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "Currency", "EUR"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"  # Billing metrics only in us-east-1
          title   = "Total Estimated Monthly Charges (EUR)"
          period  = 86400
          stat    = "Maximum"
          yAxis = {
            left = {
              min = 0
              max = 25
            }
          }
        }
      },
      # Service breakdown
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Billing", "EstimatedCharges", "Currency", "EUR", "ServiceName", "AWSLambda"],
            [".", ".", ".", ".", ".", "AmazonApiGateway"],
            [".", ".", ".", ".", ".", "AmazonDynamoDB"],
            [".", ".", ".", ".", ".", "AmazonCloudWatch"]
          ]
          view    = "timeSeries"
          stacked = true
          region  = "us-east-1"
          title   = "Service Cost Breakdown (EUR)"
          period  = 86400
          stat    = "Maximum"
        }
      },
      # Resource utilization metrics
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "provider-comparison-connect-handler"],
            [".", ".", ".", "provider-comparison-results-handler"],
            ["AWS/ApiGateway", "Count", "ApiName", "provider-comparison-websocket"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Resource Utilization"
          period  = 3600
          stat    = "Sum"
        }
      },
      # Cost per request estimation
      {
        type   = "metric"
        x      = 12
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
          title   = "DynamoDB Capacity Consumption"
          period  = 3600
          stat    = "Sum"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Purpose = "CostOptimization"
  })
}

# Lambda function for cost optimization recommendations
resource "aws_lambda_function" "cost_optimizer" {
  filename         = "lambda_packages/cost_optimizer.zip"
  function_name    = "${var.project_name}-${var.environment}-cost-optimizer"
  role            = aws_iam_role.cost_optimizer_role.arn
  handler         = "cost_optimizer.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60

  environment {
    variables = {
      BUDGET_THRESHOLD = "15"
      SNS_TOPIC_ARN   = aws_sns_topic.cost_alerts.arn
      PROJECT_NAME    = var.project_name
      ENVIRONMENT     = var.environment
    }
  }

  tags = merge(local.common_tags, {
    Purpose = "CostOptimization"
  })
}

# IAM role for cost optimizer Lambda
resource "aws_iam_role" "cost_optimizer_role" {
  name = "${var.project_name}-${var.environment}-cost-optimizer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# IAM policy for cost optimizer
resource "aws_iam_role_policy" "cost_optimizer_policy" {
  name = "${var.project_name}-${var.environment}-cost-optimizer-policy"
  role = aws_iam_role.cost_optimizer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetUsageReport",
          "budgets:ViewBudget",
          "sns:Publish"
        ]
        Resource = "*"
      }
    ]
  })
}

# EventBridge rule to trigger cost optimizer daily
resource "aws_cloudwatch_event_rule" "daily_cost_check" {
  name                = "${var.project_name}-${var.environment}-daily-cost-check"
  description         = "Trigger cost optimizer daily at 9 AM UTC"
  schedule_expression = "cron(0 9 * * ? *)"  # 9 AM UTC daily

  tags = merge(local.common_tags, {
    Purpose = "CostOptimization"
  })
}

# EventBridge target for cost optimizer
resource "aws_cloudwatch_event_target" "cost_optimizer_target" {
  rule      = aws_cloudwatch_event_rule.daily_cost_check.name
  target_id = "CostOptimizerTarget"
  arn       = aws_lambda_function.cost_optimizer.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge_cost_optimizer" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cost_optimizer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_cost_check.arn
}