# WebSocket Traffic Distribution Configuration
# This file implements 50/50 traffic distribution between old and new implementations

# DynamoDB table for connection routing tracking with enhanced fields
resource "aws_dynamodb_table" "connection_routing" {
  name         = "${var.project_name}-${var.environment}-connection-routing"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connection_id"

  attribute {
    name = "connection_id"
    type = "S"
  }

  attribute {
    name = "implementation"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  # Global secondary index for querying by implementation
  global_secondary_index {
    name            = "implementation-index"
    hash_key        = "implementation"
    projection_type = "ALL"
  }

  # Global secondary index for querying by status
  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    projection_type = "ALL"
  }

  # TTL for automatic cleanup of old connection records
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name                = "${var.project_name}-connection-routing"
    Environment         = var.environment
    TrafficDistribution = "enabled"
    ConnectionTracking  = "enabled"
  }
}

# Connection router Lambda function is defined in lambda_minimal.tf

# IAM role for connection router
resource "aws_iam_role" "connection_router_role" {
  name = "${var.project_name}-${var.environment}-connection-router-role"

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

  tags = {
    Name        = "${var.project_name}-connection-router-role"
    Environment = var.environment
  }
}

# IAM policy for connection router
resource "aws_iam_policy" "connection_router_policy" {
  name        = "${var.project_name}-${var.environment}-connection-router-policy"
  description = "Policy for Connection Router Lambda"

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
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.connection_routing.arn
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.connect_handler.arn,
          aws_lambda_function.connect_handler_old.arn,
          aws_lambda_function.search_handler.arn,
          aws_lambda_function.search_handler_old.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "connection_router_policy_attachment" {
  role       = aws_iam_role.connection_router_role.name
  policy_arn = aws_iam_policy.connection_router_policy.arn
}

# Lambda permission for connection router
resource "aws_lambda_permission" "connection_router_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connection_router.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
}

# Create old implementation Lambda functions (copies of current ones)
resource "aws_lambda_function" "connect_handler_old" {
  function_name = "${var.project_name}-${var.environment}-connect-handler-old"
  role          = aws_iam_role.lambda_role.arn
  handler       = "connect_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  architectures = ["arm64"]

  filename         = "./../lambda_packages/connect_handler.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/connect_handler.zip")

  environment {
    variables = {
      IMPLEMENTATION_VERSION = "old"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${var.project_name}-connect-handler-old"
    Environment = var.environment
    Version     = "old"
  }
}

resource "aws_lambda_function" "search_handler_old" {
  function_name = "${var.project_name}-${var.environment}-search-handler-old"
  role          = aws_iam_role.lambda_role.arn
  handler       = "search_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  architectures = ["arm64"]

  filename         = "./../lambda_packages/search_handler.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/search_handler.zip")

  environment {
    variables = {
      SQS_QUEUE_URL          = aws_sqs_queue.request_queue.url
      IMPLEMENTATION_VERSION = "old"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${var.project_name}-search-handler-old"
    Environment = var.environment
    Version     = "old"
  }
}

# Lambda permissions for old implementations
resource "aws_lambda_permission" "connect_handler_old_permission" {
  statement_id  = "AllowExecutionFromConnectionRouter"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect_handler_old.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.connection_router.arn
}

resource "aws_lambda_permission" "search_handler_old_permission" {
  statement_id  = "AllowExecutionFromConnectionRouter"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.search_handler_old.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.connection_router.arn
}

# Lambda permissions for new implementations (to be invoked by router)
resource "aws_lambda_permission" "connect_handler_new_permission" {
  statement_id  = "AllowExecutionFromConnectionRouter"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect_handler.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.connection_router.arn
}

resource "aws_lambda_permission" "search_handler_new_permission" {
  statement_id  = "AllowExecutionFromConnectionRouter"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.search_handler.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.connection_router.arn
}

