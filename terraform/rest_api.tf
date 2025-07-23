# REST API Gateway with canary deployment capability
resource "aws_api_gateway_rest_api" "rest_api" {
  name        = "${var.project_name}-${var.environment}-rest-api"
  description = "REST API with canary deployment for gradual traffic shifting"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name                = "${var.project_name}-rest-api"
    Environment         = var.environment
    CanaryDeployment    = "enabled"
    TrafficDistribution = "enabled"
  }
}

# CORS configuration for REST API
resource "aws_api_gateway_method" "options_method" {
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  resource_id   = aws_api_gateway_rest_api.rest_api.root_resource_id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_integration" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_rest_api.rest_api.root_resource_id
  http_method = aws_api_gateway_method.options_method.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_response" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_rest_api.rest_api.root_resource_id
  http_method = aws_api_gateway_method.options_method.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_rest_api.rest_api.root_resource_id
  http_method = aws_api_gateway_method.options_method.http_method
  status_code = aws_api_gateway_method_response.options_response.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# Share resource for REST API
resource "aws_api_gateway_resource" "share_resource" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  parent_id   = aws_api_gateway_rest_api.rest_api.root_resource_id
  path_part   = "share"
}

resource "aws_api_gateway_resource" "share_token_resource" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  parent_id   = aws_api_gateway_resource.share_resource.id
  path_part   = "{share_token}"
}

# Lambda function for new share API implementation
resource "aws_lambda_function" "share_api_new" {
  function_name = "${var.project_name}-${var.environment}-share-api-new"
  role          = aws_iam_role.share_api_role.arn
  handler       = "share_api.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "./../lambda_packages/share_api.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/share_api.zip")

  environment {
    variables = {
      RESULTS_TABLE_NAME = aws_dynamodb_table.provider_results.name
      IMPLEMENTATION     = "new"
      LOG_LEVEL          = "INFO"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name           = "${var.project_name}-share-api-new"
    Environment    = var.environment
    Architecture   = "arm64"
    Implementation = "new"
  }
}

# Lambda function for old share API implementation (legacy)
resource "aws_lambda_function" "share_api_old" {
  function_name = "${var.project_name}-${var.environment}-share-api-old"
  role          = aws_iam_role.share_api_old_role.arn
  handler       = "share_api.lambda_handler"
  runtime       = "python3.9"
  timeout       = 10
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "./../lambda_packages/share_api.zip"
  source_code_hash = filebase64sha256("./../lambda_packages/share_api.zip")

  environment {
    variables = {
      RESULTS_TABLE_NAME = aws_dynamodb_table.provider_results.name
      IMPLEMENTATION     = "old"
      LOG_LEVEL          = "INFO"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = {
    Name           = "${var.project_name}-share-api-old"
    Environment    = var.environment
    Architecture   = "arm64"
    Implementation = "old"
  }
}

# IAM role for new share API implementation
resource "aws_iam_role" "share_api_role" {
  name = "${var.project_name}-${var.environment}-share-api-new-role"

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

  tags = {
    Name           = "${var.project_name}-share-api-new-role"
    Environment    = var.environment
    Implementation = "new"
  }
}

# IAM role for old share API implementation
resource "aws_iam_role" "share_api_old_role" {
  name = "${var.project_name}-${var.environment}-share-api-old-role"

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

  tags = {
    Name           = "${var.project_name}-share-api-old-role"
    Environment    = var.environment
    Implementation = "old"
  }
}

# IAM policy for new share API (with enhanced permissions)
resource "aws_iam_policy" "share_api_policy" {
  name        = "${var.project_name}-${var.environment}-share-api-new-policy"
  description = "Policy for New Share API Lambda with enhanced permissions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = [
          aws_dynamodb_table.provider_results.arn,
          "${aws_dynamodb_table.provider_results.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "AWS/Lambda"
          }
        }
      }
    ]
  })
}

# IAM policy for old share API (legacy permissions)
resource "aws_iam_policy" "share_api_old_policy" {
  name        = "${var.project_name}-${var.environment}-share-api-old-policy"
  description = "Policy for Old Share API Lambda (legacy)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.provider_results.arn,
          "${aws_dynamodb_table.provider_results.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "share_api_policy_attachment" {
  role       = aws_iam_role.share_api_role.name
  policy_arn = aws_iam_policy.share_api_policy.arn
}

resource "aws_iam_role_policy_attachment" "share_api_old_policy_attachment" {
  role       = aws_iam_role.share_api_old_role.name
  policy_arn = aws_iam_policy.share_api_old_policy.arn
}

# GET method for share endpoint
resource "aws_api_gateway_method" "share_get" {
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  resource_id   = aws_api_gateway_resource.share_token_resource.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.share_token" = true
  }
}

# Integration with new implementation (primary)
resource "aws_api_gateway_integration" "share_integration_new" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_resource.share_token_resource.id
  http_method = aws_api_gateway_method.share_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.share_api_new.invoke_arn

  request_parameters = {
    "integration.request.path.share_token" = "method.request.path.share_token"
  }
}

