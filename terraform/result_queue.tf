# Results Queue for provider API responses
resource "aws_sqs_queue" "results_queue" {
  name                      = "${var.project_name}-${var.environment}-results-queue"
  delay_seconds             = 0
  max_message_size          = 262144  # 256 KB (enough for API responses)
  message_retention_seconds = 86400   # 24 hours
  receive_wait_time_seconds = 10      # Long polling

  tags = {
    Name        = "${var.project_name}-results-queue"
    Environment = var.environment
  }
}

# Dead Letter Queue for failed result processing
resource "aws_sqs_queue" "results_dlq" {
  name                      = "${var.project_name}-${var.environment}-results-dlq"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.project_name}-results-dlq"
    Environment = var.environment
  }
}

# Connect DLQ to main results queue
resource "aws_sqs_queue_redrive_policy" "results_redrive" {
  queue_url = aws_sqs_queue.results_queue.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.results_dlq.arn
    maxReceiveCount     = 3  # Fewer retries for results processing
  })
}