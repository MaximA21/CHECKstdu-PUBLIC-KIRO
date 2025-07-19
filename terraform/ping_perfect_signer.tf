# Ping Perfect Signer Lambda Function
resource "aws_lambda_function" "ping_perfect_signer" {
  function_name = "${var.project_name}-${var.environment}-ping-perfect-signer"
  role          = aws_iam_role.ping_perfect_signer_role.arn
  handler       = "ping_perfect_signer.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10  # Just signature generation, much faster
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "./../lambda_packages/ping_perfect_signer.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/ping_perfect_signer.zip")

  environment {
    variables = {
      PING_PERFECT_CLIENT_ID = var.ping_perfect_client_id
      PING_PERFECT_SECRET    = var.ping_perfect_secret
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${var.project_name}-ping-perfect-signer"
    Environment = var.environment
    Purpose     = "hmac-signing-api-calls"
  }
}

# IAM Role for Ping Perfect Signer
resource "aws_iam_role" "ping_perfect_signer_role" {
  name = "${var.project_name}-${var.environment}-ping-perfect-signer-role"

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
    Name        = "${var.project_name}-ping-perfect-signer-role"
    Environment = var.environment
  }
}

# IAM Policy for Ping Perfect Signer
resource "aws_iam_policy" "ping_perfect_signer_policy" {
  name        = "${var.project_name}-${var.environment}-ping-perfect-signer-policy"
  description = "Policy for Ping Perfect Signer Lambda"

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
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ping_perfect_signer_policy_attachment" {
  role       = aws_iam_role.ping_perfect_signer_role.name
  policy_arn = aws_iam_policy.ping_perfect_signer_policy.arn
}