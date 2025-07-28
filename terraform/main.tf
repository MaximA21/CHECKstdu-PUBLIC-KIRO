# Main Terraform configuration for WebSocket API Gateway with traffic distribution
terraform {
  required_version = ">= 1.0"
}

# Data source for current AWS account ID
data "aws_caller_identity" "current" {}

# Data source for current AWS region
data "aws_region" "current" {}

# Local values for common configurations
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  # Common tags for all resources
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Region      = var.aws_region
  }

  # WebSocket API configuration
  websocket_api_name = "${var.project_name}-${var.environment}-websocket"

  # Traffic distribution configuration
  traffic_split_percentage = 50 # 50% to new implementation

  # Connection limits configuration
  connection_timeout_minutes = 2
  max_results_per_connection = 5
}