# Integration with old implementation (fallback)
resource "aws_api_gateway_integration" "share_integration_old" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_resource.share_token_resource.id
  http_method = aws_api_gateway_method.share_get.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.share_api_old.invoke_arn

  request_parameters = {
    "integration.request.path.share_token" = "method.request.path.share_token"
  }
}

# Method response
resource "aws_api_gateway_method_response" "share_response_200" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_resource.share_token_resource.id
  http_method = aws_api_gateway_method.share_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

resource "aws_api_gateway_method_response" "share_response_404" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_resource.share_token_resource.id
  http_method = aws_api_gateway_method.share_get.http_method
  status_code = "404"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = true
  }
}

# Integration responses
resource "aws_api_gateway_integration_response" "share_integration_response_200" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_resource.share_token_resource.id
  http_method = aws_api_gateway_method.share_get.http_method
  status_code = aws_api_gateway_method_response.share_response_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }
}

resource "aws_api_gateway_integration_response" "share_integration_response_404" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  resource_id = aws_api_gateway_resource.share_token_resource.id
  http_method = aws_api_gateway_method.share_get.http_method
  status_code = aws_api_gateway_method_response.share_response_404.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }

  selection_pattern = ".*\"statusCode\":404.*"
}

# Lambda permissions for both implementations
resource "aws_lambda_permission" "share_api_new_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.share_api_new.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "share_api_old_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.share_api_old.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}

# API Gateway deployment for staging
resource "aws_api_gateway_deployment" "rest_api_staging" {
  depends_on = [
    aws_api_gateway_method.share_get,
    aws_api_gateway_integration.share_integration_new,
    aws_api_gateway_integration.share_integration_old,
    aws_api_gateway_method.options_method,
    aws_api_gateway_integration.options_integration
  ]

  rest_api_id = aws_api_gateway_rest_api.rest_api.id

  variables = {
    deployed_at    = timestamp()
    implementation = "staging"
    traffic_split  = "0" # Start with 0% traffic to new implementation
  }

  lifecycle {
    create_before_destroy = true
  }
}

# API Gateway deployment for production with canary capability
resource "aws_api_gateway_deployment" "rest_api_prod" {
  depends_on = [
    aws_api_gateway_method.share_get,
    aws_api_gateway_integration.share_integration_new,
    aws_api_gateway_integration.share_integration_old,
    aws_api_gateway_method.options_method,
    aws_api_gateway_integration.options_integration
  ]

  rest_api_id = aws_api_gateway_rest_api.rest_api.id

  variables = {
    deployed_at    = timestamp()
    implementation = "production"
    traffic_split  = "50" # 50% traffic to new implementation
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Staging stage configuration
resource "aws_api_gateway_stage" "staging" {
  deployment_id = aws_api_gateway_deployment.rest_api_staging.id
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  stage_name    = "staging"

  # Enable detailed monitoring and logging
  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.rest_api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      stage          = "$context.stage"
      userAgent      = "$context.identity.userAgent"
      errorMessage   = "$context.error.message"
      errorType      = "$context.error.messageString"
    })
  }

  tags = {
    Name        = "${var.project_name}-rest-api-staging"
    Environment = "staging"
    Stage       = "staging"
  }
}

# Method settings for staging stage
resource "aws_api_gateway_method_settings" "staging_settings" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  stage_name  = aws_api_gateway_stage.staging.stage_name
  method_path = "*/*"

  settings {
    # Enable detailed CloudWatch metrics
    metrics_enabled = true
    logging_level   = "INFO"

    # Data trace settings
    data_trace_enabled = true

    # Throttling settings per method
    throttling_rate_limit  = 100
    throttling_burst_limit = 200

    # Caching disabled for staging
    caching_enabled = false
  }
}

# Production stage with canary deployment capability
resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.rest_api_prod.id
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  stage_name    = "prod"

  # Enable detailed monitoring and logging
  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.rest_api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      stage          = "$context.stage"
      errorMessage   = "$context.error.message"
      # Canary deployment tracking
      canaryStage    = "$context.stage"
      implementation = "$stageVariables.implementation"
      trafficSplit   = "$stageVariables.traffic_split"
    })
  }

  # Stage variables for canary deployment
  variables = {
    implementation = "production"
    traffic_split  = tostring(var.canary_traffic_percentage)
  }

  tags = {
    Name             = "${var.project_name}-rest-api-prod"
    Environment      = var.environment
    Stage            = "production"
    CanaryDeployment = "enabled"
  }
}

# Method settings for production stage
resource "aws_api_gateway_method_settings" "prod_settings" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    # Enable detailed CloudWatch metrics
    metrics_enabled = true
    logging_level   = "ERROR" # Only log errors in production

    # Data trace disabled in production for performance
    data_trace_enabled = false

    # Throttling settings per method
    throttling_rate_limit  = var.rest_api_throttle_rate_limit
    throttling_burst_limit = var.rest_api_throttle_burst_limit

    # Enable caching in production
    caching_enabled                         = true
    cache_ttl_in_seconds                    = var.rest_api_cache_ttl
    require_authorization_for_cache_control = false
  }
}

