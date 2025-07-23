# S3 bucket for GitHub Actions deployment artifacts

resource "aws_s3_bucket" "deployment_artifacts" {
  bucket = "${var.project_name}-${var.environment}-deployment-artifacts-${random_id.bucket_suffix.hex}"

  tags = {
    Name        = "deployment-artifacts"
    Environment = var.environment
    Project     = "production-deployment-pipeline"
  }
}

# Random ID for bucket name uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "deployment_artifacts" {
  bucket = aws_s3_bucket.deployment_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "deployment_artifacts" {
  bucket = aws_s3_bucket.deployment_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "deployment_artifacts" {
  bucket = aws_s3_bucket.deployment_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket lifecycle configuration to manage costs
resource "aws_s3_bucket_lifecycle_configuration" "deployment_artifacts" {
  bucket = aws_s3_bucket.deployment_artifacts.id

  rule {
    id     = "deployment_artifacts_lifecycle"
    status = "Enabled"

    # Apply to all objects in the bucket
    filter {
      prefix = ""
    }

    # Delete old versions after 30 days
    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    # Delete incomplete multipart uploads after 7 days
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    # Move to IA after 30 days, then to Glacier after 90 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Delete objects after 1 year
    expiration {
      days = 365
    }
  }
}

# Output handled in outputs.tf to avoid duplication