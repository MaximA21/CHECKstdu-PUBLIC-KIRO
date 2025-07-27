# API Gateway WebSocket API in eu-central-1 with traffic distribution
resource "aws_apigatewayv2_api" "websocket_api" {
  name                       = "${var.project_name}-${var.environment}-websocket"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"

  # API description for traffic distribution
  description = "WebSocket API with 50/50 traffic distribution between old and new implementations"

  tags = {
    Name                = "${var.project_name}-websocket-api"
    Environment         = var.environment
    TrafficDistribution = "enabled"
  }
}

# Lambda Authorizer für Verbindungsautorisierung
#resource "aws_apigatewayv2_authorizer" "websocket_authorizer" {
# api_id           = aws_apigatewayv2_api.websocket_api.id
#authorizer_type  = "REQUEST"
#authorizer_uri   = aws_lambda_function.authorizer.invoke_arn
#identity_sources = ["route.request.querystring.token"]
#name             = "websocket-authorizer"
#}

# Route for connection with traffic distribution
resource "aws_apigatewayv2_route" "connect" {
  api_id    = aws_apigatewayv2_api.websocket_api.id
  route_key = "$connect"
  #  authorization_type = "CUSTOM"
  # authorizer_id      = aws_apigatewayv2_authorizer.websocket_authorizer.id
  target = "integrations/${aws_apigatewayv2_integration.connect_router_integration.id}"
}

# Route for search requests with traffic distribution
resource "aws_apigatewayv2_route" "search" {
  api_id    = aws_apigatewayv2_api.websocket_api.id
  route_key = "search"
  target    = "integrations/${aws_apigatewayv2_integration.search_router_integration.id}"
}

# Route für Trennung
#resource "aws_apigatewayv2_route" "disconnect" {
# api_id    = aws_apigatewayv2_api.websocket_api.id
#route_key = "$disconnect"
#target    = "integrations/${aws_apigatewayv2_integration.disconnect_integration.id}"
#}

# Production stage with traffic distribution and connection tracking
resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.websocket_api.id
  name        = "prod"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit   = 100  # Limit burst requests
    throttling_rate_limit    = 50   # Requests per second
    detailed_metrics_enabled = true # Enable detailed CloudWatch metrics
  }

  # Enable access logging for traffic distribution and connection tracking
  # Commented out due to CloudWatch Logs role ARN requirement
  # access_log_settings {
  #   destination_arn = aws_cloudwatch_log_group.api_logs.arn
  #   format = jsonencode({
  #     requestId          = "$context.requestId"
  #     ip                 = "$context.identity.sourceIp"
  #     requestTime        = "$context.requestTime"
  #     routeKey           = "$context.routeKey"
  #     status             = "$context.status"
  #     connectionId       = "$context.connectionId"
  #     error              = "$context.error.message"
  #     integrationLatency = "$context.integrationLatency"
  #     responseLength     = "$context.responseLength"
  #     # Additional fields for traffic distribution monitoring
  #     userAgent = "$context.identity.userAgent"
  #     protocol  = "$context.protocol"
  #     stage     = "$context.stage"
  #   })
  # }

  tags = {
    Name                = "${var.project_name}-prod-stage"
    Environment         = var.environment
    TrafficDistribution = "enabled"
    ConnectionTracking  = "enabled"
  }
}

# Staging environment for testing traffic distribution
resource "aws_apigatewayv2_stage" "staging" {
  api_id      = aws_apigatewayv2_api.websocket_api.id
  name        = "staging"
  auto_deploy = false

  default_route_settings {
    throttling_burst_limit   = 50 # Lower limits for staging
    throttling_rate_limit    = 25 # Requests per second
    detailed_metrics_enabled = true
  }

  # Commented out due to CloudWatch Logs role ARN requirement
  # access_log_settings {
  #   destination_arn = aws_cloudwatch_log_group.api_logs.arn
  #   format = jsonencode({
  #     requestId          = "$context.requestId"
  #     ip                 = "$context.identity.sourceIp"
  #     requestTime        = "$context.requestTime"
  #     routeKey           = "$context.routeKey"
  #     status             = "$context.status"
  #     connectionId       = "$context.connectionId"
  #     error              = "$context.error.message"
  #     integrationLatency = "$context.integrationLatency"
  #     responseLength     = "$context.responseLength"
  #     # Additional fields for traffic distribution monitoring
  #     userAgent = "$context.identity.userAgent"
  #     protocol  = "$context.protocol"
  #     stage     = "$context.stage"
  #   })
  # }

  tags = {
    Name                = "${var.project_name}-staging-stage"
    Environment         = "staging"
    TrafficDistribution = "enabled"
    ConnectionTracking  = "enabled"
  }
}

# CloudWatch log group for API logs
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${aws_apigatewayv2_api.websocket_api.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.enable_custom_kms_keys ? aws_kms_key.logs_key[0].arn : null

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-api-logs"
    Environment = var.environment
  })
}

# CloudWatch-Protokollgruppe für API-Logs
#resource "aws_cloudwatch_log_group" "api_logs" {
# name              = "/aws/apigateway/${aws_apigatewayv2_api.websocket_api.name}"
#retention_in_days = 30

#  tags = {
#   Name        = "${var.project_name}-api-logs"
#  Environment = var.environment
#}
#}

# API Gateway-Richtlinie - ermöglicht nur sichere TLS-Verbindungen
#resource "aws_api_gateway_rest_api_policy" "api_policy" {
# rest_api_id = aws_apigatewayv2_api.websocket_api.id

# policy = jsonencode({
#  Version = "2012-10-17"
# Statement = [
#  {
#   Effect = "Allow"
#  Principal = "*"
# Action = "execute-api:Invoke"
#      Resource = "${aws_apigatewayv2_api.websocket_api.execution_arn}/*"
#     Condition = {
#      Bool = {
#       "aws:SecureTransport" = "true"
#    }
#        }
#     }
#  ]
# })
#}