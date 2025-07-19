# Results Handler Lambda Function
resource "aws_lambda_function" "results_handler" {
  function_name = "${var.project_name}-${var.environment}-results-handler"
  role          = aws_iam_role.results_handler_role.arn
  handler       = "results_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 512

  filename         = "./../lambda_packages/results_handler.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/results_handler.zip")

  architectures = ["arm64"]

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn,
    aws_lambda_layer_version.polars_layer_arm64.arn
  ]

  environment {
    variables = {
      WEBSOCKET_API_ENDPOINT = "${aws_apigatewayv2_api.websocket_api.id}.execute-api.${var.aws_region}.amazonaws.com/prod"
      RESULTS_TABLE_NAME     = aws_dynamodb_table.provider_results.name
      ANALYTICS_TABLE_NAME   = aws_dynamodb_table.analytics.name
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${var.project_name}-results-handler"
    Environment = var.environment
  }
}

# IAM Role for Results Handler
resource "aws_iam_role" "results_handler_role" {
  name = "${var.project_name}-${var.environment}-results-handler-role"

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
    Name        = "${var.project_name}-results-handler-role"
    Environment = var.environment
  }
}

# IAM Policy for Results Handler
resource "aws_iam_policy" "results_handler_policy" {
  name        = "${var.project_name}-${var.environment}-results-handler-policy"
  description = "Policy for Results Handler Lambda"

  policy = jsonencode({
    Version   = "2012-10-17"
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
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.results_queue.arn
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

resource "aws_iam_role_policy_attachment" "results_handler_policy_attachment" {
  role       = aws_iam_role.results_handler_role.name
  policy_arn = aws_iam_policy.results_handler_policy.arn
}

# SQS Trigger for Results Handler
resource "aws_lambda_event_source_mapping" "results_sqs_trigger" {
  event_source_arn = aws_sqs_queue.results_queue.arn
  function_name    = aws_lambda_function.results_handler.arn
  batch_size       = 1  # Process one result at a time
}