# Enhanced Lambda security policies following least privilege principles
# This file provides more granular IAM policies for different Lambda function types

# Basic Lambda execution policy (minimal permissions)
resource "aws_iam_policy" "lambda_basic_execution" {
  name        = "${var.project_name}-${var.environment}-lambda-basic-execution"
  description = "Basic execution policy for Lambda functions (CloudWatch Logs only)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsAccess"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-${var.environment}-*:*"
        ]
      },
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-lambda-basic-execution"
    Purpose      = "Basic Lambda execution permissions"
    SecurityTier = "Basic"
  })
}

# WebSocket connection management policy
resource "aws_iam_policy" "lambda_websocket_policy" {
  name        = "${var.project_name}-${var.environment}-lambda-websocket"
  description = "Policy for Lambda functions that manage WebSocket connections"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WebSocketConnectionManagement"
        Effect = "Allow"
        Action = [
          "execute-api:ManageConnections"
        ]
        Resource = [
          "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
        ]
      },
      {
        Sid    = "ConnectionRoutingTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.connection_routing.arn,
          "${aws_dynamodb_table.connection_routing.arn}/index/*"
        ]
        Condition = {
          "ForAllValues:StringEquals" = {
            "dynamodb:Attributes" = [
              "connection_id",
              "user_id",
              "connected_at",
              "last_activity",
              "implementation_version",
              "result_count",
              "ttl"
            ]
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-lambda-websocket"
    Purpose      = "WebSocket connection management"
    SecurityTier = "Restricted"
  })
}

# Data access policy for search and results handlers
resource "aws_iam_policy" "lambda_data_access_policy" {
  name        = "${var.project_name}-${var.environment}-lambda-data-access"
  description = "Policy for Lambda functions that access provider results data"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ProviderResultsAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.provider_results.arn,
          "${aws_dynamodb_table.provider_results.arn}/index/*"
        ]
        Condition = {
          "ForAllValues:StringEquals" = {
            "dynamodb:Attributes" = [
              "search_id",
              "provider",
              "results",
              "timestamp",
              "status",
              "ttl"
            ]
          }
        }
      },
      {
        Sid    = "QueueAccess"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          aws_sqs_queue.request_queue.arn,
          aws_sqs_queue.results_queue.arn
        ]
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-lambda-data-access"
    Purpose      = "Provider results data access"
    SecurityTier = "Restricted"
  })
}

# Secrets access policy (most restricted)
resource "aws_iam_policy" "lambda_secrets_policy" {
  name        = "${var.project_name}-${var.environment}-lambda-secrets"
  description = "Policy for Lambda functions that need access to provider API keys"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.provider_keys.arn
        ]
        Condition = {
          StringEquals = {
            "secretsmanager:ResourceTag/Environment" = var.environment
            "secretsmanager:ResourceTag/Project"     = var.project_name
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-lambda-secrets"
    Purpose      = "Provider API keys access"
    SecurityTier = "HighlyRestricted"
  })
}

# Authorization policy for authorizer Lambda
resource "aws_iam_policy" "lambda_authorizer_policy" {
  name        = "${var.project_name}-${var.environment}-lambda-authorizer"
  description = "Policy for API Gateway authorizer Lambda function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AuthorizerMinimalAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.connection_routing.arn
        ]
        Condition = {
          "ForAllValues:StringEquals" = {
            "dynamodb:Attributes" = [
              "connection_id",
              "user_id",
              "connected_at"
            ]
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-lambda-authorizer"
    Purpose      = "API Gateway authorization"
    SecurityTier = "Restricted"
  })
}

# Function-specific IAM roles with minimal permissions

# Connect handler role (WebSocket + basic execution)
resource "aws_iam_role" "connect_handler_role" {
  name = "${var.project_name}-${var.environment}-connect-handler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-connect-handler-role"
    Purpose      = "WebSocket connection handler"
    SecurityTier = "Restricted"
  })
}

# Attach policies to connect handler role
resource "aws_iam_role_policy_attachment" "connect_handler_basic" {
  role       = aws_iam_role.connect_handler_role.name
  policy_arn = aws_iam_policy.lambda_basic_execution.arn
}

resource "aws_iam_role_policy_attachment" "connect_handler_websocket" {
  role       = aws_iam_role.connect_handler_role.name
  policy_arn = aws_iam_policy.lambda_websocket_policy.arn
}

# Search handler role (data access + secrets + basic execution)
resource "aws_iam_role" "search_handler_role" {
  name = "${var.project_name}-${var.environment}-search-handler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-search-handler-role"
    Purpose      = "Provider search handler"
    SecurityTier = "HighlyRestricted"
  })
}

# Attach policies to search handler role
resource "aws_iam_role_policy_attachment" "search_handler_basic" {
  role       = aws_iam_role.search_handler_role.name
  policy_arn = aws_iam_policy.lambda_basic_execution.arn
}

resource "aws_iam_role_policy_attachment" "search_handler_data" {
  role       = aws_iam_role.search_handler_role.name
  policy_arn = aws_iam_policy.lambda_data_access_policy.arn
}

resource "aws_iam_role_policy_attachment" "search_handler_secrets" {
  role       = aws_iam_role.search_handler_role.name
  policy_arn = aws_iam_policy.lambda_secrets_policy.arn
}

# Authorizer role (minimal permissions)
resource "aws_iam_role" "authorizer_role" {
  name = "${var.project_name}-${var.environment}-authorizer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name         = "${var.project_name}-${var.environment}-authorizer-role"
    Purpose      = "API Gateway authorizer"
    SecurityTier = "Restricted"
  })
}

# Attach policies to authorizer role
resource "aws_iam_role_policy_attachment" "authorizer_basic" {
  role       = aws_iam_role.authorizer_role.name
  policy_arn = aws_iam_policy.lambda_basic_execution.arn
}

resource "aws_iam_role_policy_attachment" "authorizer_policy" {
  role       = aws_iam_role.authorizer_role.name
  policy_arn = aws_iam_policy.lambda_authorizer_policy.arn
}

# Security best practices: Resource-based policies for additional protection

# Lambda function resource policy to restrict invocation sources
# Commented out until Lambda function exists
# resource "aws_lambda_permission" "api_gateway_invoke_authorizer" {
#   statement_id  = "AllowExecutionFromAPIGateway"
#   action        = "lambda:InvokeFunction"
#   function_name = "${var.project_name}-${var.environment}-authorizer"
#   principal     = "apigateway.amazonaws.com"
#   source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*/*"
# }

# Additional security: VPC configuration for Lambda functions (optional)
# Uncomment if VPC isolation is required
/*
resource "aws_security_group" "lambda_sg" {
  name_prefix = "${var.project_name}-${var.environment}-lambda-"
  vpc_id      = var.vpc_id  # Add vpc_id variable if using VPC

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS outbound for AWS services"
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-lambda-sg"
    Purpose = "Lambda function security group"
  })
}
*/