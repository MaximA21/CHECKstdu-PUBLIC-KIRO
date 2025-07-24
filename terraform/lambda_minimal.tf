# Lambda-Rolle mit Berechtigungen
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

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
    Name        = "${var.project_name}-lambda-role"
    Environment = var.environment
  }
}

# Comprehensive Lambda policy for new architecture
resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.project_name}-${var.environment}-lambda-policy"
  description = "Comprehensive policy for Lambda functions with DI architecture"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:*"
      },
      {
        Action = [
          "execute-api:ManageConnections"
        ]
        Effect   = "Allow"
        Resource = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
      },
      {
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Effect = "Allow"
        Resource = [
          aws_sqs_queue.request_queue.arn,
          aws_sqs_queue.request_dlq.arn,
          aws_sqs_queue.results_queue.arn,
          aws_sqs_queue.results_dlq.arn
        ]
      },
      {
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Effect = "Allow"
        Resource = [
          aws_dynamodb_table.provider_results.arn,
          aws_dynamodb_table.connection_routing.arn,
          "${aws_dynamodb_table.provider_results.arn}/index/*",
          "${aws_dynamodb_table.connection_routing.arn}/index/*"
        ]
      },
      {
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Effect = "Allow"
        Resource = [
          aws_secretsmanager_secret.provider_keys.arn
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

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# Common environment variables for all Lambda functions
locals {
  lambda_environment_variables = {
    AWS_REGION                 = var.aws_region
    ENVIRONMENT                = var.environment
    PROJECT_NAME               = var.project_name
    IMPLEMENTATION_VERSION     = "new"
    DYNAMODB_RESULTS_TABLE     = aws_dynamodb_table.provider_results.name
    DYNAMODB_ROUTING_TABLE     = aws_dynamodb_table.connection_routing.name
    SQS_REQUEST_QUEUE_URL      = aws_sqs_queue.request_queue.url
    SQS_RESULTS_QUEUE_URL      = aws_sqs_queue.results_queue.url
    WEBSOCKET_API_ENDPOINT     = aws_apigatewayv2_api.websocket_api.api_endpoint
    SECRETS_PROVIDER_KEYS      = aws_secretsmanager_secret.provider_keys.name
    LOG_LEVEL                  = "INFO"
    CONNECTION_TIMEOUT_MINUTES = local.connection_timeout_minutes
    MAX_RESULTS_PER_CONNECTION = local.max_results_per_connection
  }
}

# Connect Handler Lambda Function
resource "aws_lambda_function" "connect_handler" {
  function_name = "${var.project_name}-${var.environment}-connect-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "connect_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/connect_handler.zip"
  source_code_hash = filebase64sha256("${var.lambda_package_path}/connect_handler.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-connect-handler"
    Function = "websocket-connection"
  })
}

# Disconnect Handler Lambda Function
resource "aws_lambda_function" "disconnect_handler" {
  function_name = "${var.project_name}-${var.environment}-disconnect-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "disconnect_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/disconnect_handler.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/disconnect_handler.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-disconnect-handler"
    Function = "websocket-disconnection"
  })
}

# Search Handler Lambda Function
resource "aws_lambda_function" "search_handler" {
  function_name = "${var.project_name}-${var.environment}-search-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "search_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 60
  memory_size   = 512
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/search_handler.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/search_handler.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-search-handler"
    Function = "search-processing"
  })
}

# Results Handler Lambda Function
resource "aws_lambda_function" "results_handler" {
  function_name = "${var.project_name}-${var.environment}-results-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "results_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 300
  memory_size   = 1024
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/results_handler.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/results_handler.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn,
    aws_lambda_layer_version.polars_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-results-handler"
    Function = "results-processing"
  })
}

# Requestor Handler Lambda Function
resource "aws_lambda_function" "requestor_handler" {
  function_name = "${var.project_name}-${var.environment}-requestor-handler"
  role          = aws_iam_role.lambda_role.arn
  handler       = "requestor_handler.lambda_handler"
  runtime       = "python3.9"
  timeout       = 300
  memory_size   = 512
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/requestor_handler.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/requestor_handler.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-requestor-handler"
    Function = "provider-requests"
  })
}

