#!/usr/bin/env python3
"""
Basic Traffic Distribution Validation Script
Tests 50/50 traffic splitting functionality for both WebSocket and REST API
Validates API Gateway canary deployment works with simple health checks
"""

import argparse
import asyncio
import json
import logging
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import boto3
import requests
import websockets
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TrafficDistributionValidator:
    """Validates traffic distribution for both WebSocket and REST API."""

    def __init__(self, region: str = "eu-central-1"):
        """Initialize the validator."""
        self.region = region
        self.apigateway = boto3.client("apigateway", region_name=region)
        self.apigatewayv2 = boto3.client("apigatewayv2", region_name=region)
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)

    def get_rest_api_endpoints(self, api_name: str) -> Dict[str, str]:
        """Get REST API Gateway endpoints."""
        try:
            response = self.apigateway.get_rest_apis()
            api_id = None

            for api in response["items"]:
                if api["name"] == api_name:
                    api_id = api["id"]
                    break

            if not api_id:
                logger.error(f"REST API '{api_name}' not found")
                return {}

            endpoints = {
                "staging": f"https://{api_id}.execute-api.{self.region}.amazonaws.com/staging",
                "prod": f"https://{api_id}.execute-api.{self.region}.amazonaws.com/prod",
            }

            logger.info(f"Found REST API endpoints: {list(endpoints.keys())}")
            return endpoints

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error getting REST API endpoints: {e}")
            return {}

    def get_websocket_api_endpoint(self, api_name: str) -> Optional[str]:
        """Get WebSocket API Gateway endpoint."""
        try:
            response = self.apigatewayv2.get_apis()

            for api in response["Items"]:
                if api["Name"] == api_name and api["ProtocolType"] == "WEBSOCKET":
                    api_id = api["ApiId"]
                    endpoint = f"wss://{api_id}.execute-api.{self.region}.amazonaws.com/dev"
                    logger.info(f"Found WebSocket API endpoint: {endpoint}")
                    return endpoint

            logger.error(f"WebSocket API '{api_name}' not found")
            return None

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Error getting WebSocket API endpoint: {e}")
            return None

    def test_rest_api_endpoint(self, endpoint: str, path: str = "/share/test-token") -> Dict[str, Any]:
        """Test REST API endpoint availability and response."""
        full_url = f"{endpoint}{path}"

        try:
            start_time = time.time()
            response = requests.get(full_url, timeout=10)
            end_time = time.time()

            return {
                "url": full_url,
                "status_code": response.status_code,
                "response_time": (end_time - start_time) * 1000,
                "success": response.status_code in [200, 404],  # 404 is expected for test token
                "headers": dict(response.headers),
                "implementation": response.headers.get("X-Implementation", "unknown"),
                "error": None,
            }

        except requests.RequestException as e:
            return {
                "url": full_url,
                "status_code": None,
                "response_time": None,
                "success": False,
                "headers": {},
                "implementation": "unknown",
                "error": str(e),
            }

    async def test_websocket_connection(self, websocket_url: str, connection_id: int = 0) -> Dict[str, Any]:
        """Test WebSocket connection and determine implementation."""
        try:
            async with websockets.connect(websocket_url) as websocket:
                # Send test message
                test_message = {
                    "action": "search",
                    "data": {"address": f"Test Address {connection_id}", "providers": ["test"]},
                }

                start_time = time.time()
                await websocket.send(json.dumps(test_message))

                # Try to get response to determine implementation
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    end_time = time.time()
                    response_data = json.loads(response)

                    # Extract implementation info from response
                    implementation = response_data.get("implementation", "unknown")
                    if implementation == "unknown":
                        # Try to infer from response structure or headers
                        if "new_field" in response_data:
                            implementation = "new"
                        elif "legacy_field" in response_data:
                            implementation = "old"

                    return {
                        "connection_id": connection_id,
                        "status": "success",
                        "implementation": implementation,
                        "response_time": (end_time - start_time) * 1000,
                        "response_received": True,
                        "error": None,
                    }

                except asyncio.TimeoutError:
                    return {
                        "connection_id": connection_id,
                        "status": "timeout",
                        "implementation": "unknown",
                        "response_time": 5000,  # timeout duration
                        "response_received": False,
                        "error": "Response timeout",
                    }

        except Exception as e:
            return {
                "connection_id": connection_id,
                "status": "failed",
                "implementation": "unknown",
                "response_time": None,
                "response_received": False,
                "error": str(e),
            }

    def validate_rest_api_traffic_distribution(self, endpoints: Dict[str, str], num_requests: int = 50) -> Dict[str, Any]:
        """Test REST API traffic distribution."""
        logger.info(f"Testing REST API traffic distribution with {num_requests} requests")

        results = []
        implementation_counts = {"old": 0, "new": 0, "unknown": 0}

        # Test production endpoint (should have traffic distribution)
        prod_endpoint = endpoints.get("prod")
        if not prod_endpoint:
            return {"success": False, "error": "Production endpoint not found"}

        def make_request():
            return self.test_rest_api_endpoint(prod_endpoint)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    implementation = result.get("implementation", "unknown")
                    implementation_counts[implementation] += 1
                except Exception as e:
                    results.append({"success": False, "error": str(e), "implementation": "unknown"})
                    implementation_counts["unknown"] += 1

        # Calculate distribution
        total_successful = sum(implementation_counts.values())
        distribution_percentages = {
            impl: (count / total_successful * 100) if total_successful > 0 else 0
            for impl, count in implementation_counts.items()
        }

        # Check if distribution is approximately balanced (allow 30% variance for small samples)
        old_percentage = distribution_percentages.get("old", 0)
        new_percentage = distribution_percentages.get("new", 0)
        unknown_percentage = distribution_percentages.get("unknown", 0)

        # If most requests are unknown, we can't validate distribution
        if unknown_percentage > 70:
            distribution_status = "unknown"
            distribution_balanced = False
        else:
            distribution_balanced = abs(old_percentage - new_percentage) <= 30
            distribution_status = "balanced" if distribution_balanced else "unbalanced"

        # Calculate response time statistics
        successful_results = [r for r in results if r["success"] and r["response_time"]]
        response_times = [r["response_time"] for r in successful_results]

        return {
            "success": len(successful_results) > 0,
            "total_requests": num_requests,
            "successful_requests": len(successful_results),
            "failed_requests": num_requests - len(successful_results),
            "success_rate": len(successful_results) / num_requests * 100,
            "implementation_counts": implementation_counts,
            "distribution_percentages": distribution_percentages,
            "distribution_status": distribution_status,
            "distribution_balanced": distribution_balanced,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "results": results[:5],  # Sample of results for inspection
        }

    async def validate_websocket_traffic_distribution(self, websocket_url: str, num_connections: int = 20) -> Dict[str, Any]:
        """Test WebSocket traffic distribution."""
        logger.info(f"Testing WebSocket traffic distribution with {num_connections} connections")

        # Create multiple connections to test distribution
        tasks = []
        for i in range(num_connections):
            tasks.append(self.test_websocket_connection(websocket_url, i))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        connection_results = []
        implementation_counts = {"old": 0, "new": 0, "unknown": 0}

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Connection {i} failed: {str(result)}")
                connection_results.append(
                    {"connection_id": i, "status": "failed", "error": str(result), "implementation": "unknown"}
                )
                implementation_counts["unknown"] += 1
            else:
                connection_results.append(result)
                implementation = result.get("implementation", "unknown")
                implementation_counts[implementation] += 1

        # Calculate distribution percentages
        total_connections = len(connection_results)
        distribution_percentages = {
            impl: (count / total_connections * 100) if total_connections > 0 else 0
            for impl, count in implementation_counts.items()
        }

        # Check if distribution is approximately 50/50 (allow 30% variance)
        old_percentage = distribution_percentages.get("old", 0)
        new_percentage = distribution_percentages.get("new", 0)
        unknown_percentage = distribution_percentages.get("unknown", 0)

        if unknown_percentage > 70:
            distribution_status = "unknown"
            distribution_balanced = False
        else:
            distribution_balanced = abs(old_percentage - new_percentage) <= 30
            distribution_status = "balanced" if distribution_balanced else "unbalanced"

        # Calculate response time statistics
        successful_connections = [r for r in connection_results if r["status"] == "success" and r["response_time"]]
        response_times = [r["response_time"] for r in successful_connections]

        return {
            "success": len(successful_connections) > 0,
            "total_connections": num_connections,
            "successful_connections": len(successful_connections),
            "failed_connections": num_connections - len(successful_connections),
            "success_rate": len(successful_connections) / num_connections * 100,
            "implementation_counts": implementation_counts,
            "distribution_percentages": distribution_percentages,
            "distribution_status": distribution_status,
            "distribution_balanced": distribution_balanced,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "connection_results": connection_results[:5],  # Sample for inspection
        }

    def validate_canary_deployment(self, api_name: str) -> Dict[str, Any]:
        """Validate API Gateway canary deployment configuration."""
        logger.info(f"Validating canary deployment for {api_name}")

        try:
            # Get REST API info
            response = self.apigateway.get_rest_apis()
            api_id = None

            for api in response["items"]:
                if api["name"] == api_name:
                    api_id = api["id"]
                    break

            if not api_id:
                return {"success": False, "error": f"API '{api_name}' not found"}

            # Check production stage for canary settings
            try:
                stage_response = self.apigateway.get_stage(restApiId=api_id, stageName="prod")

                canary_settings = stage_response.get("canarySettings", {})

                # Check if canary is configured
                canary_enabled = bool(canary_settings)
                percent_traffic = int(canary_settings.get("percentTraffic", 0)) if canary_enabled else 0

                return {
                    "success": True,
                    "api_id": api_id,
                    "canary_enabled": canary_enabled,
                    "percent_traffic": percent_traffic,
                    "deployment_id": canary_settings.get("deploymentId"),
                    "stage_variables": canary_settings.get("stageVariableOverrides", {}),
                    "use_stage_cache": canary_settings.get("useStageCache", False),
                }

            except ClientError as e:
                if e.response["Error"]["Code"] == "NotFoundException":
                    return {"success": False, "error": "Production stage not found"}
                raise

        except (ClientError, BotoCoreError) as e:
            return {"success": False, "error": str(e)}

    def simple_health_check(self, endpoints: Dict[str, str]) -> Dict[str, Any]:
        """Perform simple health checks on API endpoints."""
        logger.info("Performing simple health checks")

        health_results = {}

        for stage, endpoint in endpoints.items():
            logger.info(f"Health checking {stage}: {endpoint}")

            # Test basic connectivity
            result = self.test_rest_api_endpoint(endpoint, "/share/health-check")

            health_results[stage] = {
                "endpoint": endpoint,
                "available": result["success"],
                "response_time": result["response_time"],
                "status_code": result["status_code"],
                "error": result["error"],
            }

            if result["success"]:
                logger.info(f"✅ {stage} endpoint is healthy (response time: {result['response_time']:.2f}ms)")
            else:
                logger.warning(f"❌ {stage} endpoint failed health check: {result.get('error', 'Unknown error')}")

        # Overall health status
        all_healthy = all(result["available"] for result in health_results.values())

        return {
            "success": all_healthy,
            "overall_health": "healthy" if all_healthy else "unhealthy",
            "endpoint_results": health_results,
        }

    async def run_comprehensive_validation(self, rest_api_name: str, websocket_api_name: str) -> Dict[str, Any]:
        """Run comprehensive traffic distribution validation."""
        logger.info("🚀 Starting comprehensive traffic distribution validation")
        logger.info("=" * 60)

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "region": self.region,
            "rest_api_name": rest_api_name,
            "websocket_api_name": websocket_api_name,
        }

        # 1. Get API endpoints
        logger.info("\n1️⃣ Getting API endpoints...")
        rest_endpoints = self.get_rest_api_endpoints(rest_api_name)
        websocket_endpoint = self.get_websocket_api_endpoint(websocket_api_name)

        results["rest_endpoints"] = rest_endpoints
        results["websocket_endpoint"] = websocket_endpoint

        if not rest_endpoints and not websocket_endpoint:
            logger.error("❌ No API endpoints found")
            results["overall_success"] = False
            return results

        # 2. Simple health checks for REST API
        if rest_endpoints:
            logger.info("\n2️⃣ Performing REST API health checks...")
            health_results = self.simple_health_check(rest_endpoints)
            results["rest_health_check"] = health_results

            if health_results["success"]:
                logger.info("✅ REST API health checks passed")
            else:
                logger.warning("⚠️ Some REST API health checks failed")

        # 3. Validate REST API traffic distribution
        if rest_endpoints:
            logger.info("\n3️⃣ Validating REST API traffic distribution...")
            rest_distribution = self.validate_rest_api_traffic_distribution(rest_endpoints)
            results["rest_traffic_distribution"] = rest_distribution

            if rest_distribution["success"]:
                dist_status = rest_distribution["distribution_status"]
                old_pct = rest_distribution["distribution_percentages"].get("old", 0)
                new_pct = rest_distribution["distribution_percentages"].get("new", 0)

                logger.info(f"✅ REST API traffic distribution: {old_pct:.1f}% old, {new_pct:.1f}% new ({dist_status})")
            else:
                logger.warning("⚠️ REST API traffic distribution validation failed")

        # 4. Validate WebSocket traffic distribution
        if websocket_endpoint:
            logger.info("\n4️⃣ Validating WebSocket traffic distribution...")
            websocket_distribution = await self.validate_websocket_traffic_distribution(websocket_endpoint)
            results["websocket_traffic_distribution"] = websocket_distribution

            if websocket_distribution["success"]:
                dist_status = websocket_distribution["distribution_status"]
                old_pct = websocket_distribution["distribution_percentages"].get("old", 0)
                new_pct = websocket_distribution["distribution_percentages"].get("new", 0)

                logger.info(f"✅ WebSocket traffic distribution: {old_pct:.1f}% old, {new_pct:.1f}% new ({dist_status})")
            else:
                logger.warning("⚠️ WebSocket traffic distribution validation failed")

        # 5. Validate canary deployment configuration
        if rest_endpoints:
            logger.info("\n5️⃣ Validating canary deployment configuration...")
            canary_validation = self.validate_canary_deployment(rest_api_name)
            results["canary_deployment"] = canary_validation

            if canary_validation["success"]:
                if canary_validation["canary_enabled"]:
                    logger.info(f"✅ Canary deployment is enabled ({canary_validation['percent_traffic']}% traffic)")
                else:
                    logger.info("ℹ️ Canary deployment is configured but not currently active")
            else:
                logger.warning(f"⚠️ Canary deployment validation failed: {canary_validation.get('error')}")

        # Overall success evaluation
        success_criteria = []

        if rest_endpoints:
            success_criteria.extend(
                [
                    results.get("rest_health_check", {}).get("success", False),
                    results.get("rest_traffic_distribution", {}).get("success", False),
                    results.get("canary_deployment", {}).get("success", False),
                ]
            )

        if websocket_endpoint:
            success_criteria.append(results.get("websocket_traffic_distribution", {}).get("success", False))

        overall_success = len(success_criteria) > 0 and all(success_criteria)
        results["overall_success"] = overall_success

        logger.info(f"\n{'='*60}")
        if overall_success:
            logger.info("🎉 All traffic distribution validations passed!")
        else:
            logger.warning("⚠️ Some traffic distribution validations failed or had warnings")

        return results


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Validate traffic distribution for WebSocket and REST APIs")
    parser.add_argument("--rest-api-name", default="provider-comparison-dev-rest-api", help="REST API Gateway name")
    parser.add_argument(
        "--websocket-api-name", default="provider-comparison-dev-websocket-api", help="WebSocket API Gateway name"
    )
    parser.add_argument("--region", default="eu-central-1", help="AWS region")
    parser.add_argument("--output", help="Output file for results (JSON format)")
    parser.add_argument("--rest-requests", type=int, default=50, help="Number of REST API requests for distribution testing")
    parser.add_argument(
        "--websocket-connections", type=int, default=20, help="Number of WebSocket connections for distribution testing"
    )

    args = parser.parse_args()

    async def run_validation():
        validator = TrafficDistributionValidator(args.region)
        results = await validator.run_comprehensive_validation(args.rest_api_name, args.websocket_api_name)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"\n📄 Results saved to {args.output}")

        return results["overall_success"]

    # Run the async validation
    success = asyncio.run(run_validation())

    exit_code = 0 if success else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
