#!/usr/bin/env python3
"""
Security Controls Validation Script

This script validates that basic security controls are properly configured
according to task 6.2 requirements.
"""

import json
import boto3
import sys
import argparse
from typing import Dict, List, Any
from botocore.exceptions import ClientError, NoCredentialsError


class SecurityValidator:
    """Validates security controls implementation"""

    def __init__(self, region: str = "eu-central-1", environment: str = "staging"):
        self.region = region
        self.environment = environment
        self.project_name = "webwunder"  # Default project name

        try:
            # Initialize AWS clients
            self.cloudtrail_client = boto3.client("cloudtrail", region_name=region)
            self.iam_client = boto3.client("iam", region_name=region)
            self.lambda_client = boto3.client("lambda", region_name=region)
            self.s3_client = boto3.client("s3", region_name=region)
            self.kms_client = boto3.client("kms", region_name=region)

        except NoCredentialsError:
            print("❌ AWS credentials not configured")
            sys.exit(1)

    def validate_cloudtrail(self) -> Dict[str, Any]:
        """Validate CloudTrail basic configuration"""
        print("🔍 Validating CloudTrail configuration...")

        results = {
            "status": "unknown",
            "trail_name": None,
            "logging_enabled": False,
            "s3_bucket": None,
            "multi_region": False,
            "management_events": False,
            "details": [],
        }

        try:
            # List trails
            trails = self.cloudtrail_client.describe_trails()

            trail_name = f"{self.project_name}-{self.environment}-basic-trail"
            trail_found = False

            for trail in trails["trailList"]:
                if trail["Name"] == trail_name:
                    trail_found = True
                    results["trail_name"] = trail["Name"]
                    results["s3_bucket"] = trail["S3BucketName"]
                    results["multi_region"] = trail.get("IsMultiRegionTrail", False)

                    # Check if logging is enabled
                    status = self.cloudtrail_client.get_trail_status(Name=trail["Name"])
                    results["logging_enabled"] = status["IsLogging"]

                    # Check event selectors
                    try:
                        selectors = self.cloudtrail_client.get_event_selectors(TrailName=trail["Name"])
                        for selector in selectors["EventSelectors"]:
                            if selector["IncludeManagementEvents"]:
                                results["management_events"] = True
                    except ClientError:
                        results["details"].append("Could not retrieve event selectors")

                    break

            if trail_found:
                if results["logging_enabled"] and results["management_events"]:
                    results["status"] = "compliant"
                    results["details"].append("✅ CloudTrail properly configured for basic audit logging")
                else:
                    results["status"] = "non_compliant"
                    results["details"].append("⚠️ CloudTrail found but not properly configured")
            else:
                results["status"] = "non_compliant"
                results["details"].append(f"❌ CloudTrail '{trail_name}' not found")

        except ClientError as e:
            results["status"] = "error"
            results["details"].append(f"❌ Error checking CloudTrail: {str(e)}")

        return results

    def validate_kms_usage(self) -> Dict[str, Any]:
        """Validate that AWS managed keys are used instead of custom KMS keys"""
        print("🔍 Validating KMS key usage (should use AWS managed keys)...")

        results = {"status": "unknown", "custom_keys_found": [], "aws_managed_usage": True, "details": []}

        try:
            # List customer managed keys
            keys = self.kms_client.list_keys()
            custom_keys = []

            for key in keys["Keys"]:
                key_id = key["KeyId"]
                try:
                    key_info = self.kms_client.describe_key(KeyId=key_id)
                    key_metadata = key_info["KeyMetadata"]

                    # Check if it's a customer managed key for our project
                    if (
                        key_metadata["KeyManager"] == "CUSTOMER"
                        and key_metadata.get("Description", "").find(self.project_name) != -1
                    ):
                        custom_keys.append(
                            {
                                "key_id": key_id,
                                "description": key_metadata.get("Description", ""),
                                "creation_date": key_metadata["CreationDate"].isoformat(),
                            }
                        )

                except ClientError:
                    continue  # Skip keys we can't access

            results["custom_keys_found"] = custom_keys

            if len(custom_keys) == 0:
                results["status"] = "compliant"
                results["details"].append("✅ No custom KMS keys found - using AWS managed keys for cost optimization")
            else:
                results["status"] = "warning"
                results["aws_managed_usage"] = False
                results["details"].append(
                    f"⚠️ Found {len(custom_keys)} custom KMS keys - consider using AWS managed keys for cost savings"
                )

        except ClientError as e:
            results["status"] = "error"
            results["details"].append(f"❌ Error checking KMS keys: {str(e)}")

        return results

    def validate_lambda_iam_policies(self) -> Dict[str, Any]:
        """Validate Lambda IAM policies follow least privilege"""
        print("🔍 Validating Lambda IAM policies...")

        results = {
            "status": "unknown",
            "functions_checked": 0,
            "compliant_functions": 0,
            "policy_violations": [],
            "details": [],
        }

        try:
            # List Lambda functions for our project
            functions = self.lambda_client.list_functions()
            project_functions = [
                f for f in functions["Functions"] if f["FunctionName"].startswith(f"{self.project_name}-{self.environment}")
            ]

            results["functions_checked"] = len(project_functions)

            for function in project_functions:
                function_name = function["FunctionName"]

                try:
                    # Get function configuration
                    config = self.lambda_client.get_function(FunctionName=function_name)
                    role_arn = config["Configuration"]["Role"]

                    # Extract role name from ARN
                    role_name = role_arn.split("/")[-1]

                    # Get role policies
                    try:
                        attached_policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
                        inline_policies = self.iam_client.list_role_policies(RoleName=role_name)

                        # Check for overly permissive policies
                        violations = []

                        # Check attached policies
                        for policy in attached_policies["AttachedPolicies"]:
                            policy_name = policy["PolicyName"]

                            # Flag potentially overly permissive policies
                            if any(perm in policy_name.lower() for perm in ["admin", "full", "power"]):
                                violations.append(f"Potentially overly permissive policy: {policy_name}")

                        # Check inline policies (should be minimal)
                        if len(inline_policies["PolicyNames"]) > 3:
                            violations.append(f"Too many inline policies ({len(inline_policies['PolicyNames'])})")

                        if len(violations) == 0:
                            results["compliant_functions"] += 1
                        else:
                            results["policy_violations"].extend([f"{function_name}: {violation}" for violation in violations])

                    except ClientError as e:
                        results["details"].append(f"Could not check policies for {function_name}: {str(e)}")

                except ClientError as e:
                    results["details"].append(f"Could not get configuration for {function_name}: {str(e)}")

            # Determine overall status
            if results["functions_checked"] == 0:
                results["status"] = "warning"
                results["details"].append("⚠️ No Lambda functions found for validation")
            elif results["compliant_functions"] == results["functions_checked"]:
                results["status"] = "compliant"
                results["details"].append(
                    f"✅ All {results['functions_checked']} Lambda functions have appropriate IAM policies"
                )
            else:
                results["status"] = "non_compliant"
                results["details"].append(
                    f"❌ {results['functions_checked'] - results['compliant_functions']} functions have policy violations"
                )

        except ClientError as e:
            results["status"] = "error"
            results["details"].append(f"❌ Error checking Lambda functions: {str(e)}")

        return results

    def validate_s3_security(self) -> Dict[str, Any]:
        """Validate S3 bucket security for CloudTrail"""
        print("🔍 Validating S3 bucket security...")

        results = {
            "status": "unknown",
            "bucket_name": None,
            "public_access_blocked": False,
            "encryption_enabled": False,
            "lifecycle_configured": False,
            "details": [],
        }

        try:
            # Find CloudTrail S3 bucket
            bucket_prefix = f"{self.project_name}-{self.environment}-cloudtrail-logs"
            buckets = self.s3_client.list_buckets()

            cloudtrail_bucket = None
            for bucket in buckets["Buckets"]:
                if bucket["Name"].startswith(bucket_prefix):
                    cloudtrail_bucket = bucket["Name"]
                    break

            if not cloudtrail_bucket:
                results["status"] = "non_compliant"
                results["details"].append(f"❌ CloudTrail S3 bucket not found (prefix: {bucket_prefix})")
                return results

            results["bucket_name"] = cloudtrail_bucket

            # Check public access block
            try:
                pab = self.s3_client.get_public_access_block(Bucket=cloudtrail_bucket)
                config = pab["PublicAccessBlockConfiguration"]

                if (
                    config["BlockPublicAcls"]
                    and config["BlockPublicPolicy"]
                    and config["IgnorePublicAcls"]
                    and config["RestrictPublicBuckets"]
                ):
                    results["public_access_blocked"] = True

            except ClientError:
                results["details"].append("⚠️ Could not check public access block configuration")

            # Check encryption
            try:
                encryption = self.s3_client.get_bucket_encryption(Bucket=cloudtrail_bucket)
                if encryption["ServerSideEncryptionConfiguration"]["Rules"]:
                    results["encryption_enabled"] = True
            except ClientError:
                results["details"].append("⚠️ Could not check bucket encryption")

            # Check lifecycle configuration
            try:
                lifecycle = self.s3_client.get_bucket_lifecycle_configuration(Bucket=cloudtrail_bucket)
                if lifecycle["Rules"]:
                    results["lifecycle_configured"] = True
            except ClientError:
                results["details"].append("⚠️ Could not check lifecycle configuration")

            # Determine overall status
            if results["public_access_blocked"] and results["encryption_enabled"] and results["lifecycle_configured"]:
                results["status"] = "compliant"
                results["details"].append("✅ S3 bucket properly secured")
            else:
                results["status"] = "non_compliant"
                results["details"].append("❌ S3 bucket security configuration incomplete")

        except ClientError as e:
            results["status"] = "error"
            results["details"].append(f"❌ Error checking S3 security: {str(e)}")

        return results

    def run_validation(self) -> Dict[str, Any]:
        """Run all security validations"""
        print(f"🔒 Running security controls validation for {self.project_name}-{self.environment}")
        print(f"📍 Region: {self.region}")
        print("=" * 60)

        results = {
            "timestamp": boto3.Session().region_name,
            "environment": self.environment,
            "region": self.region,
            "validations": {},
        }

        # Run all validations
        validations = [
            ("cloudtrail", self.validate_cloudtrail),
            ("kms_usage", self.validate_kms_usage),
            ("lambda_iam", self.validate_lambda_iam_policies),
            ("s3_security", self.validate_s3_security),
        ]

        overall_status = "compliant"

        for validation_name, validation_func in validations:
            try:
                result = validation_func()
                results["validations"][validation_name] = result

                # Update overall status
                if result["status"] == "error" or result["status"] == "non_compliant":
                    overall_status = "non_compliant"
                elif result["status"] == "warning" and overall_status == "compliant":
                    overall_status = "warning"

            except Exception as e:
                results["validations"][validation_name] = {"status": "error", "details": [f"Validation failed: {str(e)}"]}
                overall_status = "non_compliant"

        results["overall_status"] = overall_status

        # Print summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)

        for name, result in results["validations"].items():
            status_emoji = {"compliant": "✅", "warning": "⚠️", "non_compliant": "❌", "error": "💥", "unknown": "❓"}.get(
                result["status"], "❓"
            )

            print(f"{status_emoji} {name.upper()}: {result['status'].upper()}")
            for detail in result.get("details", []):
                print(f"   {detail}")

        print(f"\n🎯 OVERALL STATUS: {overall_status.upper()}")

        if overall_status == "compliant":
            print("🎉 All security controls are properly configured!")
        elif overall_status == "warning":
            print("⚠️ Security controls are mostly configured with some warnings")
        else:
            print("❌ Security controls need attention")

        return results


def main():
    parser = argparse.ArgumentParser(description="Validate security controls implementation")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument("--environment", default="staging", help="Environment (staging/production)")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--project", default="webwunder", help="Project name")

    args = parser.parse_args()

    validator = SecurityValidator(region=args.region, environment=args.environment)
    validator.project_name = args.project

    results = validator.run_validation()

    # Save results if output file specified
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📄 Results saved to {args.output}")

    # Exit with appropriate code
    if results["overall_status"] in ["error", "non_compliant"]:
        sys.exit(1)
    elif results["overall_status"] == "warning":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
