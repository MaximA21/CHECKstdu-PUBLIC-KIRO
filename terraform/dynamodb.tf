# dynamodb.tf - Database for storing results and analytics

# Main table for search results and sessions
resource "aws_dynamodb_table" "provider_results" {
  name           = "${var.project_name}-${var.environment}-results"
  billing_mode   = "PAY_PER_REQUEST"  # Serverless pricing
  hash_key       = "request_id"
  range_key      = "provider_name"

  # Core attributes
  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "provider_name"
    type = "S"
  }

  # For share links - GSI
  attribute {
    name = "share_token"
    type = "S"
  }

  # For user sessions - GSI
  attribute {
    name = "session_id"
    type = "S"
  }

  # For analytics by date - GSI
  attribute {
    name = "search_date"
    type = "S"  # Format: YYYY-MM-DD
  }

  # Global Secondary Index for share links
  global_secondary_index {
    name            = "ShareTokenIndex"
    hash_key        = "share_token"
    projection_type = "ALL"
  }

  # Global Secondary Index for user sessions
  global_secondary_index {
    name            = "SessionIndex"
    hash_key        = "session_id"
    range_key       = "request_id"
    projection_type = "ALL"
  }

  # Global Secondary Index for analytics
  global_secondary_index {
    name            = "AnalyticsIndex"
    hash_key        = "search_date"
    range_key       = "request_id"
    projection_type = "KEYS_ONLY"
  }

  # TTL for automatic cleanup (optional)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-results-table"
    Environment = var.environment
  }
}

# Analytics table for aggregated data
resource "aws_dynamodb_table" "analytics" {
  name           = "${var.project_name}-${var.environment}-analytics"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "metric_type"
  range_key      = "time_period"

  attribute {
    name = "metric_type"
    type = "S"  # e.g., "daily_searches", "provider_performance"
  }

  attribute {
    name = "time_period"
    type = "S"  # e.g., "2025-05-29", "2025-05-W22"
  }

  tags = {
    Name        = "${var.project_name}-analytics-table"
    Environment = var.environment
  }
}

# IAM permissions for Lambda functions to access DynamoDB
resource "aws_iam_policy" "dynamodb_access" {
  name        = "${var.project_name}-${var.environment}-dynamodb-access"
  description = "Policy for Lambda functions to access DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.provider_results.arn,
          "${aws_dynamodb_table.provider_results.arn}/index/*",
          aws_dynamodb_table.analytics.arn,
          "${aws_dynamodb_table.analytics.arn}/index/*"
        ]
      }
    ]
  })
}

# Attach policy to existing Lambda roles
resource "aws_iam_role_policy_attachment" "results_handler_dynamodb" {
  role       = aws_iam_role.results_handler_role.name
  policy_arn = aws_iam_policy.dynamodb_access.arn
}