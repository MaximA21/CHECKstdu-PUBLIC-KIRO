#!/usr/bin/env python3
"""
Rollback script for WebWunder deployments.
Provides manual rollback capabilities for production deployments.
"""

import json
import sys
import boto3
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import time


class RollbackManager:
    """Manages rollback operations for WebWunder deployments."""

    def __init__(self, environment: str, region: str = "eu-central-1"):
        self.environment = environment
        self.region = region
        self.session = boto3.Session(region_name=region)
        self.lambda_client = self.session.client("lambda")
        self.apigateway_client = self.session.client("apigateway")
        self.s3_client = self.session.client("s3")

    def list_available_versions(self) -> Dict[str, List[Dict]]:
        """List available versions for rollback."""
        functions = [
            "search_handler",
            "results_handler",
            "connect_handler",
            "disconnect_handler",
            "authorizer",
            "requestor_handler",
        ]

        versions = {}

        for func_name in functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            try:
                response = self.lambda_client.list_versions_by_function(FunctionName=full_name, MaxItems=10)

                func_versions = []
                for version in response["Versions"]:
                    if version["Version"] != "$LATEST":
                        func_versions.append(
                            {
                                "version": version["Version"],
                                "description": version.get("Description", ""),
                                "last_modified": version["LastModified"],
                                "code_size": version["CodeSize"],
                            }
                        )

                # Sort by version number (descending)
                func_versions.sort(key=lambda x: int(x["version"]), reverse=True)
                versions[func_name] = func_versions

            except Exception as e:
                print(f"❌ Could not list versions for {func_name}: {str(e)}")
                versions[func_name] = []

        return versions

    def get_current_versions(self) -> Dict[str, str]:
        """Get current active versions for all functions."""
        functions = [
            "search_handler",
            "results_handler",
            "connect_handler",
            "disconnect_handler",
            "authorizer",
            "requestor_handler",
        ]

        current_versions = {}

        for func_name in functions:
            full_name = f"webwunder-{self.environment}-{func_name}"
            try:
                # Check LIVE alias
                response = self.lambda_client.get_alias(FunctionName=full_name, Name="LIVE")
                current_versions[func_name] = response["FunctionVersion"]

            except self.lambda_client.exceptions.ResourceNotFoundException:
                # No LIVE alias, check $LATEST
                try:
                    response = self.lambda_client.get_function(FunctionName=full_name)
                    current_versions[func_name] = response["Configuration"]["Version"]
                except Exception as e:
                    print(f"❌ Could not get current version for {func_name}: {str(e)}")
                    current_versions[func_name] = "unknown"
            except Exception as e:
                print(f"❌ Could not get current version for {func_name}: {str(e)}")
                current_versions[func_name] = "unknown"

        return current_versions

    def create_backup_before_rollback(self) -> str:
        """Create backup of current state before rollback."""
        backup_id = f"rollback-backup-{int(datetime.utcnow().timestamp())}"
        backup_data = {
            "backup_id": backup_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "environment": self.environment,
            "current_versions": self.get_current_versions(),
        }

        # Save backup locally
        backup_filename = f"{backup_id}.json"
        with open(backup_filename, "w") as f:
            json.dump(backup_data, f, indent=2)

        print(f"💾 Backup created: {backup_filename}")
        return backup_id

    def rollback_lambda_functions(self, target_versions: Dict[str, str]) -> bool:
        """Rollback Lambda functions to specified versions."""
        print("🔄 Starting Lambda function rollback...")

        success = True

        for func_name, target_version in target_versions.items():
            full_name = f"webwunder-{self.environment}-{func_name}"

            try:
                print(f"Rolling back {func_name} to version {target_version}...")

                # Update LIVE alias to target version
                self.lambda_client.update_alias(
                    FunctionName=full_name,
                    Name="LIVE",
                    FunctionVersion=target_version,
                    Description=f"Rollback to version {target_version} at {datetime.utcnow().isoformat()}",
                )

                print(f"✅ {func_name} rolled back to version {target_version}")

            except self.lambda_client.exceptions.ResourceNotFoundException:
                # Create LIVE alias if it doesn't exist
                try:
                    self.lambda_client.create_alias(
                        FunctionName=full_name,
                        Name="LIVE",
                        FunctionVersion=target_version,
                        Description=f"Rollback alias created for version {target_version}",
                    )
                    print(f"✅ {func_name} LIVE alias created for version {target_version}")
                except Exception as e:
                    print(f"❌ Failed to create LIVE alias for {func_name}: {str(e)}")
                    success = False

            except Exception as e:
                print(f"❌ Failed to rollback {func_name}: {str(e)}")
                success = False

        return success

    def rollback_api_gateway_canary(self) -> bool:
        """Remove API Gateway canary deployment."""
        print("🌐 Rolling back API Gateway canary deployment...")

        try:
            # Find the API
            apis = self.apigateway_client.get_rest_apis()
            target_api = None

            for api in apis["items"]:
                if f"webwunder-{self.environment}" in api["name"]:
                    target_api = api
                    break

            if not target_api:
                print(f"⚠️ No API Gateway found for {self.environment}")
                return True  # Not an error if no API exists

            api_id = target_api["id"]
            stage_name = "prod" if self.environment == "production" else self.environment

            # Remove canary settings
            self.apigateway_client.update_stage(
                restApiId=api_id, stageName=stage_name, patchOps=[{"op": "remove", "path": "/canarySettings"}]
            )

            print("✅ API Gateway canary deployment removed")
            return True

        except Exception as e:
            print(f"❌ Failed to rollback API Gateway canary: {str(e)}")
            return False

    def verify_rollback(self, expected_versions: Dict[str, str]) -> bool:
        """Verify that rollback was successful."""
        print("🔍 Verifying rollback...")

        current_versions = self.get_current_versions()
        success = True

        for func_name, expected_version in expected_versions.items():
            current_version = current_versions.get(func_name, "unknown")

            if current_version == expected_version:
                print(f"✅ {func_name}: version {current_version} (correct)")
            else:
                print(f"❌ {func_name}: version {current_version} (expected {expected_version})")
                success = False

        return success

    def execute_rollback(self, target_versions: Dict[str, str], skip_backup: bool = False) -> bool:
        """Execute complete rollback process."""
        print(f"🚨 Starting rollback for {self.environment} environment")
        print(f"Region: {self.region}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print("-" * 60)

        # Create backup unless skipped
        backup_id = None
        if not skip_backup:
            backup_id = self.create_backup_before_rollback()

        # Show rollback plan
        print("\n📋 Rollback Plan:")
        for func_name, target_version in target_versions.items():
            print(f"  {func_name}: → version {target_version}")

        # Confirm rollback
        if not self._confirm_rollback():
            print("❌ Rollback cancelled by user")
            return False

        success = True

        # Step 1: Rollback Lambda functions
        if not self.rollback_lambda_functions(target_versions):
            success = False

        # Step 2: Rollback API Gateway canary
        if not self.rollback_api_gateway_canary():
            success = False

        # Step 3: Wait for changes to propagate
        print("\n⏳ Waiting for changes to propagate...")
        time.sleep(30)

        # Step 4: Verify rollback
        if not self.verify_rollback(target_versions):
            success = False

        # Summary
        print("\n" + "=" * 60)
        if success:
            print("✅ ROLLBACK COMPLETED SUCCESSFULLY")
            if backup_id:
                print(f"💾 Backup ID: {backup_id}")
        else:
            print("❌ ROLLBACK COMPLETED WITH ERRORS")
            print("⚠️ Manual intervention may be required")
        print("=" * 60)

        return success

    def _confirm_rollback(self) -> bool:
        """Ask user to confirm rollback operation."""
        if self.environment == "production":
            print("\n⚠️ WARNING: This will rollback PRODUCTION environment!")
            print("This action cannot be undone automatically.")

            confirmation = input("\nType 'ROLLBACK PRODUCTION' to confirm: ")
            return confirmation == "ROLLBACK PRODUCTION"
        else:
            confirmation = input(f"\nConfirm rollback of {self.environment} environment? (y/N): ")
            return confirmation.lower() in ["y", "yes"]


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Rollback WebWunder deployment")
    parser.add_argument("environment", choices=["staging", "production"], help="Environment to rollback")
    parser.add_argument("--region", default="eu-central-1", help="AWS region (default: eu-central-1)")
    parser.add_argument("--list-versions", action="store_true", help="List available versions for rollback")
    parser.add_argument("--current-versions", action="store_true", help="Show current active versions")
    parser.add_argument("--target-version", help="Target version for all functions")
    parser.add_argument("--function-versions", help="JSON string with function-specific versions")
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating backup before rollback")
    parser.add_argument("--auto-confirm", action="store_true", help="Skip confirmation prompt (dangerous!)")

    args = parser.parse_args()

    # Create rollback manager
    manager = RollbackManager(args.environment, args.region)

    try:
        # List versions mode
        if args.list_versions:
            print(f"📋 Available versions for {args.environment}:")
            print("-" * 60)

            versions = manager.list_available_versions()
            for func_name, func_versions in versions.items():
                print(f"\n{func_name}:")
                if func_versions:
                    for version in func_versions[:5]:  # Show top 5
                        print(f"  Version {version['version']}: {version['description']} " f"({version['last_modified']})")
                else:
                    print("  No versions available")
            return

        # Current versions mode
        if args.current_versions:
            print(f"📋 Current versions for {args.environment}:")
            print("-" * 60)

            current = manager.get_current_versions()
            for func_name, version in current.items():
                print(f"{func_name}: version {version}")
            return

        # Rollback mode
        target_versions = {}

        if args.function_versions:
            # Parse JSON string with function-specific versions
            try:
                target_versions = json.loads(args.function_versions)
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in --function-versions: {e}")
                sys.exit(1)
        elif args.target_version:
            # Use same version for all functions
            functions = [
                "search_handler",
                "results_handler",
                "connect_handler",
                "disconnect_handler",
                "authorizer",
                "requestor_handler",
            ]
            target_versions = {func: args.target_version for func in functions}
        else:
            print("❌ Must specify either --target-version or --function-versions")
            sys.exit(1)

        # Override confirmation if auto-confirm is set
        if args.auto_confirm:
            manager._confirm_rollback = lambda: True

        # Execute rollback
        success = manager.execute_rollback(target_versions, args.skip_backup)

        if success:
            print("\n✅ Rollback completed successfully")
            sys.exit(0)
        else:
            print("\n❌ Rollback completed with errors")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Rollback interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n💥 Rollback failed with error: {str(e)}")
        sys.exit(3)


if __name__ == "__main__":
    main()
