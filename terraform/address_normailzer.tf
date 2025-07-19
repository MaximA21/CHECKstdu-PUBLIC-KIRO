# Address Normalizer Lambda Function
resource "aws_lambda_function" "address_normalizer" {
  function_name = "${var.project_name}-${var.environment}-address-normalizer"
  role          = aws_iam_role.address_normalizer_role.arn
  handler       = "address_normalizer.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  memory_size   = 128  # Lightweight function
  architectures = ["arm64"]

  filename         = "./../lambda_packages/address_normalizer.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/address_normalizer.zip")

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name        = "${var.project_name}-address-normalizer"
    Environment = var.environment
    Purpose     = "german-character-normalization"
  }
}

# IAM Role for Address Normalizer
resource "aws_iam_role" "address_normalizer_role" {
  name = "${var.project_name}-${var.environment}-address-normalizer-role"

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
    Name        = "${var.project_name}-address-normalizer-role"
    Environment = var.environment
  }
}

# IAM Policy for Address Normalizer (minimal permissions)
resource "aws_iam_policy" "address_normalizer_policy" {
  name        = "${var.project_name}-${var.environment}-address-normalizer-policy"
  description = "Policy for Address Normalizer Lambda"

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

resource "aws_iam_role_policy_attachment" "address_normalizer_policy_attachment" {
  role       = aws_iam_role.address_normalizer_role.name
  policy_arn = aws_iam_policy.address_normalizer_policy.arn
}