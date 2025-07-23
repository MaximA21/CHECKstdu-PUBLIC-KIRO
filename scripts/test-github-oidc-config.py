#!/usr/bin/env python3
"""
Test script to validate GitHub OIDC Terraform configuration syntax
"""

import subprocess
import sys
import tempfile
import os
import shutil

def test_github_oidc_config():
    """Test the GitHub OIDC Terraform configuration in isolation."""
    
    print("🧪 Testing GitHub OIDC Terraform Configuration")
    print("=" * 50)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Copy required files to temp directory
        files_to_copy = [
            'terraform/github_oidc.tf',
            'terraform/s3_deployment_artifacts.tf',
            'terraform/providers.tf',
            'terraform/variables.tf'
        ]
        
        for file_path in files_to_copy:
            if os.path.exists(file_path):
                shutil.copy2(file_path, temp_dir)
                print(f"✅ Copied {file_path}")
            else:
                print(f"❌ File not found: {file_path}")
                return False
        
        # Create a minimal terraform.tfvars for testing
        tfvars_content = """
github_repository = "test-org/test-repo"
deployment_bucket_name = "test-deployment-bucket"
aws_region = "eu-central-1"
environment = "test"
project_name = "github-oidc-test"
"""
        
        with open(os.path.join(temp_dir, 'terraform.tfvars'), 'w') as f:
            f.write(tfvars_content)
        print("✅ Created test terraform.tfvars")
        
        # Add data source for aws_caller_identity since it's referenced
        data_tf_content = """
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
"""
        
        with open(os.path.join(temp_dir, 'data.tf'), 'w') as f:
            f.write(data_tf_content)
        print("✅ Created data.tf")
        
        # Change to temp directory and run terraform commands
        original_dir = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Initialize Terraform
            print("\n🔧 Running terraform init...")
            result = subprocess.run(['terraform', 'init'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ terraform init failed:")
                print(result.stderr)
                return False
            print("✅ terraform init successful")
            
            # Validate configuration
            print("\n🔍 Running terraform validate...")
            result = subprocess.run(['terraform', 'validate'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ terraform validate failed:")
                print(result.stderr)
                return False
            print("✅ terraform validate successful")
            
            # Format check
            print("\n📝 Running terraform fmt...")
            result = subprocess.run(['terraform', 'fmt', '-check'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"⚠️  terraform fmt found formatting issues:")
                print(result.stdout)
            else:
                print("✅ terraform fmt check passed")
            
            # Plan (dry run)
            print("\n📋 Running terraform plan...")
            result = subprocess.run(['terraform', 'plan', '-var-file=terraform.tfvars'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ terraform plan failed:")
                print(result.stderr)
                return False
            print("✅ terraform plan successful")
            
            # Show what would be created
            print("\n📊 Resources that would be created:")
            lines = result.stdout.split('\n')
            for line in lines:
                if '# aws_iam_' in line or '# aws_s3_' in line or '# random_' in line:
                    print(f"  {line}")
            
            return True
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False
        finally:
            os.chdir(original_dir)

if __name__ == '__main__':
    success = test_github_oidc_config()
    if success:
        print("\n🎉 GitHub OIDC Terraform configuration test passed!")
        print("\nThe configuration is syntactically correct and ready for deployment.")
        sys.exit(0)
    else:
        print("\n❌ GitHub OIDC Terraform configuration test failed!")
        print("\nPlease fix the issues above before proceeding.")
        sys.exit(1)