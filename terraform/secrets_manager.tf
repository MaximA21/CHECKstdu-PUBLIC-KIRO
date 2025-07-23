# Secrets Manager for provider API keys
resource "aws_secretsmanager_secret" "provider_keys" {
  name        = "${var.project_name}-${var.environment}-provider-keys-v2"
  description = "API keys for internet provider services"

  tags = {
    Name        = "${var.project_name}-provider-keys"
    Environment = var.environment
  }
}

# The secret values (you'll set these manually or via terraform.tfvars)
resource "aws_secretsmanager_secret_version" "provider_keys" {
  secret_id = aws_secretsmanager_secret.provider_keys.id
  secret_string = jsonencode({
    byteme_api_key    = var.byteme_api_key
    servus_speed_auth = var.servus_speed_auth
    #webwunder_api_key   = var.webwunder_api_key
    # ping_perfect_client_id = var.ping_perfect_client_id
    #ping_perfect_secret = var.ping_perfect_secret
    # verbyndich_api_key  = var.verbyndich_api_key
  })
}

# IAM policy for Step Functions to read secrets
resource "aws_iam_policy" "secrets_access" {
  name        = "${var.project_name}-${var.environment}-secrets-access"
  description = "Allow access to provider secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.provider_keys.arn
      }
    ]
  })
}

# Attach to Step Functions role
resource "aws_iam_role_policy_attachment" "step_functions_secrets" {
  role       = aws_iam_role.step_functions_role.name
  policy_arn = aws_iam_policy.secrets_access.arn
}