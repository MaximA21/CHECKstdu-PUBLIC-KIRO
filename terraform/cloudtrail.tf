# Basic CloudTrail for audit logging (cost-optimized)
# This provides essential audit logging without expensive features

# S3 bucket for CloudTrail logs
resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket        = "${var.project_name}-${var.environment}-cloudtrail-logs-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = merge(local.common_tags, {
    Name       = "${var.project_name}-${var.environment}-cloudtrail-logs"
    Purpose    = "CloudTrail audit logging"
    CostCenter = "Security"
  })
}

# S3 bucket versioning (disabled for cost optimization)
resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  versioning_configuration {
    status = "Disabled" # Disabled to reduce costs
  }
}

# S3 bucket encryption (using AWS managed keys for cost optimization)
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # AWS managed encryption instead of KMS for cost savings
    }
  }
}

# S3 bucket lifecycle configuration for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    id     = "cloudtrail_log_lifecycle"
    status = "Enabled"

    filter {
      prefix = ""
    }

    # Delete logs after 90 days to control costs
    expiration {
      days = 90
    }

    # Transition to IA after 30 days for cost savings
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Transition to Glacier after 60 days for further cost savings
    transition {
      days          = 60
      storage_class = "GLACIER"
    }
  }
}

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket policy for CloudTrail
resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail_logs.arn
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = "arn:aws:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${var.project_name}-${var.environment}-basic-trail"
          }
        }
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudtrail_logs.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"  = "bucket-owner-full-control"
            "AWS:SourceArn" = "arn:aws:cloudtrail:${var.aws_region}:${data.aws_caller_identity.current.account_id}:trail/${var.project_name}-${var.environment}-basic-trail"
          }
        }
      }
    ]
  })
}

# Basic CloudTrail (management events only for cost optimization)
resource "aws_cloudtrail" "basic_trail" {
  name           = "${var.project_name}-${var.environment}-basic-trail"
  s3_bucket_name = aws_s3_bucket.cloudtrail_logs.bucket

  # Basic configuration for cost optimization
  include_global_service_events = true
  is_multi_region_trail         = false # Single region to reduce costs
  enable_logging                = true

  # Management events only (no data events to reduce costs)
  event_selector {
    read_write_type                  = "All"
    include_management_events        = true
    exclude_management_event_sources = []

    # No data events configured to keep costs low
  }

  # No CloudWatch Logs integration to avoid additional costs
  # cloud_watch_logs_group_arn = null
  # cloud_watch_logs_role_arn  = null

  tags = merge(local.common_tags, {
    Name       = "${var.project_name}-${var.environment}-basic-trail"
    Purpose    = "Basic audit logging"
    CostCenter = "Security"
    Tier       = "Basic"
  })

  depends_on = [aws_s3_bucket_policy.cloudtrail_logs]
}

# Random string for S3 bucket suffix
resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# AWS account ID is available from main.tf data source