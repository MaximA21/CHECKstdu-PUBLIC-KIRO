#!/usr/bin/env python3
"""
Validation script for shared AWS resources configuration.
Validates DynamoDB tables, SQS queues, Step Functions, and backup configuration.
"""

import boto3
import json
import sys
from typing import Dict, List, Any
from botocore.exceptions import ClientError, NoCredentialsError


class SharedResourcesValidator:
    def __init__(self, region: str = "eu-central-1"):
        """Initialize AWS clients for the specified region."""
        self.region = region
        try:
            self.dynamodb = boto3.client("dynamodb", region_name=region)
            self.sqs = boto3.client("sqs", region_name=region)
            self.stepfunctions = boto3.client("stepfunctions", region_name=region)
            self.backup = boto3.client("backup", region_name=region)
            self.logs = boto3.client("logs", region_name=region)
            self.cloudwatch = boto3.client("cloudwatch", region_name=region)
            self.kms = boto3.client("kms", region_name=region)
        except NoCredentialsError:
            print("❌ AWS credentials not found. Please configure your credentials.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error initializing AWS clients: {e}")
            sys.exit(1)

    def validate_dynamodb_tables(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Validate DynamoDB tables configuration."""
        print("🔍 Validating DynamoDB tables...")
        results = {}

        tables_to_check = [f"{project_name}-{environment}-results", f"{project_name}-{environment}-analytics"]

        for table_name in tables_to_check:
            try:
                response = self.dynamodb.describe_table(TableName=table_name)
                table = response["Table"]

                results[table_name] = {
                    "exists": True,
                    "status": table["TableStatus"],
                    "billing_mode": table["BillingModeSummary"]["BillingMode"],
                    "point_in_time_recovery": self._check_pitr(table_name),
                    "encryption": table.get("SSEDescription", {}).get("Status", "DISABLED"),
                    "global_secondary_indexes": len(table.get("GlobalSecondaryIndexes", [])),
                    "region": self.region,
                }

                if table["TableStatus"] == "ACTIVE":
                    print(f"✅ Table {table_name}: Active")
                else:
                    print(f"⚠️  Table {table_name}: {table['TableStatus']}")

            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    results[table_name] = {"exists": False, "error": "Table not found"}
                    print(f"❌ Table {table_name}: Not found")
                else:
                    results[table_name] = {"exists": False, "error": str(e)}
                    print(f"❌ Table {table_name}: Error - {e}")

        return results

    def _check_pitr(self, table_name: str) -> bool:
        """Check if Point-in-Time Recovery is enabled for a table."""
        try:
            response = self.dynamodb.describe_continuous_backups(TableName=table_name)
            return (
                response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]["PointInTimeRecoveryStatus"]
                == "ENABLED"
            )
        except Exception:
            return False

    def validate_sqs_queues(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Validate SQS queues configuration."""
        print("🔍 Validating SQS queues...")
        results = {}

        queues_to_check = [
            f"{project_name}-{environment}-request-queue",
            f"{project_name}-{environment}-results-queue",
            f"{project_name}-{environment}-request-dlq",
            f"{project_name}-{environment}-results-dlq",
        ]

        for queue_name in queues_to_check:
            try:
                # Get queue URL
                response = self.sqs.get_queue_url(QueueName=queue_name)
                queue_url = response["QueueUrl"]

                # Get queue attributes
                attrs_response = self.sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
                attributes = attrs_response["Attributes"]

                results[queue_name] = {
                    "exists": True,
                    "url": queue_url,
                    "message_retention_seconds": attributes.get("MessageRetentionPeriod"),
                    "visibility_timeout_seconds": attributes.get("VisibilityTimeout"),
                    "kms_master_key_id": attributes.get("KmsMasterKeyId"),
                    "redrive_policy": attributes.get("RedrivePolicy"),
                    "region": self.region,
                }

                print(f"✅ Queue {queue_name}: Available")

            except ClientError as e:
                if e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue":
                    results[queue_name] = {"exists": False, "error": "Queue not found"}
                    print(f"❌ Queue {queue_name}: Not found")
                else:
                    results[queue_name] = {"exists": False, "error": str(e)}
                    print(f"❌ Queue {queue_name}: Error - {e}")

        return results

    def validate_step_functions(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Validate Step Functions configuration."""
        print("🔍 Validating Step Functions...")
        results = {}

        state_machine_name = f"{project_name}-{environment}-provider-workflow"

        try:
            # List state machines to find the ARN
            response = self.stepfunctions.list_state_machines()
            state_machine_arn = None

            for sm in response["stateMachines"]:
                if sm["name"] == state_machine_name:
                    state_machine_arn = sm["stateMachineArn"]
                    break

            if state_machine_arn:
                # Describe the state machine
                describe_response = self.stepfunctions.describe_state_machine(stateMachineArn=state_machine_arn)

                results[state_machine_name] = {
                    "exists": True,
                    "arn": state_machine_arn,
                    "status": describe_response["status"],
                    "type": describe_response["type"],
                    "logging_configuration": describe_response.get("loggingConfiguration", {}),
                    "tracing_configuration": describe_response.get("tracingConfiguration", {}),
                    "region": self.region,
                }

                print(f"✅ State Machine {state_machine_name}: {describe_response['status']}")
            else:
                results[state_machine_name] = {"exists": False, "error": "State machine not found"}
                print(f"❌ State Machine {state_machine_name}: Not found")

        except ClientError as e:
            results[state_machine_name] = {"exists": False, "error": str(e)}
            print(f"❌ State Machine {state_machine_name}: Error - {e}")

        return results

    def validate_backup_configuration(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Validate backup and disaster recovery configuration."""
        print("🔍 Validating backup configuration...")
        results = {}

        backup_vault_name = f"{project_name}-{environment}-dynamodb-backup-vault"
        backup_plan_name = f"{project_name}-{environment}-dynamodb-backup-plan"

        try:
            # Check backup vault
            vault_response = self.backup.describe_backup_vault(BackupVaultName=backup_vault_name)
            results["backup_vault"] = {
                "exists": True,
                "name": vault_response["BackupVaultName"],
                "arn": vault_response["BackupVaultArn"],
                "encryption_key_arn": vault_response.get("EncryptionKeyArn"),
                "region": self.region,
            }
            print(f"✅ Backup Vault {backup_vault_name}: Available")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                results["backup_vault"] = {"exists": False, "error": "Backup vault not found"}
                print(f"❌ Backup Vault {backup_vault_name}: Not found")
            else:
                results["backup_vault"] = {"exists": False, "error": str(e)}
                print(f"❌ Backup Vault {backup_vault_name}: Error - {e}")

        try:
            # List backup plans to find the one we're looking for
            plans_response = self.backup.list_backup_plans()
            backup_plan_id = None

            for plan in plans_response["BackupPlansList"]:
                if plan["BackupPlanName"] == backup_plan_name:
                    backup_plan_id = plan["BackupPlanId"]
                    break

            if backup_plan_id:
                plan_response = self.backup.get_backup_plan(BackupPlanId=backup_plan_id)
                results["backup_plan"] = {
                    "exists": True,
                    "id": backup_plan_id,
                    "name": plan_response["BackupPlan"]["BackupPlanName"],
                    "rules_count": len(plan_response["BackupPlan"]["Rules"]),
                    "region": self.region,
                }
                print(f"✅ Backup Plan {backup_plan_name}: Available")
            else:
                results["backup_plan"] = {"exists": False, "error": "Backup plan not found"}
                print(f"❌ Backup Plan {backup_plan_name}: Not found")

        except ClientError as e:
            results["backup_plan"] = {"exists": False, "error": str(e)}
            print(f"❌ Backup Plan {backup_plan_name}: Error - {e}")

        return results

    def validate_cloudwatch_logs(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Validate CloudWatch log groups configuration."""
        print("🔍 Validating CloudWatch log groups...")
        results = {}

        log_groups_to_check = [
            f"/aws/apigateway/{project_name}-{environment}-websocket",
            f"/aws/apigateway/{project_name}-{environment}-rest-api",
            f"/aws/stepfunctions/{project_name}-{environment}-provider-workflow",
        ]

        # Add Lambda function log groups
        lambda_functions = [
            "connect_handler",
            "disconnect_handler",
            "search_handler",
            "results_handler",
            "requestor_handler",
            "share_api",
            "authorizer",
            "address_normalizer",
            "ping_perfect_signer",
            "connection_limit_enforcer",
            "connection_router",
        ]

        for func in lambda_functions:
            log_groups_to_check.append(f"/aws/lambda/{project_name}-{environment}-{func}")

        for log_group_name in log_groups_to_check:
            try:
                response = self.logs.describe_log_groups(logGroupNamePrefix=log_group_name)

                if response["logGroups"]:
                    log_group = response["logGroups"][0]
                    results[log_group_name] = {
                        "exists": True,
                        "retention_in_days": log_group.get("retentionInDays"),
                        "kms_key_id": log_group.get("kmsKeyId"),
                        "stored_bytes": log_group.get("storedBytes", 0),
                        "region": self.region,
                    }
                    print(f"✅ Log Group {log_group_name}: Available")
                else:
                    results[log_group_name] = {"exists": False, "error": "Log group not found"}
                    print(f"❌ Log Group {log_group_name}: Not found")

            except ClientError as e:
                results[log_group_name] = {"exists": False, "error": str(e)}
                print(f"❌ Log Group {log_group_name}: Error - {e}")

        return results

    def validate_monitoring_alarms(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Validate CloudWatch alarms configuration."""
        print("🔍 Validating CloudWatch alarms...")
        results = {}

        try:
            response = self.cloudwatch.describe_alarms(AlarmNamePrefix=f"{project_name}-{environment}")

            alarms = response["MetricAlarms"]
            results["alarms_count"] = len(alarms)
            results["alarms"] = {}

            for alarm in alarms:
                alarm_name = alarm["AlarmName"]
                results["alarms"][alarm_name] = {
                    "state": alarm["StateValue"],
                    "metric_name": alarm["MetricName"],
                    "namespace": alarm["Namespace"],
                    "threshold": alarm["Threshold"],
                    "comparison_operator": alarm["ComparisonOperator"],
                }

                if alarm["StateValue"] == "OK":
                    print(f"✅ Alarm {alarm_name}: OK")
                elif alarm["StateValue"] == "ALARM":
                    print(f"🚨 Alarm {alarm_name}: ALARM")
                else:
                    print(f"⚠️  Alarm {alarm_name}: {alarm['StateValue']}")

        except ClientError as e:
            results = {"exists": False, "error": str(e)}
            print(f"❌ CloudWatch Alarms: Error - {e}")

        return results

    def run_validation(self, project_name: str = "provider-comparison", environment: str = "dev") -> Dict[str, Any]:
        """Run complete validation of shared AWS resources."""
        print(f"🚀 Starting validation for {project_name}-{environment} in {self.region}")
        print("=" * 60)

        validation_results = {
            "region": self.region,
            "project_name": project_name,
            "environment": environment,
            "timestamp": boto3.Session().region_name,
            "dynamodb_tables": self.validate_dynamodb_tables(project_name, environment),
            "sqs_queues": self.validate_sqs_queues(project_name, environment),
            "step_functions": self.validate_step_functions(project_name, environment),
            "backup_configuration": self.validate_backup_configuration(project_name, environment),
            "cloudwatch_logs": self.validate_cloudwatch_logs(project_name, environment),
            "monitoring_alarms": self.validate_monitoring_alarms(project_name, environment),
        }

        print("=" * 60)
        print("📊 Validation Summary:")

        # Count successful validations
        total_checks = 0
        successful_checks = 0

        for category, results in validation_results.items():
            if isinstance(results, dict) and category not in ["region", "project_name", "environment", "timestamp"]:
                if category == "monitoring_alarms":
                    if results.get("alarms_count", 0) > 0:
                        successful_checks += 1
                    total_checks += 1
                else:
                    for resource_name, resource_data in results.items():
                        total_checks += 1
                        if isinstance(resource_data, dict) and resource_data.get("exists", False):
                            successful_checks += 1

        success_rate = (successful_checks / total_checks * 100) if total_checks > 0 else 0
        print(f"✅ Successful checks: {successful_checks}/{total_checks} ({success_rate:.1f}%)")

        if success_rate >= 90:
            print("🎉 Shared resources are properly configured!")
            return validation_results
        elif success_rate >= 70:
            print("⚠️  Most resources are configured, but some issues need attention.")
            return validation_results
        else:
            print("❌ Significant configuration issues detected. Please review and fix.")
            return validation_results


def main():
    """Main function to run the validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate shared AWS resources configuration")
    parser.add_argument("--region", default="eu-central-1", help="AWS region (default: eu-central-1)")
    parser.add_argument("--project", default="provider-comparison", help="Project name")
    parser.add_argument("--environment", default="dev", help="Environment name")
    parser.add_argument("--output", help="Output file for validation results (JSON)")

    args = parser.parse_args()

    validator = SharedResourcesValidator(region=args.region)
    results = validator.run_validation(args.project, args.environment)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"📄 Validation results saved to {args.output}")

    # Exit with appropriate code
    total_resources = sum(
        len(category_results) if isinstance(category_results, dict) else 1
        for key, category_results in results.items()
        if key not in ["region", "project_name", "environment", "timestamp"]
    )

    successful_resources = 0
    for key, category_results in results.items():
        if key not in ["region", "project_name", "environment", "timestamp"]:
            if isinstance(category_results, dict):
                if key == "monitoring_alarms":
                    if category_results.get("alarms_count", 0) > 0:
                        successful_resources += 1
                else:
                    for resource_data in category_results.values():
                        if isinstance(resource_data, dict) and resource_data.get("exists", False):
                            successful_resources += 1

    success_rate = (successful_resources / total_resources * 100) if total_resources > 0 else 0

    if success_rate >= 90:
        sys.exit(0)  # Success
    elif success_rate >= 70:
        sys.exit(1)  # Warning
    else:
        sys.exit(2)  # Error


if __name__ == "__main__":
    main()
