#!/bin/bash

# Script to setup Terraform backend and migrate state
# This script should be run once to initialize the remote backend

set -e

echo "🔧 Setting up Terraform backend..."

# Step 1: Create backend resources (S3 bucket and DynamoDB table)
echo "📦 Creating backend resources..."

# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket provider-comparison-terraform-state \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1 || echo "Bucket may already exist"

# Enable versioning on S3 bucket
aws s3api put-bucket-versioning \
  --bucket provider-comparison-terraform-state \
  --versioning-configuration Status=Enabled

# Enable encryption on S3 bucket
aws s3api put-bucket-encryption \
  --bucket provider-comparison-terraform-state \
  --server-side-encryption-configuration '{
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }
    ]
  }'

# Block public access on S3 bucket
aws s3api put-public-access-block \
  --bucket provider-comparison-terraform-state \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name provider-comparison-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-central-1 || echo "DynamoDB table may already exist"

echo "✅ Backend resources created"

# Step 2: Initialize Terraform with backend
echo "🔧 Initializing Terraform with backend..."

# Remove any existing backend configuration temporarily
cp main.tf main.tf.backup
grep -v "backend" main.tf > main.tf.tmp && mv main.tf.tmp main.tf

# Initialize Terraform
terraform init

# Add backend configuration
cat >> main.tf << EOF

# Terraform Backend Configuration
terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket         = "provider-comparison-terraform-state"
    key            = "terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
    dynamodb_table = "provider-comparison-terraform-locks"
  }
}
EOF

# Re-initialize with backend
terraform init -migrate-state

echo "✅ Terraform backend initialized"

# Step 3: Import existing resources if needed
echo "📥 Importing existing resources..."

# Check if we have existing resources to import
if [[ -f "import_staging_resources.sh" ]]; then
  echo "🔄 Running import script for existing resources..."
  chmod +x import_staging_resources.sh
  ./import_staging_resources.sh || echo "Import completed with some warnings"
fi

echo "✅ Backend setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Run 'terraform plan' to verify the setup"
echo "2. Run 'terraform apply' to deploy any missing resources"
echo "3. Update GitHub Actions workflow to use the remote backend" 