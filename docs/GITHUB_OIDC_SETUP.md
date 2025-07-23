# GitHub OIDC with AWS IAM Setup Guide

This guide explains how to set up GitHub Actions OIDC authentication with AWS IAM for secure, keyless deployments.

## Overview

GitHub OIDC (OpenID Connect) allows GitHub Actions to authenticate with AWS without storing long-lived access keys as secrets. This provides better security through:

- **No long-lived credentials**: No AWS access keys stored in GitHub secrets
- **Least privilege access**: IAM roles with minimal required permissions
- **Audit trail**: All actions are logged with proper identity attribution
- **Automatic token rotation**: OIDC tokens are short-lived and automatically managed

## Prerequisites

- AWS CLI configured with administrative permissions
- Terraform installed (version 1.5.0 or later)
- GitHub repository with Actions enabled
- Repository admin access to configure variables

## Step 1: Deploy AWS Infrastructure

1. **Update Terraform Variables**

   Edit `terraform/terraform.tfvars` and set the GitHub repository:

   ```hcl
   github_repository = "your-org/your-repo"  # Replace with your actual repository
   deployment_bucket_name = "your-unique-bucket-name"  # Must be globally unique
   ```

2. **Deploy the OIDC Infrastructure**

   ```bash
   cd terraform
   terraform init
   terraform plan -var-file="terraform.tfvars"
   terraform apply -var-file="terraform.tfvars"
   ```

3. **Note the Outputs**

   After deployment, note these important outputs:
   ```bash
   terraform output github_actions_role_arn
   terraform output oidc_provider_arn
   terraform output deployment_artifacts_bucket_name
   ```

## Step 2: Configure GitHub Repository

1. **Set Repository Variables**

   Go to your GitHub repository → Settings → Secrets and variables → Actions → Variables tab

   Add these repository variables:
   - `AWS_GITHUB_ACTIONS_ROLE_ARN`: The role ARN from Terraform output
   - `AWS_REGION`: `eu-central-1`

2. **Verify Branch Protection**

   Ensure the `kiro-rewrite` branch exists and is the target branch for deployments.

## Step 3: Test the Setup

1. **Trigger a Test Deployment**

   Push a commit to the `kiro-rewrite` branch or manually trigger the deployment workflow:

   ```bash
   git checkout kiro-rewrite
   git commit --allow-empty -m "Test OIDC deployment"
   git push origin kiro-rewrite
   ```

2. **Monitor the Workflow**

   Check the GitHub Actions tab to see if the workflow can successfully authenticate with AWS.

## Security Configuration Details

### IAM Role Trust Policy

The IAM role trusts GitHub Actions from your specific repository and branch:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
      },
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:your-org/your-repo:ref:refs/heads/kiro-rewrite"
        }
      }
    }
  ]
}
```

### Permissions Granted

The GitHub Actions role has the following permissions:

- **Lambda Functions**: Create, update, and manage Lambda functions and layers
- **API Gateway**: Deploy and configure REST and WebSocket APIs
- **CloudFormation**: Manage infrastructure stacks
- **S3**: Read/write deployment artifacts
- **CloudWatch Logs**: Create and manage log groups
- **IAM**: Read-only access for validation

### Security Best Practices

1. **Branch Restriction**: The role can only be assumed from the `kiro-rewrite` branch
2. **Repository Restriction**: Only your specific GitHub repository can assume the role
3. **Minimal Permissions**: Only the permissions required for deployment are granted
4. **AWS Managed Policies**: Uses AWS managed policies where possible to reduce maintenance
5. **Short-lived Tokens**: OIDC tokens expire automatically (1 hour max)

## Troubleshooting

### Common Issues

1. **"No permission to assume role" Error**
   - Verify the `github_repository` variable matches your repository exactly
   - Ensure you're deploying from the `kiro-rewrite` branch
   - Check that the OIDC provider thumbprints are current

2. **"Invalid identity token" Error**
   - Verify the repository variables are set correctly
   - Ensure the workflow has `id-token: write` permission
   - Check that the branch name matches the trust policy

3. **"Access denied" for AWS Resources**
   - Review the IAM policies attached to the role
   - Ensure the resource ARNs in policies match your AWS account and region
   - Check CloudTrail logs for detailed permission errors

### Debugging Steps

1. **Verify OIDC Provider**
   ```bash
   aws iam list-open-id-connect-providers
   ```

2. **Check Role Trust Policy**
   ```bash
   aws iam get-role --role-name github-actions-deployment-role
   ```

3. **Test Role Assumption**
   ```bash
   aws sts get-caller-identity
   ```

4. **Review CloudTrail Logs**
   Look for `AssumeRoleWithWebIdentity` events in CloudTrail for detailed error information.

## Updating the Configuration

### Adding New Permissions

To add new AWS permissions:

1. Update the relevant IAM policy in `terraform/github_oidc.tf`
2. Run `terraform plan` and `terraform apply`
3. Test the new permissions in a GitHub Actions workflow

### Changing Repository or Branch

To change the trusted repository or branch:

1. Update the `github_repository` variable in `terraform/terraform.tfvars`
2. Modify the trust policy condition in `terraform/github_oidc.tf` if changing branches
3. Apply the Terraform changes

### Rotating OIDC Thumbprints

GitHub's OIDC thumbprints may change over time. To update:

1. Get current thumbprints from GitHub's documentation
2. Update the `thumbprint_list` in `terraform/github_oidc.tf`
3. Apply the Terraform changes

## Cost Considerations

The OIDC setup has minimal cost impact:

- **IAM Role**: No charge
- **OIDC Provider**: No charge
- **S3 Bucket**: Standard S3 pricing for artifact storage
- **CloudWatch Logs**: Standard pricing for deployment logs

The S3 bucket includes lifecycle policies to minimize storage costs by automatically transitioning old artifacts to cheaper storage classes and deleting them after one year.

## Security Monitoring

Monitor the following for security:

1. **CloudTrail Events**: Monitor `AssumeRoleWithWebIdentity` events
2. **IAM Access Analyzer**: Review role usage and permissions
3. **AWS Config**: Track IAM role and policy changes
4. **GitHub Audit Log**: Monitor repository access and workflow runs

## References

- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [AWS IAM OIDC Documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [Configuring AWS Credentials Action](https://github.com/aws-actions/configure-aws-credentials)