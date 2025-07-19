# EventBridge rule to trigger every 5 minutes
resource "aws_cloudwatch_event_rule" "lambda_warmer" {
  name                = "${var.project_name}-${var.environment}-lambda-warmer"
  description         = "Keep Lambda functions warm to reduce cold starts"
  schedule_expression = "rate(5 minutes)"

  tags = {
    Name        = "${var.project_name}-lambda-warmer"
    Environment = var.environment
    Purpose     = "cold-start-optimization"
  }
}

# Target: Results Handler (the heavy one with Polars)
resource "aws_cloudwatch_event_target" "warm_results_handler" {
  rule      = aws_cloudwatch_event_rule.lambda_warmer.name
  target_id = "WarmResultsHandler"
  arn       = aws_lambda_function.results_handler.arn

  # Send a special "warmer" payload
  input = jsonencode({
    "warmer": true,
    "timestamp": "scheduled-ping"
  })
}

# Lambda permissions for EventBridge to invoke
resource "aws_lambda_permission" "allow_eventbridge_results_handler" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.results_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_warmer.arn
}

# Optional: CloudWatch dashboard to monitor warmer effectiveness
resource "aws_cloudwatch_dashboard" "lambda_performance" {
  dashboard_name = "${var.project_name}-${var.environment}-lambda-performance"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.results_handler.function_name],
            [".", "InitDuration", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Lambda Performance - Duration vs InitDuration"
          period  = 300
        }
      }
    ]
  })
}