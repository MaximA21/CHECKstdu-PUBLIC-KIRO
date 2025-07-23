# GitHub OIDC Setup for AWS Deployment

This directory contains Terraform configuration for setting up GitHub Actions OIDC authentication with AWS IAM.

## Quick Start

1. **Update Configuration**
   ```bash
   # Edit terraform.tfvars
   github_repository = "your-org/your-repo"  # Your actual GitHub repository
   deployment_bucket_name = "your-unique-bucket-name"  # Must be globally unique
   ```

2. **Deploy Infrastructure**
   ```bash
   terraform init
   terraform plan -var-file="terraform.tfvars"
   terraform apply -var-file="terraform.tfvars"
   ```

3. **Get Configuration Values**
   ```bash
   terraform output github_actions_role_arn
   terraform output deployment_artifacts_bucket_name
   ```

4. **Configure GitHub Repository**
   - Go to repository Settings → Secrets and variables → Actions → Variables
   - Add `AWS_GITHUB_ACTIONS_ROLE_ARN` with the role ARN from step 3
   - Add `AWS_REGION` with value `eu-central-1`

5. **Validate Setup**
   ```bash
   python3 ../scripts/validate-github-oidc.py \
     --role-arn "$(terraform output -raw github_actions_role_arn)" \
     --oidc-provider-arn "$(terraform output -raw oidc_provider_arn)" \
     --bucket-name "$(terraform output -raw deployment_artifacts_bucket_name)" \
     --repository "your-org/your-repo"
   ```

## Files Created

- `github_oidc.tf` - OIDC provider and IAM role configuration
- `s3_deployment_artifacts.tf` - S3 bucket for deployment artifacts

## Security Features

- ✅ No long-lived AWS credentials in GitHub
- ✅ Role can only be assumed from specific repository and branch
- ✅ Least privilege permissions
- ✅ Short-lived tokens (1 hour max)
- ✅ Full audit trail in CloudTrail

## Troubleshooting

See `../docs/GITHUB_OIDC_SETUP.md` for detailed setup instructions and troubleshooting.

## Cost Impact

- IAM Role: Free
- OIDC Provider: Free  
- S3 Bucket: ~$0.02/month for typical usage
- Total: < $0.05/month