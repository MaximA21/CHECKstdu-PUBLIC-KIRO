#!/usr/bin/env python3
"""
AWS Cost Optimization Script for Shared Resources
Analyzes current usage and provides cost optimization recommendations.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class CostOptimizer:
    def __init__(self, region: str = "eu-central-1"):
        """Initialize AWS clients for cost analysis."""
        self.region = region
        try:
            self.ce = boto3.client("ce", region_name="us-east-1")  # Cost Explorer is only in us-east-1
            self.logs = boto3.client("logs", region_name=region)
            self.dynamodb = boto3.client("dynamodb", region_name=region)
            self.backup = boto3.client("backup", region_name=region)
            self.cloudwatch = boto3.client("cloudwatch", region_name=region)
        except NoCredentialsError:
            print("❌ AWS credentials not found. Please configure your credentials.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error initializing AWS clients: {e}")
            sys.exit(1)

    def get_monthly_costs(self, months_back: int = 3) -> Dict[str, Any]:
        """Get monthly costs for the last N months."""
        print("💰 Analyzing monthly costs...")

        end_date = datetime.now().replace(day=1)
        start_date = end_date - timedelta(days=months_back * 30)

        try:
            response = self.ce.get_cost_and_usage(
                TimePeriod={"Start": start_date.strftime("%Y-%m-%d"), "End": end_date.strftime("%Y-%m-%d")},
                Granularity="MONTHLY",
                Metrics=["BlendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            costs_by_service = {}
            total_cost = 0

            for result in response["ResultsByTime"]:
                period = result["TimePeriod"]["Start"]
                for group in result["Groups"]:
                    service = group["Keys"][0]
                    cost = float(group["Metrics"]["BlendedCost"]["Amount"])

                    if service not in costs_by_service:
                        costs_by_service[service] = []
                    costs_by_service[service].append({"period": period, "cost": cost})
                    total_cost += cost

            return {
                "costs_by_service": costs_by_service,
                "total_cost": total_cost,
                "analysis_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            }

        except ClientError as e:
            print(f"❌ Error getting cost data: {e}")
            return {}

    def analyze_log_usage(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Analyze CloudWatch log usage and storage."""
        print("📊 Analyzing CloudWatch log usage...")

        log_groups = [
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
            log_groups.append(f"/aws/lambda/{project_name}-{environment}-{func}")

        log_analysis = {}
        total_stored_bytes = 0
        total_monthly_cost = 0

        for log_group_name in log_groups:
            try:
                response = self.logs.describe_log_groups(logGroupNamePrefix=log_group_name)

                if response["logGroups"]:
                    log_group = response["logGroups"][0]
                    stored_bytes = log_group.get("storedBytes", 0)
                    retention_days = log_group.get("retentionInDays", "Never expire")

                    # Calculate monthly cost (approximate)
                    storage_gb = stored_bytes / (1024**3)
                    monthly_storage_cost = storage_gb * 0.03  # $0.03 per GB per month

                    log_analysis[log_group_name] = {
                        "stored_bytes": stored_bytes,
                        "stored_gb": round(storage_gb, 3),
                        "retention_days": retention_days,
                        "monthly_storage_cost": round(monthly_storage_cost, 2),
                    }

                    total_stored_bytes += stored_bytes
                    total_monthly_cost += monthly_storage_cost

            except ClientError:
                log_analysis[log_group_name] = {"status": "not_found"}

        return {
            "log_groups": log_analysis,
            "total_stored_gb": round(total_stored_bytes / (1024**3), 3),
            "estimated_monthly_cost": round(total_monthly_cost, 2),
            "optimization_potential": self._calculate_log_optimization_savings(log_analysis),
        }

    def _calculate_log_optimization_savings(self, log_analysis: Dict) -> Dict[str, Any]:
        """Calculate potential savings from log optimization."""
        savings_scenarios = {"reduce_retention_to_7_days": 0, "reduce_retention_to_14_days": 0, "remove_unused_log_groups": 0}

        for log_group, data in log_analysis.items():
            if isinstance(data, dict) and "monthly_storage_cost" in data:
                current_cost = data["monthly_storage_cost"]
                retention = data.get("retention_days", "Never expire")

                # Estimate savings based on retention reduction
                if isinstance(retention, int):
                    if retention > 14:
                        savings_scenarios["reduce_retention_to_14_days"] += current_cost * 0.3
                    if retention > 7:
                        savings_scenarios["reduce_retention_to_7_days"] += current_cost * 0.5

                # Check for potentially unused log groups (very low storage)
                if data.get("stored_gb", 0) < 0.001:  # Less than 1MB
                    savings_scenarios["remove_unused_log_groups"] += current_cost

        return {k: round(v, 2) for k, v in savings_scenarios.items()}

    def analyze_dynamodb_usage(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Analyze DynamoDB usage and costs."""
        print("🗄️  Analyzing DynamoDB usage...")

        tables = [f"{project_name}-{environment}-results", f"{project_name}-{environment}-analytics"]

        dynamodb_analysis = {}
        total_storage_cost = 0

        for table_name in tables:
            try:
                response = self.dynamodb.describe_table(TableName=table_name)
                table = response["Table"]

                table_size_bytes = table.get("TableSizeBytes", 0)
                item_count = table.get("ItemCount", 0)

                # Calculate storage cost
                storage_gb = table_size_bytes / (1024**3)
                monthly_storage_cost = storage_gb * 0.25  # $0.25 per GB per month

                # Estimate PITR cost (20% of storage cost)
                pitr_cost = monthly_storage_cost * 0.2

                dynamodb_analysis[table_name] = {
                    "size_bytes": table_size_bytes,
                    "size_gb": round(storage_gb, 3),
                    "item_count": item_count,
                    "monthly_storage_cost": round(monthly_storage_cost, 2),
                    "pitr_cost": round(pitr_cost, 2),
                    "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode", "Unknown"),
                }

                total_storage_cost += monthly_storage_cost + pitr_cost

            except ClientError:
                dynamodb_analysis[table_name] = {"status": "not_found"}

        return {"tables": dynamodb_analysis, "total_monthly_cost": round(total_storage_cost, 2)}

    def analyze_backup_costs(self, project_name: str, environment: str) -> Dict[str, Any]:
        """Analyze AWS Backup costs."""
        print("💾 Analyzing backup costs...")

        backup_vault_name = f"{project_name}-{environment}-dynamodb-backup-vault"

        try:
            # Get backup vault info
            vault_response = self.backup.describe_backup_vault(BackupVaultName=backup_vault_name)

            # List recovery points to estimate storage
            recovery_points = self.backup.list_recovery_points_by_backup_vault(BackupVaultName=backup_vault_name)

            total_backup_size = 0
            backup_count = len(recovery_points["RecoveryPoints"])

            for rp in recovery_points["RecoveryPoints"]:
                backup_size = rp.get("BackupSizeInBytes", 0)
                total_backup_size += backup_size

            # Estimate costs
            backup_storage_gb = total_backup_size / (1024**3)
            monthly_storage_cost = backup_storage_gb * 0.05  # $0.05 per GB per month

            # Estimate request costs (daily + weekly backups)
            monthly_requests = 30 + 4  # ~30 daily + 4 weekly
            request_cost = monthly_requests * 0.05

            return {
                "vault_name": backup_vault_name,
                "backup_count": backup_count,
                "total_backup_gb": round(backup_storage_gb, 3),
                "monthly_storage_cost": round(monthly_storage_cost, 2),
                "monthly_request_cost": round(request_cost, 2),
                "total_monthly_cost": round(monthly_storage_cost + request_cost, 2),
            }

        except ClientError as e:
            return {"status": "not_found", "error": str(e)}

    def get_optimization_recommendations(self, analysis_results: Dict) -> List[Dict[str, Any]]:
        """Generate cost optimization recommendations."""
        recommendations = []

        # Student Budget Optimizations (15-20 EUR/month target)
        recommendations.extend(
            [
                {
                    "category": "Student Budget - Kinesis",
                    "priority": "Critical",
                    "recommendation": "Remove expensive Kinesis stream",
                    "potential_savings": "$28/month",
                    "action": "Set enable_kinesis_stream = false in terraform.tfvars.student-budget",
                    "alternative": "Use CloudWatch Logs Insights for log analysis instead",
                },
                {
                    "category": "Student Budget - AWS Backup",
                    "priority": "Critical",
                    "recommendation": "Disable AWS Backup service",
                    "potential_savings": "$20-50/month",
                    "action": "Set enable_aws_backup = false in terraform.tfvars.student-budget",
                    "alternative": "Use DynamoDB point-in-time recovery only",
                },
                {
                    "category": "Student Budget - CloudWatch Logs",
                    "priority": "High",
                    "recommendation": "Reduce log retention to 7 days",
                    "potential_savings": "$10-15/month",
                    "action": "Set log_retention_days = 7, lambda_log_retention_days = 7",
                    "alternative": "Shorter retention reduces storage costs significantly",
                },
                {
                    "category": "Student Budget - KMS",
                    "priority": "Medium",
                    "recommendation": "Remove custom KMS keys",
                    "potential_savings": "$2/month",
                    "action": "Set enable_custom_kms_keys = false in terraform.tfvars.student-budget",
                    "alternative": "Use AWS managed keys for encryption",
                },
                {
                    "category": "Student Budget - CloudWatch Alarms",
                    "priority": "Medium",
                    "recommendation": "Consolidate to essential alarms only",
                    "potential_savings": "$3-5/month",
                    "action": "Set minimal_cloudwatch_alarms = true in terraform.tfvars.student-budget",
                    "alternative": "Keep only critical failure monitoring",
                },
            ]
        )

        # Log optimization recommendations
        if "log_analysis" in analysis_results:
            log_data = analysis_results["log_analysis"]
            if log_data.get("estimated_monthly_cost", 0) > 5:
                recommendations.append(
                    {
                        "category": "CloudWatch Logs",
                        "priority": "High",
                        "recommendation": "Further reduce log retention periods",
                        "potential_savings": f"${log_data['optimization_potential']['reduce_retention_to_7_days']}/month",
                        "action": "Already included in student budget configuration",
                    }
                )

        # DynamoDB optimization
        if "dynamodb_analysis" in analysis_results:
            dynamodb_data = analysis_results["dynamodb_analysis"]
            recommendations.append(
                {
                    "category": "DynamoDB",
                    "priority": "Low",
                    "recommendation": "Already optimized with on-demand billing",
                    "potential_savings": "$0/month",
                    "action": "No changes needed - already cost-optimized for low usage",
                }
            )

        # Backup optimization
        if "backup_analysis" in analysis_results:
            backup_data = analysis_results["backup_analysis"]
            recommendations.append(
                {
                    "category": "AWS Backup",
                    "priority": "Critical",
                    "recommendation": "Already included in student budget optimization",
                    "potential_savings": f"${backup_data.get('total_monthly_cost', 0)}/month",
                    "action": "Disable completely for student budget",
                }
            )

        return recommendations

    def generate_cost_report(self, project_name: str = "provider-comparison", environment: str = "dev") -> Dict[str, Any]:
        """Generate comprehensive cost analysis report."""
        print(f"📈 Generating cost report for {project_name}-{environment}")
        print("=" * 60)

        analysis_results = {
            "project_name": project_name,
            "environment": environment,
            "region": self.region,
            "timestamp": datetime.now().isoformat(),
            "monthly_costs": self.get_monthly_costs(),
            "log_analysis": self.analyze_log_usage(project_name, environment),
            "dynamodb_analysis": self.analyze_dynamodb_usage(project_name, environment),
            "backup_analysis": self.analyze_backup_costs(project_name, environment),
        }

        # Generate recommendations
        analysis_results["recommendations"] = self.get_optimization_recommendations(analysis_results)

        # Calculate total estimated monthly cost for new resources
        total_new_cost = 0
        total_new_cost += analysis_results["log_analysis"].get("estimated_monthly_cost", 0)
        total_new_cost += analysis_results["dynamodb_analysis"].get("total_monthly_cost", 0)
        total_new_cost += analysis_results["backup_analysis"].get("total_monthly_cost", 0)
        total_new_cost += 2.30  # KMS keys
        total_new_cost += 28  # Kinesis stream (estimated)
        total_new_cost += 1  # SNS topic (estimated)

        analysis_results["estimated_new_resources_cost"] = round(total_new_cost, 2)

        return analysis_results

    def print_cost_summary(self, analysis_results: Dict):
        """Print a formatted cost summary."""
        print("\n💰 COST ANALYSIS SUMMARY")
        print("=" * 50)

        # New resources cost
        new_cost = analysis_results.get("estimated_new_resources_cost", 0)
        print(f"📊 Estimated Monthly Cost for New Resources: ${new_cost}")

        # Breakdown
        print("\n📋 Cost Breakdown:")
        log_cost = analysis_results["log_analysis"].get("estimated_monthly_cost", 0)
        dynamodb_cost = analysis_results["dynamodb_analysis"].get("total_monthly_cost", 0)
        backup_cost = analysis_results["backup_analysis"].get("total_monthly_cost", 0)

        print(f"  • CloudWatch Logs: ${log_cost}")
        print(f"  • DynamoDB (storage + PITR): ${dynamodb_cost}")
        print(f"  • AWS Backup: ${backup_cost}")
        print(f"  • KMS Keys: $2.30")
        print(f"  • Kinesis Stream: ~$28")
        print(f"  • SNS Topic: ~$1")
        print(f"  • CloudWatch Alarms/Dashboard: ~$4")

        # Student Budget Analysis
        self.print_student_budget_analysis(new_cost)

        # Recommendations
        print("\n🎯 TOP RECOMMENDATIONS:")
        recommendations = analysis_results.get("recommendations", [])
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"  {i}. {rec['recommendation']} ({rec['category']})")
            print(f"     💰 Potential savings: {rec['potential_savings']}")
            print(f"     🔧 Action: {rec['action']}")
            if "alternative" in rec:
                print(f"     🔄 Alternative: {rec['alternative']}")
            print()

    def print_student_budget_analysis(self, current_cost: float):
        """Print student budget optimization analysis."""
        print("\n🎓 STUDENT BUDGET ANALYSIS (Target: 15-20 EUR/month)")
        print("=" * 60)

        # Calculate potential savings
        kinesis_savings = 28
        backup_savings = 35  # Average of 20-50
        log_savings = 12  # Average of 10-15
        kms_savings = 2
        alarm_savings = 4  # Average of 3-5

        total_savings = kinesis_savings + backup_savings + log_savings + kms_savings + alarm_savings
        optimized_cost = current_cost - total_savings

        print(f"📊 Current estimated cost: ${current_cost}/month")
        print(f"💰 Total potential savings: ${total_savings}/month")
        print(f"🎯 Optimized cost: ${optimized_cost}/month")

        if optimized_cost <= 20:
            print("✅ TARGET ACHIEVED: Cost within student budget!")
        else:
            print("⚠️  Additional optimizations needed")

        print("\n📋 Student Budget Optimizations:")
        optimizations = [
            ("Remove Kinesis stream", kinesis_savings, "enable_kinesis_stream = false"),
            ("Disable AWS Backup", backup_savings, "enable_aws_backup = false"),
            ("Reduce log retention to 7 days", log_savings, "log_retention_days = 7"),
            ("Use AWS managed KMS keys", kms_savings, "enable_custom_kms_keys = false"),
            ("Minimal CloudWatch alarms", alarm_savings, "minimal_cloudwatch_alarms = true"),
        ]

        for opt_name, savings, config in optimizations:
            print(f"  • {opt_name}: -${savings}/month")
            print(f"    Config: {config}")

        print(f"\n🚀 DEPLOYMENT COMMAND:")
        print(f"   cp terraform/terraform.tfvars.student-budget terraform/terraform.tfvars")
        print(f"   cd terraform && terraform apply")


def main():
    """Main function to run cost analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze AWS costs for shared resources")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument("--project", default="provider-comparison", help="Project name")
    parser.add_argument("--environment", default="dev", help="Environment name")
    parser.add_argument("--output", help="Output file for analysis results (JSON)")
    parser.add_argument("--format", choices=["json", "summary"], default="summary", help="Output format")
    parser.add_argument("--student-budget", action="store_true", help="Show student budget optimization summary")

    args = parser.parse_args()

    if args.student_budget:
        print("🎓 STUDENT BUDGET OPTIMIZATION GUIDE")
        print("=" * 50)
        print("Target: 15-20 EUR/month total AWS costs")
        print()
        print("📋 Required Optimizations:")
        print("1. Remove Kinesis stream: -$28/month")
        print("2. Disable AWS Backup: -$35/month")
        print("3. Reduce log retention to 7 days: -$12/month")
        print("4. Use AWS managed KMS keys: -$2/month")
        print("5. Minimal CloudWatch alarms: -$4/month")
        print()
        print("💰 Total savings: ~$81/month")
        print("🎯 Expected final cost: ~$15-20/month")
        print()
        print("🚀 IMPLEMENTATION:")
        print("1. Copy student budget config:")
        print("   cp terraform/terraform.tfvars.student-budget terraform/terraform.tfvars")
        print()
        print("2. Apply changes:")
        print("   cd terraform")
        print("   terraform plan")
        print("   terraform apply")
        print()
        print("3. Monitor costs:")
        print("   python3 scripts/cost-optimization.py --format summary")
        return

    optimizer = CostOptimizer(region=args.region)
    results = optimizer.generate_cost_report(args.project, args.environment)

    if args.format == "summary":
        optimizer.print_cost_summary(results)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"📄 Analysis results saved to {args.output}")

    if args.format == "json":
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
