resource "aws_apigatewayv2_api" "rest_api" {
  name          = "${var.project_name}-${var.environment}-rest-api"
  protocol_type = "HTTP"
  description   = "REST API for share links"

  cors_configuration {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "OPTIONS"]
    allow_headers     = ["content-type"]
    expose_headers    = ["*"]
    max_age          = 300
  }

  tags = {
    Name        = "${var.project_name}-rest-api"
    Environment = var.environment
  }
}

# Lambda function for share API
resource "aws_lambda_function" "share_api" {
  function_name = "${var.project_name}-${var.environment}-share-api"
  role          = aws_iam_role.share_api_role.arn
  handler       = "share_api.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  memory_size   = 256  # Lightweight function
  architectures = ["arm64"]

  filename         = "./../lambda_packages/share_api.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/share_api.zip")

  environment {
    variables = {
      RESULTS_TABLE_NAME = aws_dynamodb_table.provider_results.name
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name         = "${var.project_name}-share-api"
    Environment  = var.environment
    Architecture = "arm64"
  }
}

# Separate IAM role for share API (minimal permissions)
resource "aws_iam_role" "share_api_role" {
  name = "${var.project_name}-${var.environment}-share-api-role"

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
    Name        = "${var.project_name}-share-api-role"
    Environment = var.environment
  }
}

# IAM policy for share API (read-only DynamoDB access)
resource "aws_iam_policy" "share_api_policy" {
  name        = "${var.project_name}-${var.environment}-share-api-policy"
  description = "Policy for Share API Lambda"

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
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.provider_results.arn,
          "${aws_dynamodb_table.provider_results.arn}/index/*"
        ]
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

resource "aws_iam_role_policy_attachment" "share_api_policy_attachment" {
  role       = aws_iam_role.share_api_role.name
  policy_arn = aws_iam_policy.share_api_policy.arn
}

# Routes for REST API
resource "aws_apigatewayv2_route" "share_route" {
  api_id    = aws_apigatewayv2_api.rest_api.id
  route_key = "GET /share/{share_token}"
  target    = "integrations/${aws_apigatewayv2_integration.share_integration.id}"
}

# Integration
resource "aws_apigatewayv2_integration" "share_integration" {
  api_id           = aws_apigatewayv2_api.rest_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.share_api.invoke_arn
}

# Lambda permission for REST API
resource "aws_lambda_permission" "share_api_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.share_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rest_api.execution_arn}/*/*"
}

# Deploy REST API
resource "aws_apigatewayv2_stage" "rest_api_prod" {
  api_id      = aws_apigatewayv2_api.rest_api.id
  name        = "prod"
  auto_deploy = true

  # Enable logging for REST API
  default_route_settings {
    detailed_metrics_enabled = true
    throttling_burst_limit   = 100
    throttling_rate_limit    = 50
  }

  tags = {
    Name        = "${var.project_name}-rest-api-prod"
    Environment = var.environment
  }
}

# Outputs for the REST API URLs
output "rest_api_url" {
  description = "REST API Gateway URL"
  value       = aws_apigatewayv2_api.rest_api.api_endpoint
}

output "share_api_url" {
  description = "Share link API URL"
  value       = "${aws_apigatewayv2_api.rest_api.api_endpoint}/prod/share"
}

output "websocket_api_url" {
  description = "WebSocket API URL"
  value       = "wss://${aws_apigatewayv2_api.websocket_api.id}.execute-api.${var.aws_region}.amazonaws.com/prod"
}