# Authorizer Lambda Function
resource "aws_lambda_function" "authorizer" {
  function_name = "${var.project_name}-${var.environment}-authorizer"
  role          = aws_iam_role.lambda_role.arn
  handler       = "authorizer.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/authorizer.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/authorizer.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-authorizer"
    Function = "api-authorization"
  })
}

# Address Normalizer Lambda Function
resource "aws_lambda_function" "address_normalizer" {
  function_name = "${var.project_name}-${var.environment}-address-normalizer"
  role          = aws_iam_role.lambda_role.arn
  handler       = "address_normalizer.lambda_handler"
  runtime       = "python3.9"
  timeout       = 60
  memory_size   = 512
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/address_normalizer.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/address_normalizer.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-address-normalizer"
    Function = "address-processing"
  })
}

# Share API Lambda Function
resource "aws_lambda_function" "share_api" {
  function_name = "${var.project_name}-${var.environment}-share-api"
  role          = aws_iam_role.lambda_role.arn
  handler       = "share_api.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/share_api.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/share_api.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-share-api"
    Function = "result-sharing"
  })
}

# Connection Limit Enforcer Lambda Function
resource "aws_lambda_function" "connection_limit_enforcer" {
  function_name = "${var.project_name}-${var.environment}-connection-limit-enforcer"
  role          = aws_iam_role.lambda_role.arn
  handler       = "connection_limit_enforcer.lambda_handler"
  runtime       = "python3.9"
  timeout       = 60
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/connection_limit_enforcer.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/connection_limit_enforcer.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-connection-limit-enforcer"
    Function = "connection-management"
  })
}

# Connection Router Lambda Function
resource "aws_lambda_function" "connection_router" {
  function_name = "${var.project_name}-${var.environment}-connection-router"
  role          = aws_iam_role.lambda_role.arn
  handler       = "connection_router.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/connection_router.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/connection_router.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-connection-router"
    Function = "traffic-routing"
  })
}

# Ping Perfect Signer Lambda Function
resource "aws_lambda_function" "ping_perfect_signer" {
  function_name = "${var.project_name}-${var.environment}-ping-perfect-signer"
  role          = aws_iam_role.lambda_role.arn
  handler       = "ping_perfect_signer.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 256
  architectures = ["arm64"]

  filename         = "${var.lambda_package_path}/ping_perfect_signer.zip"
  source_code_hash = var.skip_lambda_package_validation ? "dummy-hash" : filebase64sha256("${var.lambda_package_path}/ping_perfect_signer.zip")

  layers = [
    aws_lambda_layer_version.json_layer_arm64.arn
  ]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = local.lambda_environment_variables
  }

  tags = merge(local.common_tags, {
    Name     = "${var.project_name}-ping-perfect-signer"
    Function = "provider-authentication"
  })
}

# Lambda permissions for API Gateway WebSocket
resource "aws_lambda_permission" "connect_permission" {
  statement_id  = "AllowExecutionFromAPIGatewayConnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*/$connect"
}

resource "aws_lambda_permission" "disconnect_permission" {
  statement_id  = "AllowExecutionFromAPIGatewayDisconnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.disconnect_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*/$disconnect"
}

resource "aws_lambda_permission" "search_permission" {
  statement_id  = "AllowExecutionFromAPIGatewaySearch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.search_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*/search"
}

# Lambda permissions for SQS triggers
resource "aws_lambda_event_source_mapping" "results_handler_sqs" {
  event_source_arn                   = aws_sqs_queue.results_queue.arn
  function_name                      = aws_lambda_function.results_handler.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
}

resource "aws_lambda_event_source_mapping" "requestor_handler_sqs" {
  event_source_arn                   = aws_sqs_queue.request_queue.arn
  function_name                      = aws_lambda_function.requestor_handler.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 5
}

# Lambda permissions for REST API Gateway
resource "aws_lambda_permission" "share_api_permission" {
  statement_id  = "AllowExecutionFromRestAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.share_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}

# Lambda permissions for authorizer
resource "aws_lambda_permission" "authorizer_permission" {
  statement_id  = "AllowExecutionFromAPIGatewayAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/authorizers/*"
}