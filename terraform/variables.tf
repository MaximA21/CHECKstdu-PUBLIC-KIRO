variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-central-1" # Frankfurt
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "provider-comparison"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "google_maps_api_key" {
  description = "API key for Google Maps service"
  type        = string
  sensitive   = true # Markiert als sensibel, nicht in Logs anzeigen
  default     = ""
}

# Provider API Keys for Secrets Manager
variable "byteme_api_key" {
  description = "API key for ByteMe provider"
  type        = string
  sensitive   = true
  default     = ""
}

variable "servus_speed_auth" {
  description = "Authorization header for Servus Speed (Basic auth)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "webwunder_api_key" {
  description = "API key for WebWunder provider"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ping_perfect_client_id" {
  description = "Client ID for Ping Perfect"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ping_perfect_secret" {
  description = "Secret for Ping Perfect HMAC signing"
  type        = string
  sensitive   = true
  default     = ""
}

variable "verbyndich_api_key" {
  description = "API key for VerbynDich provider"
  type        = string
  sensitive   = true
  default     = ""
}

# Canary deployment configuration variables
variable "canary_enabled" {
  description = "Enable canary deployment for REST API"
  type        = bool
  default     = true
}

variable "canary_traffic_percentage" {
  description = "Initial percentage of traffic to route to canary deployment"
  type        = number
  default     = 10
  validation {
    condition     = var.canary_traffic_percentage >= 0 && var.canary_traffic_percentage <= 100
    error_message = "Canary traffic percentage must be between 0 and 100."
  }
}

variable "rest_api_throttle_rate_limit" {
  description = "Rate limit for REST API throttling (requests per second)"
  type        = number
  default     = 500
}

variable "rest_api_throttle_burst_limit" {
  description = "Burst limit for REST API throttling"
  type        = number
  default     = 1000
}

variable "rest_api_cache_ttl" {
  description = "Cache TTL in seconds for REST API responses"
  type        = number
  default     = 300
}

# Log retention configuration variables
variable "log_retention_days" {
  description = "CloudWatch log retention period in days for API Gateway logs"
  type        = number
  default     = 7 # Reduced to 7 days for cost optimization
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

variable "lambda_log_retention_days" {
  description = "CloudWatch log retention period in days for Lambda functions"
  type        = number
  default     = 7 # Reduced to 7 days for cost optimization
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.lambda_log_retention_days)
    error_message = "Lambda log retention days must be a valid CloudWatch retention period."
  }
}

variable "step_functions_log_retention_days" {
  description = "CloudWatch log retention period in days for Step Functions"
  type        = number
  default     = 7
  validation {
    condition = contains([
      1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653
    ], var.step_functions_log_retention_days)
    error_message = "Step Functions log retention days must be a valid CloudWatch retention period."
  }
}

# Backup and disaster recovery configuration
variable "backup_retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 365
}

variable "backup_cold_storage_days" {
  description = "Number of days after which backups are moved to cold storage"
  type        = number
  default     = 30
}

# Cost optimization variables for student budget
variable "enable_kinesis_stream" {
  description = "Enable Kinesis stream for log analysis (expensive - saves ~$28/month when disabled)"
  type        = bool
  default     = false # Disabled by default for student budget
}

variable "enable_custom_kms_keys" {
  description = "Enable custom KMS keys (saves ~$2/month when disabled, uses AWS managed keys)"
  type        = bool
  default     = false # Disabled by default for student budget
}

variable "enable_aws_backup" {
  description = "Enable AWS Backup service (saves ~$20-50/month when disabled, uses DynamoDB PITR only)"
  type        = bool
  default     = false # Disabled by default for student budget
}

variable "minimal_cloudwatch_alarms" {
  description = "Use minimal CloudWatch alarms only (saves ~$3-5/month)"
  type        = bool
  default     = true # Enabled by default for student budget
}

variable "monthly_cost_alert_threshold" {
  description = "Monthly cost threshold for alerts in USD"
  type        = number
  default     = 100
}

variable "monthly_cost_limit_threshold" {
  description = "Monthly cost hard limit threshold in USD"
  type        = number
  default     = 150
}

variable "budget_alert_email" {
  description = "Email address for budget and cost alerts"
  type        = string
  default     = "admin@example.com"
}

# GitHub OIDC configuration variables
variable "github_repository" {
  description = "GitHub repository in format 'owner/repo' for OIDC trust relationship"
  type        = string
  default     = "your-org/your-repo" # Replace with actual repository
}

variable "deployment_bucket_name" {
  description = "S3 bucket name for storing deployment artifacts"
  type        = string
  default     = "github-actions-deployment-artifacts"
}

variable "lambda_package_path" {
  description = "Path to lambda packages directory"
  type        = string
  default     = "../lambda_packages"
}

variable "skip_lambda_package_validation" {
  description = "Skip lambda package file validation (for terraform validate in CI)"
  type        = bool
  default     = false
}