# CloudWatch dashboard for traffic distribution monitoring
resource "aws_cloudwatch_dashboard" "websocket_traffic_distribution" {
  dashboard_name = "${var.project_name}-${var.environment}-websocket-traffic"

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
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.connect_handler.function_name],
            [".", ".", ".", aws_lambda_function.connect_handler_old.function_name],
            [".", ".", ".", aws_lambda_function.search_handler.function_name],
            [".", ".", ".", aws_lambda_function.search_handler_old.function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "WebSocket Handler Invocations"
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
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.connect_handler.function_name],
            [".", ".", ".", aws_lambda_function.connect_handler_old.function_name],
            [".", ".", ".", aws_lambda_function.search_handler.function_name],
            [".", ".", ".", aws_lambda_function.search_handler_old.function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "WebSocket Handler Errors"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.connect_handler.function_name],
            [".", ".", ".", aws_lambda_function.connect_handler_old.function_name],
            [".", ".", ".", aws_lambda_function.search_handler.function_name],
            [".", ".", ".", aws_lambda_function.search_handler_old.function_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "WebSocket Handler Duration"
          period  = 300
        }
      }
    ]
  })
}

# CloudWatch alarms for traffic distribution monitoring
resource "aws_cloudwatch_metric_alarm" "websocket_error_rate_new" {
  alarm_name          = "${var.project_name}-${var.environment}-websocket-error-rate-new"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors error rate for new WebSocket implementation"
  alarm_actions       = []

  dimensions = {
    FunctionName = aws_lambda_function.connect_handler.function_name
  }

  tags = {
    Name        = "${var.project_name}-websocket-error-rate-new"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "websocket_error_rate_old" {
  alarm_name          = "${var.project_name}-${var.environment}-websocket-error-rate-old"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors error rate for old WebSocket implementation"
  alarm_actions       = []

  dimensions = {
    FunctionName = aws_lambda_function.connect_handler_old.function_name
  }

  tags = {
    Name        = "${var.project_name}-websocket-error-rate-old"
    Environment = var.environment
  }
}
# Connection limit enforcer Lambda function is defined in lambda_minimal.tf

# IAM role for connection limit enforcer
resource "aws_iam_role" "connection_limit_enforcer_role" {
  name = "${var.project_name}-${var.environment}-connection-limit-enforcer-role"

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

  tags = {
    Name        = "${var.project_name}-connection-limit-enforcer-role"
    Environment = var.environment
  }
}

# IAM policy for connection limit enforcer
resource "aws_iam_policy" "connection_limit_enforcer_policy" {
  name        = "${var.project_name}-${var.environment}-connection-limit-enforcer-policy"
  description = "Policy for Connection Limit Enforcer Lambda"

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
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.connection_routing.arn,
          "${aws_dynamodb_table.connection_routing.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "connection_limit_enforcer_policy_attachment" {
  role       = aws_iam_role.connection_limit_enforcer_role.name
  policy_arn = aws_iam_policy.connection_limit_enforcer_policy.arn
}

# EventBridge rule to trigger connection limit enforcer every minute
resource "aws_cloudwatch_event_rule" "connection_limit_enforcement" {
  name                = "${var.project_name}-${var.environment}-connection-limit-enforcement"
  description         = "Trigger connection limit enforcement every minute"
  schedule_expression = "rate(1 minute)"

  tags = {
    Name        = "${var.project_name}-connection-limit-enforcement"
    Environment = var.environment
  }
}

# EventBridge target for connection limit enforcer
resource "aws_cloudwatch_event_target" "connection_limit_enforcement_target" {
  rule      = aws_cloudwatch_event_rule.connection_limit_enforcement.name
  target_id = "ConnectionLimitEnforcementTarget"
  arn       = aws_lambda_function.connection_limit_enforcer.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "connection_limit_enforcer_eventbridge_permission" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connection_limit_enforcer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.connection_limit_enforcement.arn
}

# EventBridge rule for cleanup (every 5 minutes)
resource "aws_cloudwatch_event_rule" "connection_cleanup" {
  name                = "${var.project_name}-${var.environment}-connection-cleanup"
  description         = "Trigger connection cleanup every 5 minutes"
  schedule_expression = "rate(5 minutes)"

  tags = {
    Name        = "${var.project_name}-connection-cleanup"
    Environment = var.environment
  }
}

# EventBridge target for connection cleanup
resource "aws_cloudwatch_event_target" "connection_cleanup_target" {
  rule      = aws_cloudwatch_event_rule.connection_cleanup.name
  target_id = "ConnectionCleanupTarget"
  arn       = aws_lambda_function.connection_limit_enforcer.arn

  input = jsonencode({
    "handler" : "cleanup"
  })
}

# Lambda permission for cleanup EventBridge
resource "aws_lambda_permission" "connection_cleanup_eventbridge_permission" {
  statement_id  = "AllowExecutionFromEventBridgeCleanup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connection_limit_enforcer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.connection_cleanup.arn
}