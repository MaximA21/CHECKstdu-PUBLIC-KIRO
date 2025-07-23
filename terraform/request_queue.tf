# Main queue for new search requests
resource "aws_sqs_queue" "request_queue" {
  name                       = "${var.project_name}-${var.environment}-request-queue"
  delay_seconds              = 0
  max_message_size           = 262144 # 256 KB
  message_retention_seconds  = 86400  # 24 hours (1 day)
  receive_wait_time_seconds  = 10     # Long polling for efficient processing
  visibility_timeout_seconds = 300    # 5 minutes

  # Server-side encryption
  kms_master_key_id                 = "alias/aws/sqs"
  kms_data_key_reuse_period_seconds = 300

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-request-queue"
    Environment = var.environment
  })
}

# Dead Letter Queue for failed requests
resource "aws_sqs_queue" "request_dlq" {
  name                       = "${var.project_name}-${var.environment}-request-dlq"
  delay_seconds              = 0
  max_message_size           = 262144  # 256 KB
  message_retention_seconds  = 1209600 # 14 days for longer analysis time
  visibility_timeout_seconds = 300     # 5 minutes

  # Server-side encryption
  kms_master_key_id                 = "alias/aws/sqs"
  kms_data_key_reuse_period_seconds = 300

  tags = merge(local.common_tags, {
    Name        = "${var.project_name}-request-dlq"
    Environment = var.environment
  })
}

# Connect the DLQ with the main queue
resource "aws_sqs_queue_redrive_policy" "request_redrive" {
  queue_url = aws_sqs_queue.request_queue.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.request_dlq.arn
    maxReceiveCount     = 5 # After 5 failed attempts to DLQ
  })
}

# CloudWatch alarms for request queue monitoring
resource "aws_cloudwatch_metric_alarm" "request_queue_dlq_messages" {
  alarm_name          = "${var.project_name}-${var.environment}-request-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "10"
  alarm_description   = "This metric monitors request DLQ message count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.request_dlq.name
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "request_queue_age" {
  alarm_name          = "${var.project_name}-${var.environment}-request-queue-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "900" # 15 minutes
  alarm_description   = "This metric monitors request queue message age"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.request_queue.name
  }

  tags = local.common_tags
}