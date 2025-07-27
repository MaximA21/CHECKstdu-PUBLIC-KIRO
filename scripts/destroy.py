#!/usr/bin/env python3
"""
Destroy script for WebWunder infrastructure.
Provides complete infrastructure destruction capabilities.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import boto3


class DestroyManager:
    """Manages complete infrastructure destruction for WebWunder deployments."""

    def __init__(self, environment: str, region: str = "eu-central-1"):
        self.environment = environment
        self.region = region
        self.session = boto3.Session(region_name=region)
        self.lambda_client = self.session.client("lambda")
        self.apigateway_client = self.session.client("apigateway")
        self.s3_client = self.session.client("s3")
        self.ecs_client = self.session.client("ecs")
        self.dynamodb_client = self.session.client("dynamodb")
        self.sqs_client = self.session.client("sqs")
        self.cloudwatch_client = self.session.client("cloudwatch")

    def list_resources(self) -> Dict[str, List[str]]:
        """List all resources that will be destroyed."""
        resources = {
            "lambda_functions": [],
            "api_gateways": [],
            "dynamodb_tables": [],
            "sqs_queues": [],
            "ecs_services": [],
            "cloudwatch_logs": [],
            "s3_buckets": []
        }

        # List Lambda functions
        try:
            paginator = self.lambda_client.get_paginator("list_functions")
            for page in paginator.paginate():
                for func in page["Functions"]:
                    if f"webwunder-{self.environment}" in func["FunctionName"]:
                        resources["lambda_functions"].append(func["FunctionName"])
        except Exception as e:
            print(f"❌ Could not list Lambda functions: {str(e)}")

        # List API Gateways
        try:
            response = self.apigateway_client.get_rest_apis()
            for api in response["items"]:
                if f"webwunder-{self.environment}" in api["name"].lower():
                    resources["api_gateways"].append(api["name"])
        except Exception as e:
            print(f"❌ Could not list API Gateways: {str(e)}")

        # List DynamoDB tables
        try:
            response = self.dynamodb_client.list_tables()
            for table in response["TableNames"]:
                if f"webwunder-{self.environment}" in table.lower():
                    resources["dynamodb_tables"].append(table)
        except Exception as e:
            print(f"❌ Could not list DynamoDB tables: {str(e)}")

        # List SQS queues
        try:
            response = self.sqs_client.list_queues()
            if "QueueUrls" in response:
                for queue_url in response["QueueUrls"]:
                    queue_name = queue_url.split("/")[-1]
                    if f"webwunder-{self.environment}" in queue_name.lower():
                        resources["sqs_queues"].append(queue_name)
        except Exception as e:
            print(f"❌ Could not list SQS queues: {str(e)}")

        # List ECS services
        try:
            response = self.ecs_client.list_clusters()
            for cluster_arn in response["clusterArns"]:
                if f"webwunder-{self.environment}" in cluster_arn.lower():
                    services_response = self.ecs_client.list_services(cluster=cluster_arn)
                    for service_arn in services_response["serviceArns"]:
                        resources["ecs_services"].append(service_arn)
        except Exception as e:
            print(f"❌ Could not list ECS services: {str(e)}")

        return resources

    def create_backup_before_destroy(self) -> str:
        """Create backup of current state before destruction."""
        backup_id = f"destroy-backup-{self.environment}-{int(datetime.utcnow().timestamp())}"
        
        print(f"💾 Creating backup: {backup_id}")
        
        backup_data = {
            "backup_id": backup_id,
            "environment": self.environment,
            "timestamp": datetime.utcnow().isoformat(),
            "resources": self.list_resources()
        }
        
        # Save backup to file
        backup_file = f"backup-{backup_id}.json"
        with open(backup_file, "w") as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print(f"✅ Backup saved to: {backup_file}")
        return backup_id

    def destroy_lambda_functions(self) -> bool:
        """Destroy all Lambda functions for the environment."""
        print("🗑️ Destroying Lambda functions...")
        
        try:
            paginator = self.lambda_client.get_paginator("list_functions")
            for page in paginator.paginate():
                for func in page["Functions"]:
                    if f"webwunder-{self.environment}" in func["FunctionName"]:
                        func_name = func["FunctionName"]
                        print(f"  🗑️ Deleting {func_name}...")
                        
                        # Delete all versions except $LATEST
                        versions_response = self.lambda_client.list_versions_by_function(FunctionName=func_name)
                        for version in versions_response["Versions"]:
                            if version["Version"] != "$LATEST":
                                try:
                                    self.lambda_client.delete_function(
                                        FunctionName=func_name,
                                        Qualifier=version["Version"]
                                    )
                                except Exception as e:
                                    print(f"    ⚠️ Could not delete version {version['Version']}: {str(e)}")
                        
                        # Delete aliases
                        aliases_response = self.lambda_client.list_aliases(FunctionName=func_name)
                        for alias in aliases_response["Aliases"]:
                            try:
                                self.lambda_client.delete_alias(
                                    FunctionName=func_name,
                                    Name=alias["Name"]
                                )
                            except Exception as e:
                                print(f"    ⚠️ Could not delete alias {alias['Name']}: {str(e)}")
                        
                        # Delete the function itself
                        try:
                            self.lambda_client.delete_function(FunctionName=func_name)
                            print(f"    ✅ Deleted {func_name}")
                        except Exception as e:
                            print(f"    ❌ Could not delete {func_name}: {str(e)}")
                            return False
            
            print("✅ Lambda functions destruction completed")
            return True
            
        except Exception as e:
            print(f"❌ Lambda functions destruction failed: {str(e)}")
            return False

    def destroy_api_gateways(self) -> bool:
        """Destroy API Gateways for the environment."""
        print("🗑️ Destroying API Gateways...")
        
        try:
            response = self.apigateway_client.get_rest_apis()
            for api in response["items"]:
                if f"webwunder-{self.environment}" in api["name"].lower():
                    api_id = api["id"]
                    api_name = api["name"]
                    print(f"  🗑️ Deleting API Gateway: {api_name} ({api_id})...")
                    
                    try:
                        # Delete all stages first
                        stages_response = self.apigateway_client.get_stages(restApiId=api_id)
                        for stage in stages_response["item"]:
                            try:
                                self.apigateway_client.delete_stage(
                                    restApiId=api_id,
                                    stageName=stage["stageName"]
                                )
                            except Exception as e:
                                print(f"    ⚠️ Could not delete stage {stage['stageName']}: {str(e)}")
                        
                        # Delete the API
                        self.apigateway_client.delete_rest_api(restApiId=api_id)
                        print(f"    ✅ Deleted API Gateway: {api_name}")
                        
                    except Exception as e:
                        print(f"    ❌ Could not delete API Gateway {api_name}: {str(e)}")
                        return False
            
            print("✅ API Gateways destruction completed")
            return True
            
        except Exception as e:
            print(f"❌ API Gateways destruction failed: {str(e)}")
            return False

    def destroy_dynamodb_tables(self) -> bool:
        """Destroy DynamoDB tables for the environment."""
        print("🗑️ Destroying DynamoDB tables...")
        
        try:
            response = self.dynamodb_client.list_tables()
            for table in response["TableNames"]:
                if f"webwunder-{self.environment}" in table.lower():
                    print(f"  🗑️ Deleting DynamoDB table: {table}...")
                    
                    try:
                        self.dynamodb_client.delete_table(TableName=table)
                        print(f"    ✅ Deleted DynamoDB table: {table}")
                    except Exception as e:
                        print(f"    ❌ Could not delete DynamoDB table {table}: {str(e)}")
                        return False
            
            print("✅ DynamoDB tables destruction completed")
            return True
            
        except Exception as e:
            print(f"❌ DynamoDB tables destruction failed: {str(e)}")
            return False

    def destroy_sqs_queues(self) -> bool:
        """Destroy SQS queues for the environment."""
        print("🗑️ Destroying SQS queues...")
        
        try:
            response = self.sqs_client.list_queues()
            if "QueueUrls" in response:
                for queue_url in response["QueueUrls"]:
                    queue_name = queue_url.split("/")[-1]
                    if f"webwunder-{self.environment}" in queue_name.lower():
                        print(f"  🗑️ Deleting SQS queue: {queue_name}...")
                        
                        try:
                            self.sqs_client.delete_queue(QueueUrl=queue_url)
                            print(f"    ✅ Deleted SQS queue: {queue_name}")
                        except Exception as e:
                            print(f"    ❌ Could not delete SQS queue {queue_name}: {str(e)}")
                            return False
            
            print("✅ SQS queues destruction completed")
            return True
            
        except Exception as e:
            print(f"❌ SQS queues destruction failed: {str(e)}")
            return False

    def destroy_terraform_infrastructure(self) -> bool:
        """Destroy infrastructure using Terraform."""
        print("🗑️ Destroying Terraform infrastructure...")
        
        try:
            import subprocess
            import os
            
            # Change to terraform directory
            terraform_dir = "terraform"
            if not os.path.exists(terraform_dir):
                print(f"❌ Terraform directory not found: {terraform_dir}")
                return False
            
            os.chdir(terraform_dir)
            
            # Initialize Terraform
            print("  🔧 Initializing Terraform...")
            result = subprocess.run(["terraform", "init"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Terraform init failed: {result.stderr}")
                return False
            
            # Select workspace
            workspace_name = self.environment
            print(f"  🔧 Selecting workspace: {workspace_name}")
            result = subprocess.run(["terraform", "workspace", "select", workspace_name], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"⚠️ Could not select workspace {workspace_name}, creating it...")
                result = subprocess.run(["terraform", "workspace", "new", workspace_name], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"❌ Could not create workspace {workspace_name}: {result.stderr}")
                    return False
            
            # Destroy infrastructure
            print("  🗑️ Running terraform destroy...")
            result = subprocess.run(
                ["terraform", "destroy", "-auto-approve", "-var", f"environment={self.environment}"],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                print("✅ Terraform infrastructure destruction completed")
                return True
            else:
                print(f"❌ Terraform destroy failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Terraform infrastructure destruction failed: {str(e)}")
            return False

    def execute_destroy(self, skip_backup: bool = False, skip_terraform: bool = False) -> bool:
        """Execute complete infrastructure destruction."""
        print(f"🚨 STARTING COMPLETE INFRASTRUCTURE DESTRUCTION FOR {self.environment.upper()}")
        print("=" * 80)
        
        # List resources that will be destroyed
        print("\n📋 Resources that will be destroyed:")
        resources = self.list_resources()
        for resource_type, resource_list in resources.items():
            if resource_list:
                print(f"  {resource_type}: {len(resource_list)} items")
                for resource in resource_list[:3]:  # Show first 3
                    print(f"    - {resource}")
                if len(resource_list) > 3:
                    print(f"    ... and {len(resource_list) - 3} more")
            else:
                print(f"  {resource_type}: 0 items")
        
        # Create backup
        backup_id = None
        if not skip_backup:
            backup_id = self.create_backup_before_destroy()
        
        # Confirm destruction
        if not self._confirm_destroy():
            print("❌ Destruction cancelled by user")
            return False
        
        print("\n🚨 EXECUTING INFRASTRUCTURE DESTRUCTION")
        print("=" * 80)
        
        success = True
        
        # Step 1: Destroy Lambda functions
        if not self.destroy_lambda_functions():
            print("⚠️ Lambda functions destruction had errors")
            success = False
        
        # Step 2: Destroy API Gateways
        if not self.destroy_api_gateways():
            print("⚠️ API Gateways destruction had errors")
            success = False
        
        # Step 3: Destroy DynamoDB tables
        if not self.destroy_dynamodb_tables():
            print("⚠️ DynamoDB tables destruction had errors")
            success = False
        
        # Step 4: Destroy SQS queues
        if not self.destroy_sqs_queues():
            print("⚠️ SQS queues destruction had errors")
            success = False
        
        # Step 5: Destroy Terraform infrastructure (if not skipped)
        if not skip_terraform:
            if not self.destroy_terraform_infrastructure():
                print("⚠️ Terraform infrastructure destruction had errors")
                success = False
        
        print("\n" + "=" * 80)
        if success:
            print("✅ INFRASTRUCTURE DESTRUCTION COMPLETED SUCCESSFULLY")
            if backup_id:
                print(f"💾 Backup available: backup-{backup_id}.json")
        else:
            print("❌ INFRASTRUCTURE DESTRUCTION COMPLETED WITH ERRORS")
            print("⚠️ Some resources may still exist - check manually")
        
        return success

    def _confirm_destroy(self) -> bool:
        """Ask user to confirm destruction operation."""
        if self.environment == "production":
            print("\n⚠️ WARNING: This will DESTROY ALL PRODUCTION INFRASTRUCTURE!")
            print("⚠️ This action is IRREVERSIBLE!")
            print("⚠️ All data will be LOST!")
            
            confirmation = input("\nType 'DESTROY PRODUCTION' to confirm: ")
            return confirmation == "DESTROY PRODUCTION"
        else:
            print(f"\n⚠️ WARNING: This will destroy all {self.environment} infrastructure!")
            print("⚠️ This action is IRREVERSIBLE!")
            
            confirmation = input(f"\nConfirm destruction of {self.environment} environment? (y/N): ")
            return confirmation.lower() == "y"


def main():
    parser = argparse.ArgumentParser(description="Destroy WebWunder infrastructure")
    parser.add_argument("environment", choices=["staging", "production"], help="Environment to destroy")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument("--list-resources", action="store_true", help="List resources that will be destroyed")
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating backup before destruction")
    parser.add_argument("--skip-terraform", action="store_true", help="Skip Terraform destruction (manual cleanup only)")
    parser.add_argument("--auto-confirm", action="store_true", help="Skip confirmation prompts (use with caution)")

    args = parser.parse_args()

    # Create destroy manager
    manager = DestroyManager(args.environment, args.region)

    try:
        if args.list_resources:
            # List resources mode
            print(f"📋 Resources in {args.environment} environment:")
            resources = manager.list_resources()
            
            for resource_type, resource_list in resources.items():
                print(f"\n{resource_type.upper()}:")
                if resource_list:
                    for resource in resource_list:
                        print(f"  - {resource}")
                else:
                    print("  (no resources found)")
            
            return 0

        # Auto-confirm mode
        if args.auto_confirm:
            manager._confirm_destroy = lambda: True

        # Execute destruction
        success = manager.execute_destroy(args.skip_backup, args.skip_terraform)

        if success:
            print("\n✅ Infrastructure destruction completed successfully")
            return 0
        else:
            print("\n❌ Infrastructure destruction completed with errors")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️ Infrastructure destruction interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Infrastructure destruction failed with error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 