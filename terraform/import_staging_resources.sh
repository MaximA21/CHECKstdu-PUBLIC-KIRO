#!/bin/bash

# Script to import existing staging resources into Terraform state
# Run this script when Terraform state is empty but resources exist in AWS

set -e

echo "Importing existing staging resources into Terraform state..."

# DynamoDB Tables
echo "Importing DynamoDB tables..."
terraform import aws_dynamodb_table.provider_results provider-comparison-staging-results
terraform import aws_dynamodb_table.analytics provider-comparison-staging-analytics
terraform import aws_dynamodb_table.connection_routing provider-comparison-staging-connection-routing

# IAM Roles
echo "Importing IAM roles..."
terraform import aws_iam_role.lambda_role provider-comparison-staging-lambda-role
terraform import aws_iam_role.connect_handler_role provider-comparison-staging-connect-handler-role
terraform import aws_iam_role.search_handler_role provider-comparison-staging-search-handler-role
terraform import aws_iam_role.authorizer_role provider-comparison-staging-authorizer-role
terraform import aws_iam_role.share_api_role provider-comparison-staging-share-api-new-role
terraform import aws_iam_role.share_api_old_role provider-comparison-staging-share-api-old-role
terraform import aws_iam_role.connection_router_role provider-comparison-staging-connection-router-role
terraform import aws_iam_role.connection_limit_enforcer_role provider-comparison-staging-connection-limit-enforcer-role
terraform import aws_iam_role.step_functions_role provider-comparison-staging-step-functions-role

# IAM Policies
echo "Importing IAM policies..."
terraform import aws_iam_policy.lambda_basic_execution provider-comparison-staging-lambda-basic-execution
terraform import aws_iam_policy.lambda_deployment_policy github-actions-lambda-deployment
terraform import aws_iam_policy.api_gateway_deployment_policy github-actions-api-gateway-deployment
terraform import aws_iam_policy.cloudformation_deployment_policy github-actions-cloudformation-deployment
terraform import aws_iam_policy.s3_artifacts_policy github-actions-s3-artifacts
terraform import aws_iam_policy.cloudwatch_logs_policy github-actions-cloudwatch-logs

# Secrets Manager
echo "Importing Secrets Manager..."
terraform import aws_secretsmanager_secret.provider_keys provider-comparison-staging-provider-keys-v2

# EventBridge Connections
echo "Importing EventBridge Connections..."
terraform import aws_cloudwatch_event_connection.byteme_connection provider-comparison-staging-byteme-connection
terraform import aws_cloudwatch_event_connection.verbyndich_connection provider-comparison-staging-verbyndich-connection
terraform import aws_cloudwatch_event_connection.servus_speed_connection provider-comparison-staging-servus-speed-connection
terraform import aws_cloudwatch_event_connection.webwunder_connection provider-comparison-staging-webwunder-connection
terraform import aws_cloudwatch_event_connection.ping_perfect_connection provider-comparison-staging-ping_perfect-connection

echo "Import completed. Running terraform plan to check status..."
terraform plan -var-file=terraform.tfvars.staging 