# Canary deployment for new implementation (separate deployment)
resource "aws_api_gateway_deployment" "rest_api_canary" {
  count = var.canary_enabled ? 1 : 0

  depends_on = [
    aws_api_gateway_method.share_get,
    aws_api_gateway_integration.share_integration_new,
    aws_api_gateway_method.options_method,
    aws_api_gateway_integration.options_integration
  ]

  rest_api_id = aws_api_gateway_rest_api.rest_api.id

  variables = {
    deployed_at    = timestamp()
    implementation = "canary"
    traffic_split  = tostring(var.canary_traffic_percentage)
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Canary stage for gradual traffic shifting
resource "aws_api_gateway_stage" "canary" {
  count = var.canary_enabled ? 1 : 0

  deployment_id = aws_api_gateway_deployment.rest_api_canary[0].id
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  stage_name    = "canary"

  # Enable detailed monitoring and logging
  xray_tracing_enabled = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.rest_api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      stage          = "$context.stage"
      errorMessage   = "$context.error.message"
      # Canary deployment tracking
      implementation = "$stageVariables.implementation"
      trafficSplit   = "$stageVariables.traffic_split"
    })
  }

  # Stage variables for canary deployment
  variables = {
    implementation = "canary"
    traffic_split  = tostring(var.canary_traffic_percentage)
  }

  tags = {
    Name             = "${var.project_name}-rest-api-canary"
    Environment      = var.environment
    Stage            = "canary"
    CanaryDeployment = "enabled"
  }
}

# Method settings for canary stage
resource "aws_api_gateway_method_settings" "canary_settings" {
  count = var.canary_enabled ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  stage_name  = aws_api_gateway_stage.canary[0].stage_name
  method_path = "*/*"

  settings {
    # Enable detailed CloudWatch metrics for canary
    metrics_enabled = true
    logging_level   = "INFO" # More detailed logging for canary

    # Enable data trace for canary monitoring
    data_trace_enabled = true

    # Conservative throttling for canary
    throttling_rate_limit  = var.rest_api_throttle_rate_limit / 2
    throttling_burst_limit = var.rest_api_throttle_burst_limit / 2

    # Disable caching for canary to ensure fresh responses
    caching_enabled = false
  }
}

# CloudWatch log group for REST API access logs
resource "aws_cloudwatch_log_group" "rest_api_logs" {
  name              = "/aws/apigateway/${aws_api_gateway_rest_api.rest_api.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].arn : null

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-rest-api-logs"
    Environment = var.environment
  })
}

# Outputs for the REST API URLs
output "rest_api_id" {
  description = "REST API Gateway ID"
  value       = aws_api_gateway_rest_api.rest_api.id
}

output "rest_api_execution_arn" {
  description = "REST API Gateway execution ARN"
  value       = aws_api_gateway_rest_api.rest_api.execution_arn
}

output "rest_api_staging_url" {
  description = "REST API Gateway staging URL"
  value       = "https://${aws_api_gateway_rest_api.rest_api.id}.execute-api.${var.aws_region}.amazonaws.com/staging"
}

output "rest_api_prod_url" {
  description = "REST API Gateway production URL"
  value       = "https://${aws_api_gateway_rest_api.rest_api.id}.execute-api.${var.aws_region}.amazonaws.com/prod"
}

output "share_api_staging_url" {
  description = "Share link API staging URL"
  value       = "https://${aws_api_gateway_rest_api.rest_api.id}.execute-api.${var.aws_region}.amazonaws.com/staging/share"
}

output "share_api_prod_url" {
  description = "Share link API production URL"
  value       = "https://${aws_api_gateway_rest_api.rest_api.id}.execute-api.${var.aws_region}.amazonaws.com/prod/share"
}

output "canary_deployment_info" {
  description = "Canary deployment configuration"
  value = var.canary_enabled ? {
    enabled         = true
    percent_traffic = var.canary_traffic_percentage
    stage_name      = aws_api_gateway_stage.canary[0].stage_name
    deployment_id   = aws_api_gateway_deployment.rest_api_canary[0].id
    canary_url      = "https://${aws_api_gateway_rest_api.rest_api.id}.execute-api.${var.aws_region}.amazonaws.com/canary"
    } : {
    enabled = false
  }
}

output "rest_api_implementations" {
  description = "REST API Lambda function implementations"
  value = {
    new_implementation = {
      function_name = aws_lambda_function.share_api_new.function_name
      function_arn  = aws_lambda_function.share_api_new.arn
    }
    old_implementation = {
      function_name = aws_lambda_function.share_api_old.function_name
      function_arn  = aws_lambda_function.share_api_old.arn
    }
  }
}