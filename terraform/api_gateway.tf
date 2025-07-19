resource "aws_apigatewayv2_api" "websocket_api" {
  name                       = "${var.project_name}-${var.environment}-websocket"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"

  tags = {
    Name        = "${var.project_name}-websocket-api"
    Environment = var.environment
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

# Standardroute für Verbindung mit Authorizer
resource "aws_apigatewayv2_route" "connect" {
  api_id             = aws_apigatewayv2_api.websocket_api.id
  route_key          = "$connect"
#  authorization_type = "CUSTOM"
 # authorizer_id      = aws_apigatewayv2_authorizer.websocket_authorizer.id
  target             = "integrations/${aws_apigatewayv2_integration.connect_integration.id}"
}

# Route für Anfragen
resource "aws_apigatewayv2_route" "search" {
  api_id    = aws_apigatewayv2_api.websocket_api.id
  route_key = "search"
  target    = "integrations/${aws_apigatewayv2_integration.search_integration.id}"
}

# Route für Trennung
#resource "aws_apigatewayv2_route" "disconnect" {
 # api_id    = aws_apigatewayv2_api.websocket_api.id
  #route_key = "$disconnect"
  #target    = "integrations/${aws_apigatewayv2_integration.disconnect_integration.id}"
#}

# Deployment des API Gateway
resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.websocket_api.id
  name        = "prod"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100  # Begrenzt Burst-Anfragen
    throttling_rate_limit  = 50   # Anfragen pro Sekunde
    detailed_metrics_enabled = true  # Aktiviert detaillierte CloudWatch-Metriken
  }

  # Protokollierung von Anfragen und Antworten
 # access_log_settings {
  #  destination_arn = aws_cloudwatch_log_group.api_logs.arn
   # format          = jsonencode({
    #  requestId      = "$context.requestId"
     # ip             = "$context.identity.sourceIp"
      #requestTime    = "$context.requestTime"
  #    routeKey       = "$context.routeKey"
   #   status         = "$context.status"
    #  connectionId   = "$context.connectionId"
     # error          = "$context.error.message"
      #integrationLatency = "$context.integrationLatency"
    #})
  #}

  #tags = {
   # Name        = "${var.project_name}-prod-stage"
    #Environment = var.environment
  #}
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