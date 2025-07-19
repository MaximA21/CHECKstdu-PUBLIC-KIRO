# Lambda-Rolle mit Berechtigungen
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
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
    Name        = "${var.project_name}-lambda-role"
    Environment = var.environment
  }
}


# Vereinfachte Richtlinie für Lambda-Rolle
resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.project_name}-${var.environment}-lambda-policy"
  description = "Policy for Lambda functions"

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action = [
          "execute-api:ManageConnections"
        ]
        Effect   = "Allow"
        Resource = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
      },
      {
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Effect   = "Allow"
        Resource = [
          aws_sqs_queue.request_queue.arn,
          aws_sqs_queue.request_dlq.arn
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

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# Connect Handler Lambda-Funktion
resource "aws_lambda_function" "connect_handler" {
  function_name = "${var.project_name}-${var.environment}-connect-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "connect_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  architectures = ["arm64"]

  filename         = "./../lambda_packages/connect_handler.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/connect_handler.zip")

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${var.project_name}-connect-handler"
    Environment = var.environment
  }
}

# Search Handler Lambda-Funktion
resource "aws_lambda_function" "search_handler" {
  function_name = "${var.project_name}-${var.environment}-search-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "search_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  architectures = ["arm64"]

  filename         = "./../lambda_packages/search_handler.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/search_handler.zip")

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      SQS_QUEUE_URL = aws_sqs_queue.request_queue.url
    }
  }

  tags = {
    Name        = "${var.project_name}-search-handler"
    Environment = var.environment
  }
}

# Lambda-Berechtigungen für API Gateway
resource "aws_lambda_permission" "connect_permission" {
  statement_id  = "AllowExecutionFromAPIGatewayConnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*/$connect"
}
# Lambda-Berechtigungen für API Gateway
resource "aws_lambda_permission" "search_permission" {
  statement_id  = "AllowExecutionFromAPIGatewaySearch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.search_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*/search"
}