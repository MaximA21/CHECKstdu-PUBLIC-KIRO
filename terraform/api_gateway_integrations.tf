# Integration for Connect endpoint with traffic distribution
resource "aws_apigatewayv2_integration" "connect_router_integration" {
  api_id           = aws_apigatewayv2_api.websocket_api.id
  integration_type = "AWS_PROXY"

  integration_uri           = aws_lambda_function.connection_router.invoke_arn
  integration_method        = "POST"
  content_handling_strategy = "CONVERT_TO_TEXT"
}

# Integration for Search endpoint with traffic distribution
resource "aws_apigatewayv2_integration" "search_router_integration" {
  api_id           = aws_apigatewayv2_api.websocket_api.id
  integration_type = "AWS_PROXY"

  integration_uri           = aws_lambda_function.connection_router.invoke_arn
  integration_method        = "POST"
  content_handling_strategy = "CONVERT_TO_TEXT"
}

# Legacy integrations for direct access (kept for fallback)
resource "aws_apigatewayv2_integration" "connect_integration" {
  api_id           = aws_apigatewayv2_api.websocket_api.id
  integration_type = "AWS_PROXY"

  integration_uri           = aws_lambda_function.connect_handler.invoke_arn
  integration_method        = "POST"
  content_handling_strategy = "CONVERT_TO_TEXT"
}

resource "aws_apigatewayv2_integration" "search_integration" {
  api_id           = aws_apigatewayv2_api.websocket_api.id
  integration_type = "AWS_PROXY"

  integration_uri           = aws_lambda_function.search_handler.invoke_arn
  integration_method        = "POST"
  content_handling_strategy = "CONVERT_TO_TEXT"
}

# Integration für den Disconnect-Endpunkt
#resource "aws_apigatewayv2_integration" "disconnect_integration" {
# api_id           = aws_apigatewayv2_api.websocket_api.id
#integration_type = "AWS_PROXY"

#integration_uri           = aws_lambda_function.disconnect_handler.invoke_arn
#integration_method        = "POST"
#content_handling_strategy = "CONVERT_TO_TEXT"
#}