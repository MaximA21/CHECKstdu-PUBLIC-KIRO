# Results Queue for provider API responses
resource "aws_sqs_queue" "results_queue" {
  name                      = "${var.project_name}-${var.environment}-results-queue"
  delay_seconds             = 0
  max_message_size          = 262144 # 256 KB (enough for API responses)
  message_retention_seconds = 86400  # 24 hours
  receive_wait_time_seconds = 10     # Long polling
  visibility_timeout_seconds = 300   # 5 minutes

  # Server-side encryption
  kms_master_key_id                 = "alias/aws/sqs"
  kms_data_key_reuse_period_seconds = 300

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-results-queue"
    Environment = var.environment
  })
}

# Dead Letter Queue for failed result processing
resource "aws_sqs_queue" "results_dlq" {
  name                      = "${var.project_name}-${var.environment}-results-dlq"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 1209600 # 14 days
  visibility_timeout_seconds = 300    # 5 minutes

  # Server-side encryption
  kms_master_key_id                 = "alias/aws/sqs"
  kms_data_key_reuse_period_seconds = 300

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-results-dlq"
    Environment = var.environment
  })
}

# Connect DLQ to main results queue
resource "aws_sqs_queue_redrive_policy" "results_redrive" {
  queue_url = aws_sqs_queue.results_queue.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.results_dlq.arn
    maxReceiveCount     = 3 # Fewer retries for results processing
  })
}

# CloudWatch alarms for results queue monitoring
resource "aws_cloudwatch_metric_alarm" "results_queue_dlq_messages" {
  alarm_name          = "${var.project_name}-${var.environment}-results-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "5"
  alarm_description   = "This metric monitors results DLQ message count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.results_dlq.name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "results_queue_age" {
  alarm_name          = "${var.project_name}-${var.environment}-results-queue-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "600" # 10 minutes
  alarm_description   = "This metric monitors results queue message age"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.results_queue.name
  }

  tags = local.common_tags
}
#
# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-alerts"
  })
}

# SNS topic policy
resource "aws_sns_topic_policy" "alerts_policy" {
  arn = aws_sns_topic.alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action = "sns:Publish"
        Resource = aws_sns_topic.alerts.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}