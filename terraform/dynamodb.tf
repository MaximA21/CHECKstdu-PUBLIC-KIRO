# dynamodb.tf - Database for storing results and analytics

# Main table for search results and sessions
resource "aws_dynamodb_table" "provider_results" {
  name         = "${var.project_name}-${var.environment}-results"
  billing_mode = "PAY_PER_REQUEST" # Serverless pricing
  hash_key     = "request_id"
  range_key    = "provider_name"

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
    type = "S" # Format: YYYY-MM-DD
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

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption (use AWS managed keys for cost optimization)
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.enable_custom_kms_keys && var.enable_aws_backup ? (length(aws_kms_key.backup_key) > 0 ? aws_kms_key.backup_key[0].arn : null) : null
  }

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-results-table"
    Environment = var.environment
    BackupPolicy = var.enable_aws_backup ? "enabled" : "disabled"
  })
}

# Analytics table for aggregated data
resource "aws_dynamodb_table" "analytics" {
  name         = "${var.project_name}-${var.environment}-analytics"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "metric_type"
  range_key    = "time_period"

  attribute {
    name = "metric_type"
    type = "S" # e.g., "daily_searches", "provider_performance"
  }

  attribute {
    name = "time_period"
    type = "S" # e.g., "2025-05-29", "2025-05-W22"
  }

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption (use AWS managed keys for cost optimization)
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.enable_custom_kms_keys && var.enable_aws_backup ? (length(aws_kms_key.backup_key) > 0 ? aws_kms_key.backup_key[0].arn : null) : null
  }

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-analytics-table"
    Environment = var.environment
    BackupPolicy = var.enable_aws_backup ? "enabled" : "disabled"
  })
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

# DynamoDB access is now included in the main lambda_policy in lambda_minimal.tf

# AWS Backup Service (conditional - expensive, saves ~$20-50/month when disabled)
resource "aws_backup_vault" "dynamodb_backup_vault" {
  count = var.enable_aws_backup ? 1 : 0
  
  name        = "${var.project_name}-${var.environment}-dynamodb-backup-vault"
  kms_key_arn = var.enable_custom_kms_keys ? aws_kms_key.backup_key[0].arn : null

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-dynamodb-backup-vault"
  })
}

# KMS key for backup encryption (conditional)
resource "aws_kms_key" "backup_key" {
  count = var.enable_aws_backup && var.enable_custom_kms_keys ? 1 : 0
  
  description             = "KMS key for DynamoDB backup encryption"
  deletion_window_in_days = 7

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-backup-key"
  })
}

resource "aws_kms_alias" "backup_key_alias" {
  count = var.enable_aws_backup && var.enable_custom_kms_keys ? 1 : 0
  
  name          = "alias/${var.project_name}-${var.environment}-backup-key"
  target_key_id = aws_kms_key.backup_key[0].key_id
}

# IAM role for AWS Backup (conditional)
resource "aws_iam_role" "backup_role" {
  count = var.enable_aws_backup ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "backup_policy" {
  count = var.enable_aws_backup ? 1 : 0
  
  role       = aws_iam_role.backup_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "restore_policy" {
  count = var.enable_aws_backup ? 1 : 0
  
  role       = aws_iam_role.backup_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

# Backup plan for DynamoDB tables (conditional)
resource "aws_backup_plan" "dynamodb_backup_plan" {
  count = var.enable_aws_backup ? 1 : 0
  
  name = "${var.project_name}-${var.environment}-dynamodb-backup-plan"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.dynamodb_backup_vault[0].name
    schedule          = "cron(0 2 * * ? *)" # Daily at 2 AM UTC

    lifecycle {
      cold_storage_after = var.backup_cold_storage_days
      delete_after       = var.backup_retention_days
    }

    recovery_point_tags = merge(local.common_tags, {
      BackupType = "daily"
    })
  }

  tags = local.common_tags
}

# Backup selection for DynamoDB tables (conditional)
resource "aws_backup_selection" "dynamodb_backup_selection" {
  count = var.enable_aws_backup ? 1 : 0
  
  iam_role_arn = aws_iam_role.backup_role[0].arn
  name         = "${var.project_name}-${var.environment}-dynamodb-backup-selection"
  plan_id      = aws_backup_plan.dynamodb_backup_plan[0].id

  resources = [
    aws_dynamodb_table.provider_results.arn,
    aws_dynamodb_table.analytics.arn
  ]

  condition {
    string_equals {
      key   = "aws:ResourceTag/BackupPolicy"
      value = "enabled"
    }
  }
}