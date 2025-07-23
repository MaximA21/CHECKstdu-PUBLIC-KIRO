#!/usr/bin/env python3
"""
GitHub OIDC Setup Validation Script

This script validates that the GitHub OIDC configuration is properly set up
and can be used by GitHub Actions to authenticate with AWS.
"""

import boto3
import json
import sys
import argparse
from botocore.exceptions import ClientError, NoCredentialsError


def validate_oidc_provider(iam_client, provider_arn):
    """Validate that the OIDC provider exists and is configured correctly."""
    try:
        response = iam_client.get_open_id_connect_provider(OpenIDConnectProviderArn=provider_arn)

        provider = response
        print("✅ OIDC Provider found")
        print(f"   URL: {provider['Url']}")
        print(f"   Client IDs: {', '.join(provider['ClientIDList'])}")
        print(f"   Thumbprints: {len(provider['ThumbprintList'])} configured")

        # Validate expected configuration
        if provider["Url"] != "https://token.actions.githubusercontent.com":
            print("❌ OIDC Provider URL is incorrect")
            return False

        if "sts.amazonaws.com" not in provider["ClientIDList"]:
            print("❌ OIDC Provider missing required client ID")
            return False

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print("❌ OIDC Provider not found")
        else:
            print(f"❌ Error checking OIDC Provider: {e}")
        return False


def validate_iam_role(iam_client, role_arn, expected_repo):
    """Validate that the IAM role exists and has correct trust policy."""
    try:
        role_name = role_arn.split("/")[-1]
        response = iam_client.get_role(RoleName=role_name)

        role = response["Role"]
        print("✅ IAM Role found")
        print(f"   Role Name: {role['RoleName']}")
        print(f"   Role ARN: {role['Arn']}")

        # Parse and validate trust policy
        trust_policy = role["AssumeRolePolicyDocument"]

        # Check for OIDC trust relationship
        has_oidc_trust = False
        has_correct_repo = False

        for statement in trust_policy.get("Statement", []):
            if statement.get("Action") == "sts:AssumeRoleWithWebIdentity":
                has_oidc_trust = True

                # Check conditions
                conditions = statement.get("Condition", {})
                string_like = conditions.get("StringLike", {})
                sub_condition = string_like.get("token.actions.githubusercontent.com:sub", "")

                if expected_repo in sub_condition:
                    has_correct_repo = True
                    print(f"✅ Trust policy allows repository: {expected_repo}")
                    break

        if not has_oidc_trust:
            print("❌ IAM Role missing OIDC trust relationship")
            return False

        if not has_correct_repo:
            print(f"❌ IAM Role trust policy doesn't allow repository: {expected_repo}")
            return False

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print("❌ IAM Role not found")
        else:
            print(f"❌ Error checking IAM Role: {e}")
        return False


def validate_role_policies(iam_client, role_arn):
    """Validate that the IAM role has necessary policies attached."""
    try:
        role_name = role_arn.split("/")[-1]

        # Get attached managed policies
        managed_policies = iam_client.list_attached_role_policies(RoleName=role_name)

        # Get inline policies
        inline_policies = iam_client.list_role_policies(RoleName=role_name)

        print("✅ Role Policies:")
        print(f"   Managed Policies: {len(managed_policies['AttachedPolicies'])}")
        for policy in managed_policies["AttachedPolicies"]:
            print(f"     - {policy['PolicyName']}")

        print(f"   Inline Policies: {len(inline_policies['PolicyNames'])}")
        for policy_name in inline_policies["PolicyNames"]:
            print(f"     - {policy_name}")

        # Check for required policies
        required_policies = [
            "github-actions-lambda-deployment",
            "github-actions-api-gateway-deployment",
            "github-actions-s3-artifacts",
        ]

        attached_policy_names = [p["PolicyName"] for p in managed_policies["AttachedPolicies"]]
        attached_policy_names.extend(inline_policies["PolicyNames"])

        missing_policies = []
        for required in required_policies:
            if not any(required in name for name in attached_policy_names):
                missing_policies.append(required)

        if missing_policies:
            print(f"⚠️  Potentially missing policies: {', '.join(missing_policies)}")
        else:
            print("✅ All expected policies are attached")

        return True

    except ClientError as e:
        print(f"❌ Error checking role policies: {e}")
        return False


