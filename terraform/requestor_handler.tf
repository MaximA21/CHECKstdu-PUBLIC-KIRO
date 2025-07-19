# requestor_handler.tf

resource "aws_lambda_function" "requestor_handler" {
  function_name = "${var.project_name}-${var.environment}-requestor-handler"
  role          = aws_iam_role.requestor_handler_role.arn
  handler       = "requestor_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30  # Längerer Timeout für die Verarbeitung

  filename         = "./../lambda_packages/requestor_handler.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/requestor_handler.zip")

  architectures = ["arm64"]

  environment {
    variables = {
      SQS_QUEUE_URL     = aws_sqs_queue.request_queue.url
      STATE_MACHINE_ARN = aws_sfn_state_machine.provider_workflow.arn
    }
  }

  tracing_config {
  mode = "Active"
}

  tags = {
    Name        = "${var.project_name}-requestor-handler"
    Environment = var.environment
  }
}

# IAM-Rolle für den Requestor Handler
resource "aws_iam_role" "requestor_handler_role" {
  name = "${var.project_name}-${var.environment}-requestor-handler-role"

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
    Name        = "${var.project_name}-requestor-handler-role"
    Environment = var.environment
  }
}

# IAM-Policy für den Requestor Handler
resource "aws_iam_policy" "requestor_handler_policy" {
  name        = "${var.project_name}-${var.environment}-requestor-handler-policy"
  description = "Policy for Requestor Handler Lambda"

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
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.request_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = aws_sfn_state_machine.provider_workflow.arn
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

resource "aws_iam_role_policy_attachment" "requestor_handler_policy_attachment" {
  role       = aws_iam_role.requestor_handler_role.name
  policy_arn = aws_iam_policy.requestor_handler_policy.arn
}

# SQS-Trigger für Lambda
resource "aws_lambda_event_source_mapping" "sqs_requestor_mapping" {
  event_source_arn = aws_sqs_queue.request_queue.arn
  function_name    = aws_lambda_function.requestor_handler.arn
  batch_size       = 1  # Verarbeite eine Nachricht gleichzeitig
}