# GitHub OIDC Identity Provider and IAM Roles for CI/CD Pipeline

# OIDC Identity Provider for GitHub Actions
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = {
    Name        = "github-actions-oidc"
    Environment = var.environment
    Project     = "production-deployment-pipeline"
  }
}

# IAM Role for GitHub Actions CI/CD Pipeline
resource "aws_iam_role" "github_actions_role" {
  name = "github-actions-deployment-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:ref:refs/heads/kiro-rewrite"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "github-actions-deployment-role"
    Environment = var.environment
    Project     = "production-deployment-pipeline"
  }
}

# IAM Policy for Lambda deployment permissions
resource "aws_iam_policy" "lambda_deployment_policy" {
  name        = "github-actions-lambda-deployment"
  description = "Policy for GitHub Actions to deploy Lambda functions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:CreateFunction",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:GetFunction",
          "lambda:ListFunctions",
          "lambda:PublishVersion",
          "lambda:CreateAlias",
          "lambda:UpdateAlias",
          "lambda:GetAlias",
          "lambda:ListAliases",
          "lambda:TagResource",
          "lambda:UntagResource",
          "lambda:ListTags"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:CreateLayerVersion",
          "lambda:GetLayerVersion",
          "lambda:ListLayerVersions",
          "lambda:ListLayers"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:layer:*"
        ]
      }
    ]
  })
}

# IAM Policy for API Gateway deployment permissions
resource "aws_iam_policy" "api_gateway_deployment_policy" {
  name        = "github-actions-api-gateway-deployment"
  description = "Policy for GitHub Actions to deploy API Gateway resources"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "apigateway:GET",
          "apigateway:POST",
          "apigateway:PUT",
          "apigateway:PATCH",
          "apigateway:DELETE",
          "apigateway:UpdateRestApiPolicy",
          "apigateway:CreateDeployment",
          "apigateway:CreateStage",
          "apigateway:UpdateStage",
          "apigateway:GetStage",
          "apigateway:GetDeployment",
          "apigateway:TagResource",
          "apigateway:UntagResource"
        ]
        Resource = [
          "arn:aws:apigateway:${var.aws_region}::/restapis/*",
          "arn:aws:apigateway:${var.aws_region}::/apis/*"
        ]
      }
    ]
  })
}

# IAM Policy for CloudFormation stack management
resource "aws_iam_policy" "cloudformation_deployment_policy" {
  name        = "github-actions-cloudformation-deployment"
  description = "Policy for GitHub Actions to manage CloudFormation stacks"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudformation:CreateStack",
          "cloudformation:UpdateStack",
          "cloudformation:DeleteStack",
          "cloudformation:DescribeStacks",
          "cloudformation:DescribeStackEvents",
          "cloudformation:DescribeStackResources",
          "cloudformation:GetTemplate",
          "cloudformation:ValidateTemplate",
          "cloudformation:ListStacks",
          "cloudformation:TagResource",
          "cloudformation:UntagResource"
        ]
        Resource = [
          "arn:aws:cloudformation:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stack/*"
        ]
      }
    ]
  })
}

# IAM Policy for S3 artifact storage
resource "aws_iam_policy" "s3_artifacts_policy" {
  name        = "github-actions-s3-artifacts"
  description = "Policy for GitHub Actions to manage deployment artifacts in S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.deployment_bucket_name}",
          "arn:aws:s3:::${var.deployment_bucket_name}/*"
        ]
      }
    ]
  })
}

# IAM Policy for CloudWatch Logs access
resource "aws_iam_policy" "cloudwatch_logs_policy" {
  name        = "github-actions-cloudwatch-logs"
  description = "Policy for GitHub Actions to access CloudWatch Logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:TagResource",
          "logs:UntagResource"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/apigateway/*"
        ]
      }
    ]
  })
}

# Attach AWS managed policies for basic deployment needs
resource "aws_iam_role_policy_attachment" "github_actions_iam_read_only" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = "arn:aws:iam::aws:policy/IAMReadOnlyAccess"
}

# Attach custom policies to the GitHub Actions role
resource "aws_iam_role_policy_attachment" "lambda_deployment" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.lambda_deployment_policy.arn
}

resource "aws_iam_role_policy_attachment" "api_gateway_deployment" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.api_gateway_deployment_policy.arn
}

resource "aws_iam_role_policy_attachment" "cloudformation_deployment" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.cloudformation_deployment_policy.arn
}

resource "aws_iam_role_policy_attachment" "s3_artifacts" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.s3_artifacts_policy.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch_logs" {
  role       = aws_iam_role.github_actions_role.name
  policy_arn = aws_iam_policy.cloudwatch_logs_policy.arn
}

# Data source to get current AWS account ID (using existing one from main.tf)