# Haupt-Queue für neue Suchanfragen
resource "aws_sqs_queue" "request_queue" {
  name                      = "${var.project_name}-${var.environment}-request-queue"
  delay_seconds             = 0
  max_message_size          = 262144  # 256 KB
  message_retention_seconds = 86400   # 24 Stunden (1 Tag)
  receive_wait_time_seconds = 10      # Long polling für effiziente Verarbeitung

  tags = {
    Name        = "${var.project_name}-request-queue"
    Environment = var.environment
  }
}

# Dead Letter Queue für fehlgeschlagene Anfragen
resource "aws_sqs_queue" "request_dlq" {
  name                      = "${var.project_name}-${var.environment}-request-dlq"
  delay_seconds             = 0
  max_message_size          = 262144  # 256 KB
  message_retention_seconds = 1209600 # 14 Tage für längere Analyse-Zeit

  tags = {
    Name        = "${var.project_name}-request-dlq"
    Environment = var.environment
  }
}

# Verbinde die DLQ mit der Haupt-Queue
resource "aws_sqs_queue_redrive_policy" "request_redrive" {
  queue_url    = aws_sqs_queue.request_queue.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.request_dlq.arn
    maxReceiveCount     = 5  # Nach 5 fehlgeschlagenen Versuchen zur DLQ
  })
}