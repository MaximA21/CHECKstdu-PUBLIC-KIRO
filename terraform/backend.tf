# Terraform Backend Configuration
terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket         = "provider-comparison-terraform-state"
    key            = "terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
  }
} 