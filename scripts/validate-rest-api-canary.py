#!/usr/bin/env python3
"""
Script to validate REST API Gateway canary deployment functionality.
This script tests the canary deployment setup and traffic distribution.
"""

import argparse
import boto3
import requests
import json
import time
import statistics
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError, BotoCoreError


class RestApiCanaryValidator:
    """Validates REST API Gateway canary deployment functionality."""

    def __init__(self, region: str = "eu-central-1"):
        """Initialize the validator."""
        self.region = region
        self.apigateway = boto3.client("apigateway", region_name=region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)

    def get_api_endpoints(self, api_name: str) -> Dict[str, str]:
        """Get API Gateway endpoints for different stages."""
        try:
            response = self.apigateway.get_rest_apis()
            api_id = None

            for api in response["items"]:
                if api["name"] == api_name:
                    api_id = api["id"]
                    break

            if not api_id:
                raise ValueError(f"API '{api_name}' not found")

            endpoints = {
                "staging": f"https://{api_id}.execute-api.{self.region}.amazonaws.com/staging",
                "prod": f"https://{api_id}.execute-api.{self.region}.amazonaws.com/prod",
            }

            return endpoints

        except (ClientError, BotoCoreError) as e:
            print(f"Error getting API endpoints: {e}")
            return {}

    def test_endpoint_availability(self, endpoint: str, path: str = "/share/test-token") -> Dict[str, Any]:
        """Test if an endpoint is available and responsive."""
        full_url = f"{endpoint}{path}"

        try:
            start_time = time.time()
            response = requests.get(full_url, timeout=10)
            end_time = time.time()

            return {
                "url": full_url,
                "status_code": response.status_code,
                "response_time": (end_time - start_time) * 1000,  # in milliseconds
                "success": response.status_code in [200, 404],  # 404 is expected for test token
                "headers": dict(response.headers),
                "error": None,
            }

        except requests.RequestException as e:
            return {
                "url": full_url,
                "status_code": None,
                "response_time": None,
                "success": False,
                "headers": {},
                "error": str(e),
            }

    def load_test_endpoint(self, endpoint: str, num_requests: int = 100, concurrency: int = 10) -> Dict[str, Any]:
        """Perform load testing on an endpoint."""
        print(f"🔄 Load testing {endpoint} with {num_requests} requests (concurrency: {concurrency})")

        results = []

        def make_request():
            return self.test_endpoint_availability(endpoint)

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({"success": False, "error": str(e), "response_time": None})

        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        response_times = [r["response_time"] for r in successful_requests if r["response_time"]]

        analysis = {
            "total_requests": num_requests,
            "successful_requests": len(successful_requests),
            "failed_requests": len(failed_requests),
            "success_rate": len(successful_requests) / num_requests * 100,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "p95_response_time": statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0,
            "errors": [r["error"] for r in failed_requests if r["error"]],
        }

        return analysis

    def validate_cors_configuration(self, endpoint: str) -> Dict[str, Any]:
        """Validate CORS configuration for the API."""
        print(f"🔄 Validating CORS configuration for {endpoint}")

        try:
            # Test OPTIONS request
            response = requests.options(f"{endpoint}/share/test", timeout=10)

            cors_headers = {
                "access_control_allow_origin": response.headers.get("Access-Control-Allow-Origin"),
                "access_control_allow_methods": response.headers.get("Access-Control-Allow-Methods"),
                "access_control_allow_headers": response.headers.get("Access-Control-Allow-Headers"),
                "access_control_max_age": response.headers.get("Access-Control-Max-Age"),
            }

            # Validate CORS headers
            cors_valid = all(
                [
                    cors_headers["access_control_allow_origin"] == "*",
                    "GET" in (cors_headers["access_control_allow_methods"] or ""),
                    "OPTIONS" in (cors_headers["access_control_allow_methods"] or ""),
                ]
            )

            return {
                "status_code": response.status_code,
                "cors_headers": cors_headers,
                "cors_valid": cors_valid,
                "success": response.status_code == 200 and cors_valid,
            }

        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def validate_canary_deployment(self, api_name: str, stage_name: str = "prod") -> Dict[str, Any]:
        """Validate canary deployment configuration."""
        print(f"🔄 Validating canary deployment for {api_name}/{stage_name}")

        try:
            # Get API info
            response = self.apigateway.get_rest_apis()
            api_id = None

            for api in response["items"]:
                if api["name"] == api_name:
                    api_id = api["id"]
                    break

            if not api_id:
                return {"success": False, "error": f"API '{api_name}' not found"}

            # Get stage info
            stage_response = self.apigateway.get_stage(restApiId=api_id, stageName=stage_name)

            canary_settings = stage_response.get("canarySettings", {})

            validation_result = {
                "api_id": api_id,
                "stage_name": stage_name,
                "canary_enabled": bool(canary_settings),
                "percent_traffic": int(canary_settings.get("percentTraffic", 0)),
                "deployment_id": canary_settings.get("deploymentId"),
                "stage_variables": canary_settings.get("stageVariableOverrides", {}),
                "use_stage_cache": canary_settings.get("useStageCache", False),
                "success": True,
            }

            return validation_result

        except (ClientError, BotoCoreError) as e:
            return {"success": False, "error": str(e)}

    def validate_monitoring_setup(self, api_name: str) -> Dict[str, Any]:
        """Validate CloudWatch monitoring and alarms setup."""
        print(f"🔄 Validating monitoring setup for {api_name}")

        try:
            # Check for CloudWatch alarms
            response = self.cloudwatch.describe_alarms(AlarmNamePrefix=f"provider-comparison-dev-{api_name.replace('-', '-')}")

            alarms = response["MetricAlarms"]
            alarm_names = [alarm["AlarmName"] for alarm in alarms]

            expected_alarms = [
                "rest-api-high-error-rate",
                "rest-api-high-latency",
                "share-api-new-errors",
                "share-api-old-errors",
                "canary-rollback-trigger",
            ]

            missing_alarms = []
            for expected in expected_alarms:
                if not any(expected in name for name in alarm_names):
                    missing_alarms.append(expected)

            # Check for CloudWatch dashboard
            try:
                dashboard_response = self.cloudwatch.get_dashboard(DashboardName=f"provider-comparison-dev-rest-api-canary")
                dashboard_exists = True
            except ClientError:
                dashboard_exists = False

            return {
                "alarms_found": len(alarms),
                "alarm_names": alarm_names,
                "missing_alarms": missing_alarms,
                "dashboard_exists": dashboard_exists,
                "success": len(missing_alarms) == 0 and dashboard_exists,
            }

        except (ClientError, BotoCoreError) as e:
            return {"success": False, "error": str(e)}

    def run_comprehensive_validation(self, api_name: str) -> Dict[str, Any]:
        """Run comprehensive validation of the REST API canary deployment."""
        print(f"🚀 Starting comprehensive validation for {api_name}")
        print("=" * 60)

        results = {}

        # 1. Get API endpoints
        print("\n1️⃣ Getting API endpoints...")
        endpoints = self.get_api_endpoints(api_name)
        results["endpoints"] = endpoints

        if not endpoints:
            print("❌ Failed to get API endpoints")
            return {"success": False, "results": results}

        print(f"✅ Found endpoints: {list(endpoints.keys())}")

        # 2. Test endpoint availability
        print("\n2️⃣ Testing endpoint availability...")
        availability_results = {}

        for stage, endpoint in endpoints.items():
            print(f"Testing {stage}: {endpoint}")
            test_result = self.test_endpoint_availability(endpoint)
            availability_results[stage] = test_result

            if test_result["success"]:
                print(f"✅ {stage} endpoint is available (response time: {test_result['response_time']:.2f}ms)")
            else:
                print(f"❌ {stage} endpoint failed: {test_result.get('error', 'Unknown error')}")

        results["availability"] = availability_results

        # 3. Validate CORS configuration
        print("\n3️⃣ Validating CORS configuration...")
        cors_results = {}

        for stage, endpoint in endpoints.items():
            cors_result = self.validate_cors_configuration(endpoint)
            cors_results[stage] = cors_result

            if cors_result["success"]:
                print(f"✅ {stage} CORS configuration is valid")
            else:
                print(f"❌ {stage} CORS configuration failed")

        results["cors"] = cors_results

        # 4. Validate canary deployment
        print("\n4️⃣ Validating canary deployment...")
        canary_result = self.validate_canary_deployment(api_name)
        results["canary"] = canary_result

        if canary_result["success"]:
            if canary_result["canary_enabled"]:
                print(f"✅ Canary deployment is enabled ({canary_result['percent_traffic']}% traffic)")
            else:
                print("ℹ️ Canary deployment is not currently active")
        else:
            print(f"❌ Canary deployment validation failed: {canary_result.get('error')}")

        # 5. Validate monitoring setup
        print("\n5️⃣ Validating monitoring setup...")
        monitoring_result = self.validate_monitoring_setup(api_name)
        results["monitoring"] = monitoring_result

        if monitoring_result["success"]:
            print(f"✅ Monitoring setup is complete ({monitoring_result['alarms_found']} alarms found)")
        else:
            print(f"❌ Monitoring setup incomplete: {monitoring_result.get('missing_alarms', [])}")

        # 6. Load testing (optional)
        if endpoints.get("prod"):
            print("\n6️⃣ Running load test on production endpoint...")
            load_test_result = self.load_test_endpoint(endpoints["prod"], num_requests=50, concurrency=5)
            results["load_test"] = load_test_result

            print(f"✅ Load test completed:")
            print(f"   Success rate: {load_test_result['success_rate']:.1f}%")
            print(f"   Average response time: {load_test_result['avg_response_time']:.2f}ms")
            print(f"   P95 response time: {load_test_result['p95_response_time']:.2f}ms")

        # Overall success
        overall_success = all(
            [
                bool(endpoints),
                all(r["success"] for r in availability_results.values()),
                all(r["success"] for r in cors_results.values()),
                canary_result["success"],
                monitoring_result["success"],
            ]
        )

        results["overall_success"] = overall_success

        print(f"\n{'='*60}")
        if overall_success:
            print("🎉 All validations passed! REST API canary deployment is ready.")
        else:
            print("❌ Some validations failed. Please check the results above.")

        return {"success": overall_success, "results": results}


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Validate REST API Gateway canary deployment")
    parser.add_argument("--api-name", required=True, help="API Gateway name")
    parser.add_argument("--region", default="eu-central-1", help="AWS region (default: eu-central-1)")
    parser.add_argument("--output", help="Output file for results (JSON format)")

    args = parser.parse_args()

    validator = RestApiCanaryValidator(args.region)
    results = validator.run_comprehensive_validation(args.api_name)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📄 Results saved to {args.output}")

    exit_code = 0 if results["success"] else 1
    exit(exit_code)


if __name__ == "__main__":
    main()