def validate_s3_bucket(s3_client, bucket_name):
    """Validate that the deployment artifacts S3 bucket exists and is accessible."""
    try:
        # Check if bucket exists and is accessible
        s3_client.head_bucket(Bucket=bucket_name)
        print("✅ S3 Deployment Bucket accessible")
        print(f"   Bucket Name: {bucket_name}")

        # Check bucket encryption
        try:
            encryption = s3_client.get_bucket_encryption(Bucket=bucket_name)
            print("✅ Bucket encryption enabled")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                print("⚠️  Bucket encryption not configured")
            else:
                print(f"⚠️  Could not check bucket encryption: {e}")

        # Check bucket versioning
        try:
            versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
            if versioning.get("Status") == "Enabled":
                print("✅ Bucket versioning enabled")
            else:
                print("⚠️  Bucket versioning not enabled")
        except ClientError as e:
            print(f"⚠️  Could not check bucket versioning: {e}")

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchBucket":
            print("❌ S3 Deployment Bucket not found")
        elif e.response["Error"]["Code"] == "Forbidden":
            print("❌ Access denied to S3 Deployment Bucket")
        else:
            print(f"❌ Error checking S3 bucket: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate GitHub OIDC setup for AWS deployment")
    parser.add_argument("--role-arn", required=True, help="ARN of the GitHub Actions IAM role")
    parser.add_argument("--oidc-provider-arn", required=True, help="ARN of the OIDC provider")
    parser.add_argument("--bucket-name", required=True, help="Name of the deployment artifacts S3 bucket")
    parser.add_argument("--repository", required=True, help="GitHub repository in format owner/repo")
    parser.add_argument("--region", default="eu-central-1", help="AWS region")

    args = parser.parse_args()

    print("🔍 Validating GitHub OIDC Setup for AWS Deployment")
    print("=" * 60)

    try:
        # Initialize AWS clients
        session = boto3.Session(region_name=args.region)
        iam_client = session.client("iam")
        s3_client = session.client("s3")

        print(f"AWS Region: {args.region}")
        print(f"Repository: {args.repository}")
        print()

        # Run validations
        validations = [
            ("OIDC Provider", lambda: validate_oidc_provider(iam_client, args.oidc_provider_arn)),
            ("IAM Role", lambda: validate_iam_role(iam_client, args.role_arn, args.repository)),
            ("Role Policies", lambda: validate_role_policies(iam_client, args.role_arn)),
            ("S3 Bucket", lambda: validate_s3_bucket(s3_client, args.bucket_name)),
        ]

        results = []
        for name, validation_func in validations:
            print(f"\n📋 Validating {name}...")
            try:
                result = validation_func()
                results.append((name, result))
            except Exception as e:
                print(f"❌ Unexpected error validating {name}: {e}")
                results.append((name, False))

        # Summary
        print("\n" + "=" * 60)
        print("📊 Validation Summary")
        print("=" * 60)

        passed = 0
        total = len(results)

        for name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{name:20} {status}")
            if result:
                passed += 1

        print(f"\nOverall: {passed}/{total} validations passed")

        if passed == total:
            print("\n🎉 All validations passed! GitHub OIDC setup is ready for use.")
            print("\nNext steps:")
            print("1. Set AWS_GITHUB_ACTIONS_ROLE_ARN repository variable in GitHub")
            print("2. Set AWS_REGION repository variable in GitHub")
            print("3. Test deployment from kiro-rewrite branch")
            return 0
        else:
            print(f"\n⚠️  {total - passed} validation(s) failed. Please fix the issues above.")
            print("\nRefer to docs/GITHUB_OIDC_SETUP.md for troubleshooting guidance.")
            return 1

    except NoCredentialsError:
        print("❌ AWS credentials not configured. Please configure AWS CLI or set environment variables.")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
