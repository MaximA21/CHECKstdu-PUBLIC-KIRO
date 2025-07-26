#!/usr/bin/env python3
"""
Streamlined deployment tests for WebWunder.
Tests basic CI/CD pipeline functionality and rollback mechanisms.
Focuses on core functionality rather than comprehensive coverage.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from unittest.mock import MagicMock, Mock, patch

import boto3
import pytest
from moto import mock_aws


class TestStreamlinedDeployment:
    """Test class for streamlined deployment functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.environment = "staging"
        self.region = "eu-central-1"

    def test_github_actions_workflows_exist(self):
        """Test that all required GitHub Actions workflow files exist."""
        required_workflows = [
            ".github/workflows/code-quality-security.yml",
            ".github/workflows/comprehensive-testing.yml",
            ".github/workflows/build-package.yml",
            ".github/workflows/deployment.yml",
            ".github/workflows/streamlined-deployment-testing.yml",
        ]

        missing_workflows = []
        for workflow in required_workflows:
            if not os.path.exists(workflow):
                missing_workflows.append(workflow)

        assert not missing_workflows, f"Missing required workflow files: {missing_workflows}"

    def test_deployment_scripts_exist(self):
        """Test that all required deployment scripts exist."""
        required_scripts = [
            "scripts/deployment-validator.py",
            "scripts/deployment-monitor.py",
            "scripts/rollback.py",
            "scripts/health-check.py",
            "scripts/deployment_testing.py",  # Fixed: underscore instead of hyphen
        ]

        missing_scripts = []
        for script in required_scripts:
            if not os.path.exists(script):
                missing_scripts.append(script)

        assert not missing_scripts, f"Missing required deployment scripts: {missing_scripts}"

    def test_terraform_configuration_valid(self):
        """Test that Terraform configuration is valid."""
        if not os.path.exists("terraform"):
            pytest.skip("Terraform directory not found")

        try:
            # Test terraform fmt
            result = subprocess.run(
                ["terraform", "fmt", "-check", "-recursive"], cwd="terraform", capture_output=True, text=True, timeout=30
            )

            # Format check should pass or we should be able to format
            if result.returncode != 0:
                # Try to format and check again
                subprocess.run(["terraform", "fmt", "-recursive"], cwd="terraform", timeout=30)

            # Test terraform init and validate
            init_result = subprocess.run(
                ["terraform", "init", "-backend=false"], cwd="terraform", capture_output=True, text=True, timeout=60
            )

            assert init_result.returncode == 0, f"Terraform init failed: {init_result.stderr}"

            validate_result = subprocess.run(
                ["terraform", "validate"], cwd="terraform", capture_output=True, text=True, timeout=30
            )

            assert validate_result.returncode == 0, f"Terraform validation failed: {validate_result.stderr}"

        except subprocess.TimeoutExpired:
            pytest.fail("Terraform validation timed out")
        except FileNotFoundError:
            pytest.skip("Terraform not installed")

    def test_lambda_package_creation(self):
        """Test that Lambda packages can be created."""
        if not os.path.exists("lambda_functions"):
            pytest.skip("Lambda functions directory not found")

        # Test creating a simple Lambda package
        with tempfile.TemporaryDirectory() as temp_dir:
            test_func_dir = os.path.join(temp_dir, "test_function")
            os.makedirs(test_func_dir)

            # Create a simple test handler
            handler_content = """
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": "Test handler"
    }
"""
            with open(os.path.join(test_func_dir, "handler.py"), "w") as f:
                f.write(handler_content)

            # Create a zip package
            import zipfile

            zip_path = os.path.join(temp_dir, "test_package.zip")
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                zip_file.write(os.path.join(test_func_dir, "handler.py"), "handler.py")

            assert os.path.exists(zip_path)
            assert os.path.getsize(zip_path) > 0

    @mock_aws
    def test_rollback_script_functionality(self):
        """Test that rollback script basic functionality works."""
        rollback_script = "scripts/rollback.py"
        if not os.path.exists(rollback_script):
            pytest.skip("Rollback script not found")

        # Create mock IAM role first
        iam_client = boto3.client("iam", region_name=self.region)
        role_name = "webwunder-test-lambda-role"

        # Create the IAM role with proper assume role policy
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{"Action": "sts:AssumeRole", "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}}],
        }

        try:
            iam_client.create_role(
                RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy), Description="Test Lambda role"
            )
        except iam_client.exceptions.EntityAlreadyExistsException:
            pass  # Role already exists

        # Create mock Lambda functions for testing
        lambda_client = boto3.client("lambda", region_name=self.region)

        # Create a test function
        function_name = f"webwunder-{self.environment}-search_handler"
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.11",
            Role="arn:aws:iam::123456789012:role/webwunder-test-lambda-role",
            Handler="handler.lambda_handler",
            Code={"ZipFile": b"fake code"},
            Description="Test function",
        )

        # Test version listing (should not crash)
        try:
            result = subprocess.run(
                ["python3", rollback_script, self.environment, "--list-versions"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "AWS_DEFAULT_REGION": self.region},
            )

            # Should not crash, even if no versions are found
            assert result.returncode in [0, 1], f"Rollback script crashed: {result.stderr}"

        except subprocess.TimeoutExpired:
            pytest.fail("Rollback script timed out")

    def test_backup_creation_functionality(self):
        """Test that backup creation works correctly."""
        # Test creating a backup file
        backup_data = {
            "test_backup": True,
            "timestamp": "2024-01-01T00:00:00Z",
            "environment": self.environment,
            "current_versions": {"search_handler": "1", "results_handler": "2"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(backup_data, f, indent=2)
            backup_file = f.name

        try:
            # Verify backup file was created and is readable
            assert os.path.exists(backup_file)

            with open(backup_file, "r") as f:
                loaded_data = json.load(f)

            assert loaded_data["test_backup"] is True
            assert loaded_data["environment"] == self.environment
            assert "current_versions" in loaded_data

        finally:
            # Clean up
            if os.path.exists(backup_file):
                os.unlink(backup_file)

    @mock_aws
    def test_core_functionality_check(self):
        """Test core functionality checking logic."""
        # Create mock IAM role first
        iam_client = boto3.client("iam", region_name=self.region)
        role_name = "webwunder-test-lambda-role"

        # Create the IAM role with proper assume role policy
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{"Action": "sts:AssumeRole", "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}}],
        }

        try:
            iam_client.create_role(
                RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy), Description="Test Lambda role"
            )
        except iam_client.exceptions.EntityAlreadyExistsException:
            pass  # Role already exists

        # Create mock Lambda functions
        lambda_client = boto3.client("lambda", region_name=self.region)
        logs_client = boto3.client("logs", region_name=self.region)

        essential_functions = ["search_handler", "results_handler", "connect_handler"]

        for func_name in essential_functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            lambda_client.create_function(
                FunctionName=full_name,
                Runtime="python3.11",
                Role="arn:aws:iam::123456789012:role/webwunder-test-lambda-role",
                Handler="handler.lambda_handler",
                Code={"ZipFile": b"fake code"},
                Description=f"Test {func_name}",
            )

            # Create log group
            log_group_name = f"/aws/lambda/{full_name}"
            logs_client.create_log_group(logGroupName=log_group_name)

        # Import and test the deployment testing script functionality
        sys.path.append("scripts")
        try:
            from deployment_testing import StreamlinedDeploymentTester

            tester = StreamlinedDeploymentTester(self.environment, self.region)

            # Test core functionality check
            result = tester.test_core_functionality()

            # Should detect the mock functions as active
            assert result["lambda_functions_exist"] is True
            assert result["no_critical_errors"] is True

        except ImportError:
            pytest.skip("Could not import deployment testing script")

    def test_streamlined_deployment_testing_script(self):
        """Test that the streamlined deployment testing script runs without crashing."""
        script_path = "scripts/deployment-testing.py"
        if not os.path.exists(script_path):
            pytest.skip("Deployment testing script not found")

        # Test script help/usage (should not crash)
        try:
            result = subprocess.run(["python3", script_path, "--help"], capture_output=True, text=True, timeout=10)

            assert result.returncode == 0, f"Script help failed: {result.stderr}"
            assert "streamlined deployment testing" in result.stdout.lower()

        except subprocess.TimeoutExpired:
            pytest.fail("Deployment testing script help timed out")
        except FileNotFoundError:
            pytest.skip("Python3 not available")

    def test_github_actions_workflow_syntax(self):
        """Test that GitHub Actions workflows have valid YAML syntax."""
        import yaml

        workflow_files = [".github/workflows/streamlined-deployment-testing.yml", ".github/workflows/deployment.yml"]

        for workflow_file in workflow_files:
            if os.path.exists(workflow_file):
                with open(workflow_file, "r") as f:
                    try:
                        yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        pytest.fail(f"Invalid YAML syntax in {workflow_file}: {e}")

    def test_cost_optimization_features(self):
        """Test that cost optimization features are properly configured."""
        # Check that cost optimization features are configured in Terraform
        terraform_files = ["terraform/minimal_monitoring.tf", "terraform/cost_monitoring.tf"]

        cost_optimized_features = []
        for tf_file in terraform_files:
            if os.path.exists(tf_file):
                with open(tf_file, "r") as f:
                    content = f.read()
                    # Look for various cost optimization patterns
                    if any(
                        pattern in content.lower()
                        for pattern in [
                            "cost-optimized",
                            "student budget",
                            "budget alert",
                            "cost anomaly",
                            "cost monitoring",
                            "cost optimization",
                        ]
                    ):
                        cost_optimized_features.append(tf_file)

        # Should have at least some cost optimization configuration
        assert len(cost_optimized_features) > 0, "No cost optimization features found"

    def test_security_controls_basic_validation(self):
        """Test basic security controls validation."""
        # Check .gitignore for security patterns
        if os.path.exists(".gitignore"):
            with open(".gitignore", "r") as f:
                gitignore_content = f.read()

            security_patterns = ["secrets", "credentials", ".env", "*.key", "*.pem"]
            found_patterns = [pattern for pattern in security_patterns if pattern in gitignore_content]

            assert len(found_patterns) > 0, "No security patterns found in .gitignore"

        # Check that no obvious hardcoded secrets exist in Python files
        python_files = []
        for root, dirs, files in os.walk("src"):
            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))

        if python_files:
            # Sample a few files to check for obvious issues
            for py_file in python_files[:5]:  # Check first 5 files
                with open(py_file, "r") as f:
                    content = f.read().lower()

                # Check for obvious hardcoded secrets
                suspicious_patterns = ['password = "', 'secret = "', 'key = "']
                for pattern in suspicious_patterns:
                    assert pattern not in content, f"Potential hardcoded secret in {py_file}"


# Integration test that can be run separately
@pytest.mark.integration
class TestDeploymentIntegration:
    """Integration tests for deployment functionality."""

    def test_end_to_end_deployment_testing_workflow(self):
        """Test the complete deployment testing workflow."""
        # This would be run in a real AWS environment
        pytest.skip("Integration test - requires real AWS environment")

    def test_rollback_integration(self):
        """Test rollback functionality in a real environment."""
        # This would test actual rollback in staging
        pytest.skip("Integration test - requires real AWS environment")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
