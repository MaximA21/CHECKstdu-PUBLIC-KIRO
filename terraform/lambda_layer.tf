# Lambda Layer for ultra-fast JSON processing (orjson)
/*
resource "aws_lambda_layer_version" "json_layer" {
  filename         = "./../lambda_packages/json_layer.zip"
  layer_name       = "${var.project_name}-${var.environment}-json"
  source_code_hash = filebase64sha256("./../lambda_packages/json_layer.zip")

  compatible_runtimes = ["python3.9"]
  description        = "Ultra-fast JSON processing with orjson"

}

# Lambda Layer for data processing (polars)
resource "aws_lambda_layer_version" "polars_layer" {
  filename         = "./../lambda_packages/polars_layer.zip"
  layer_name       = "${var.project_name}-${var.environment}-polars"
  source_code_hash = filebase64sha256("./../lambda_packages/polars_layer.zip")

  compatible_runtimes = ["python3.9"]
  description        = "High-performance data processing with Polars"
}

 */

# Lambda Layer for ultra-fast JSON processing (orjson) - ARM64
resource "aws_lambda_layer_version" "json_layer_arm64" {
  filename         = "./../lambda_packages/json_layer_arm64.zip"
  layer_name       = "${var.project_name}-${var.environment}-json-arm64"
  source_code_hash = filebase64sha256("./../lambda_packages/json_layer_arm64.zip")

  compatible_runtimes      = ["python3.9", "python3.10", "python3.11"]
  compatible_architectures = ["arm64"]
  description              = "Ultra-fast JSON processing with orjson (Graviton2 optimized)"


}

# Lambda Layer for data processing (polars) - ARM64
resource "aws_lambda_layer_version" "polars_layer_arm64" {
  filename         = "./../lambda_packages/polars_layer_arm64.zip"
  layer_name       = "${var.project_name}-${var.environment}-polars-arm64"
  source_code_hash = filebase64sha256("./../lambda_packages/polars_layer_arm64.zip")

  compatible_runtimes      = ["python3.9", "python3.10", "python3.11"]
  compatible_architectures = ["arm64"]
  description              = "High-performance data processing with Polars (Graviton2 optimized)"


}

# Lambda Layer for shared dependencies (boto3, requests, etc.) - ARM64
resource "aws_lambda_layer_version" "shared_dependencies_layer_arm64" {
  filename         = "./../lambda_packages/shared_dependencies_arm64.zip"
  layer_name       = "${var.project_name}-${var.environment}-shared-deps-arm64"
  source_code_hash = filebase64sha256("./../lambda_packages/shared_dependencies_arm64.zip")

  compatible_runtimes      = ["python3.9", "python3.10", "python3.11"]
  compatible_architectures = ["arm64"]
  description              = "Shared dependencies for Lambda functions (boto3, requests, etc.)"


}

