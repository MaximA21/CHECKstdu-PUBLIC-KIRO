#!/usr/bin/env python3
"""
Student Budget Validation Script
Validates that cost optimizations are properly implemented and working.
"""

import boto3
import json
import sys
from typing import Dict, List, Any
from botocore.exceptions import ClientError, NoCredentialsError


class StudentBudgetValidator:
    def __init__(self, region: str = "eu-central-1", project_name: str = "provider-comparison", environment: str = "dev"):
        """Initialize AWS clients for validation."""
        self.region = region
        self.project_name = project_name
        self.environment = environment

        try:
            self.logs = boto3.client("logs", region_name=region)
            self.dynamodb = boto3.client("dynamodb", region_name=region)
            self.backup = boto3.client("backup", region_name=region)
            self.cloudwatch = boto3.client("cloudwatch", region_name=region)
            self.kms = boto3.client("kms", region_name=region)
            self.kinesis = boto3.client("kinesis", region_name=region)
        except NoCredentialsError:
            print("❌ AWS credentials not found. Please configure your credentials.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error initializing AWS clients: {e}")
            sys.exit(1)

    def validate_kinesis_stream_removed(self) -> Dict[str, Any]:
        """Validate that Kinesis stream has been removed."""
        stream_name = f"{self.project_name}-{self.environment}-log-stream"

        try:
            self.kinesis.describe_stream(StreamName=stream_name)
            return {
                "status": "FAIL",
                "message": f"Kinesis stream {stream_name} still exists",
                "cost_impact": "+$28/month",
                "action": "Set enable_kinesis_stream = false and run terraform apply",
            }
        except ClientError as e:
            if "ResourceNotFoundException" in str(e):
                return {
                    "status": "PASS",
                    "message": "Kinesis stream successfully removed",
                    "cost_impact": "-$28/month",
                    "action": "None required",
                }
            else:
                return {
                    "status": "ERROR",
                    "message": f"Error checking Kinesis stream: {e}",
                    "cost_impact": "Unknown",
                    "action": "Check AWS permissions",
                }

    def validate_aws_backup_disabled(self) -> Dict[str, Any]:
        """Validate that AWS Backup has been disabled."""
        vault_name = f"{self.project_name}-{self.environment}-dynamodb-backup-vault"

        try:
            self.backup.describe_backup_vault(BackupVaultName=vault_name)
            return {
                "status": "FAIL",
                "message": f"AWS Backup vault {vault_name} still exists",
                "cost_impact": "+$20-50/month",
                "action": "Set enable_aws_backup = false and run terraform apply",
            }
        except ClientError as e:
            if "ResourceNotFoundException" in str(e):
                return {
                    "status": "PASS",
                    "message": "AWS Backup vault successfully removed",
                    "cost_impact": "-$20-50/month",
                    "action": "None required",
                }
            else:
                return {
                    "status": "ERROR",
                    "message": f"Error checking AWS Backup: {e}",
                    "cost_impact": "Unknown",
                    "action": "Check AWS permissions",
                }

    def validate_log_retention(self) -> Dict[str, Any]:
        """Validate that log retention has been reduced to 7 days."""
        log_groups_to_check = [
            f"/aws/lambda/{self.project_name}-{self.environment}-connect_handler",
            f"/aws/lambda/{self.project_name}-{self.environment}-search_handler",
            f"/aws/lambda/{self.project_name}-{self.environment}-results_handler",
        ]

        issues = []
        optimized_groups = 0

        for log_group_name in log_groups_to_check:
            try:
                response = self.logs.describe_log_groups(logGroupNamePrefix=log_group_name)

                if response["logGroups"]:
                    log_group = response["logGroups"][0]
                    retention_days = log_group.get("retentionInDays", "Never expire")

                    if retention_days != 7:
                        issues.append(f"{log_group_name}: {retention_days} days (should be 7)")
                    else:
                        optimized_groups += 1

            except ClientError:
                issues.append(f"{log_group_name}: Not found")

        if issues:
            return {
                "status": "PARTIAL" if optimized_groups > 0 else "FAIL",
                "message": f'Log retention issues found: {", ".join(issues)}',
                "cost_impact": f"+${len(issues) * 2}/month",
                "action": "Set log_retention_days = 7, lambda_log_retention_days = 7",
            }
        else:
            return {
                "status": "PASS",
                "message": f"All {len(log_groups_to_check)} log groups have 7-day retention",
                "cost_impact": "-$10-15/month",
                "action": "None required",
            }

    def validate_kms_keys_removed(self) -> Dict[str, Any]:
        """Validate that custom KMS keys have been removed."""
        key_aliases_to_check = [
            f"alias/{self.project_name}-{self.environment}-logs-key",
            f"alias/{self.project_name}-{self.environment}-backup-key",
        ]

        existing_keys = []

        for alias in key_aliases_to_check:
            try:
                self.kms.describe_key(KeyId=alias)
                existing_keys.append(alias)
            except ClientError as e:
                if "NotFoundException" not in str(e):
                    existing_keys.append(f"{alias} (error: {e})")

        if existing_keys:
            return {
                "status": "FAIL",
                "message": f'Custom KMS keys still exist: {", ".join(existing_keys)}',
                "cost_impact": f"+${len(existing_keys)}/month",
                "action": "Set enable_custom_kms_keys = false and run terraform apply",
            }
        else:
            return {
                "status": "PASS",
                "message": "Custom KMS keys successfully removed",
                "cost_impact": "-$2/month",
                "action": "None required",
            }

    def validate_dynamodb_pitr_enabled(self) -> Dict[str, Any]:
        """Validate that DynamoDB point-in-time recovery is still enabled."""
        tables_to_check = [
            f"{self.project_name}-{self.environment}-results",
            f"{self.project_name}-{self.environment}-analytics",
        ]

        pitr_disabled = []

        for table_name in tables_to_check:
            try:
                response = self.dynamodb.describe_continuous_backups(TableName=table_name)
                pitr_status = response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"][
                    "PointInTimeRecoveryStatus"
                ]

                if pitr_status != "ENABLED":
                    pitr_disabled.append(table_name)

            except ClientError:
                pitr_disabled.append(f"{table_name} (not found)")

        if pitr_disabled:
            return {
                "status": "FAIL",
                "message": f'PITR disabled on tables: {", ".join(pitr_disabled)}',
                "cost_impact": "Risk of data loss",
                "action": "Ensure point_in_time_recovery.enabled = true in DynamoDB configuration",
            }
        else:
            return {
                "status": "PASS",
                "message": f"PITR enabled on all {len(tables_to_check)} tables",
                "cost_impact": "Data protection maintained",
                "action": "None required",
            }

    def validate_cloudwatch_alarms(self) -> Dict[str, Any]:
        """Validate CloudWatch alarms optimization."""
        try:
            response = self.cloudwatch.describe_alarms()
            project_alarms = [
                alarm
                for alarm in response["MetricAlarms"]
                if self.project_name in alarm["AlarmName"] and self.environment in alarm["AlarmName"]
            ]

            alarm_count = len(project_alarms)

            if alarm_count > 5:
                return {
                    "status": "PARTIAL",
                    "message": f"{alarm_count} alarms found (consider reducing for student budget)",
                    "cost_impact": f"+${(alarm_count - 3) * 0.1}/month",
                    "action": "Set minimal_cloudwatch_alarms = true for further optimization",
                }
            elif alarm_count >= 2:
                return {
                    "status": "PASS",
                    "message": f"{alarm_count} essential alarms configured",
                    "cost_impact": "-$3-5/month",
                    "action": "None required",
                }
            else:
                return {
                    "status": "WARN",
                    "message": f"Only {alarm_count} alarms found (may need essential monitoring)",
                    "cost_impact": "Risk of missing critical issues",
                    "action": "Ensure at least basic failure monitoring is in place",
                }

        except ClientError as e:
            return {
                "status": "ERROR",
                "message": f"Error checking CloudWatch alarms: {e}",
                "cost_impact": "Unknown",
                "action": "Check AWS permissions",
            }

    def calculate_estimated_savings(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate estimated monthly savings from optimizations."""
        total_savings = 0
        optimization_status = {}

        savings_map = {
            "kinesis": 28,
            "backup": 35,  # Average of 20-50
            "logs": 12,  # Average of 10-15
            "kms": 2,
            "alarms": 4,  # Average of 3-5
        }

        for result in validation_results:
            if "kinesis" in result.get("message", "").lower():
                if result["status"] == "PASS":
                    total_savings += savings_map["kinesis"]
                    optimization_status["kinesis"] = "optimized"
                else:
                    optimization_status["kinesis"] = "not_optimized"

            elif "backup" in result.get("message", "").lower():
                if result["status"] == "PASS":
                    total_savings += savings_map["backup"]
                    optimization_status["backup"] = "optimized"
                else:
                    optimization_status["backup"] = "not_optimized"

            elif "log" in result.get("message", "").lower():
                if result["status"] == "PASS":
                    total_savings += savings_map["logs"]
                    optimization_status["logs"] = "optimized"
                else:
                    optimization_status["logs"] = "not_optimized"

            elif "kms" in result.get("message", "").lower():
                if result["status"] == "PASS":
                    total_savings += savings_map["kms"]
                    optimization_status["kms"] = "optimized"
                else:
                    optimization_status["kms"] = "not_optimized"

            elif "alarm" in result.get("message", "").lower():
                if result["status"] == "PASS":
                    total_savings += savings_map["alarms"]
                    optimization_status["alarms"] = "optimized"
                else:
                    optimization_status["alarms"] = "not_optimized"

        # Estimate remaining cost
        baseline_cost = 100  # Approximate baseline before optimizations
        estimated_monthly_cost = baseline_cost - total_savings

        return {
            "total_monthly_savings": total_savings,
            "estimated_monthly_cost": estimated_monthly_cost,
            "optimization_status": optimization_status,
            "target_achieved": estimated_monthly_cost <= 20,
        }

    def run_validation(self) -> Dict[str, Any]:
        """Run all validation checks."""
        print(f"🔍 Validating student budget optimizations for {self.project_name}-{self.environment}")
        print("=" * 70)

        validation_results = []

        # Run all validation checks
        checks = [
            ("Kinesis Stream Removal", self.validate_kinesis_stream_removed),
            ("AWS Backup Disabled", self.validate_aws_backup_disabled),
            ("Log Retention Optimization", self.validate_log_retention),
            ("Custom KMS Keys Removal", self.validate_kms_keys_removed),
            ("DynamoDB PITR Status", self.validate_dynamodb_pitr_enabled),
            ("CloudWatch Alarms Optimization", self.validate_cloudwatch_alarms),
        ]

        for check_name, check_function in checks:
            print(f"\n🔍 {check_name}:")
            result = check_function()
            result["check_name"] = check_name
            validation_results.append(result)

            status_emoji = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️", "WARN": "⚠️", "ERROR": "🚨"}

            print(f"   {status_emoji.get(result['status'], '❓')} Status: {result['status']}")
            print(f"   📝 Message: {result['message']}")
            print(f"   💰 Cost Impact: {result['cost_impact']}")
            print(f"   🔧 Action: {result['action']}")

        # Calculate savings summary
        savings_summary = self.calculate_estimated_savings(validation_results)

        print(f"\n💰 COST OPTIMIZATION SUMMARY")
        print("=" * 40)
        print(f"📊 Total monthly savings: ${savings_summary['total_monthly_savings']}")
        print(f"🎯 Estimated monthly cost: ${savings_summary['estimated_monthly_cost']}")
        print(f"✅ Target achieved: {'Yes' if savings_summary['target_achieved'] else 'No'}")

        if savings_summary["target_achieved"]:
            print("🎉 Congratulations! Student budget target (15-20 EUR/month) achieved!")
        else:
            print("⚠️  Additional optimizations needed to reach student budget target.")

        print(f"\n📋 Optimization Status:")
        for opt, status in savings_summary["optimization_status"].items():
            status_emoji = "✅" if status == "optimized" else "❌"
            print(f"   {status_emoji} {opt.title()}: {status}")

        return {
            "validation_results": validation_results,
            "savings_summary": savings_summary,
            "overall_status": "PASS" if savings_summary["target_achieved"] else "NEEDS_WORK",
        }


def main():
    """Main function to run validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate student budget cost optimizations")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument("--project", default="provider-comparison", help="Project name")
    parser.add_argument("--environment", default="dev", help="Environment name")
    parser.add_argument("--output", help="Output file for validation results (JSON)")

    args = parser.parse_args()

    validator = StudentBudgetValidator(args.region, args.project, args.environment)
    results = validator.run_validation()

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📄 Validation results saved to {args.output}")

    # Exit with appropriate code
    sys.exit(0 if results["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
