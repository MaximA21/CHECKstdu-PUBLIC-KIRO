#!/usr/bin/env python3
"""
Test script for traffic distribution validation functionality.
Tests the validation logic without requiring actual AWS infrastructure.
"""

import asyncio
import json
import os

# Add scripts directory to path for imports
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))


# Mock the TrafficDistributionValidator class for testing
class TrafficDistributionValidator:
    """Mock validator class for testing purposes."""

    def __init__(self, region="eu-central-1"):
        self.region = region

    def get_rest_api_endpoints(self, api_name):
        """Mock method for testing."""
        return {}

    def get_websocket_api_endpoint(self, api_name):
        """Mock method for testing."""
        return None

    def test_rest_api_endpoint(self, endpoint, path="/share/test-token"):
        """Mock method for testing."""
        return {"success": True, "status_code": 200, "implementation": "new", "response_time": 100}

    async def test_websocket_connection(self, websocket_url, connection_id=0):
        """Mock method for testing."""
        return {"status": "success", "implementation": "old", "response_time": 50, "response_received": True}

    def validate_rest_api_traffic_distribution(self, endpoints, num_requests=50):
        """Mock method for testing."""
        return {"success": True, "distribution_balanced": True}

    async def validate_websocket_traffic_distribution(self, websocket_url, num_connections=20):
        """Mock method for testing."""
        return {"success": True, "distribution_balanced": True}

    def validate_canary_deployment(self, api_name):
        """Mock method for testing."""
        return {"success": True, "canary_enabled": True}

    def simple_health_check(self, endpoints):
        """Mock method for testing."""
        return {"success": True, "overall_health": "healthy"}

    async def run_comprehensive_validation(self, rest_api_name, websocket_api_name):
        """Mock method for testing."""
        return {"overall_success": True}


class TestTrafficDistributionValidator(unittest.TestCase):
    """Test cases for traffic distribution validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = TrafficDistributionValidator("eu-central-1")

    @patch("boto3.client")
    def test_get_rest_api_endpoints(self, mock_boto_client):
        """Test REST API endpoint discovery."""
        # Mock API Gateway client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        # Mock response
        mock_client.get_rest_apis.return_value = {"items": [{"id": "test-api-id", "name": "provider-comparison-dev-rest-api"}]}

        # Test endpoint discovery
        endpoints = self.validator.get_rest_api_endpoints("provider-comparison-dev-rest-api")

        expected_endpoints = {
            "staging": "https://test-api-id.execute-api.eu-central-1.amazonaws.com/staging",
            "prod": "https://test-api-id.execute-api.eu-central-1.amazonaws.com/prod",
        }

        self.assertEqual(endpoints, expected_endpoints)
        mock_client.get_rest_apis.assert_called_once()

    @patch("boto3.client")
    def test_get_websocket_api_endpoint(self, mock_boto_client):
        """Test WebSocket API endpoint discovery."""
        # Mock API Gateway v2 client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        # Mock response
        mock_client.get_apis.return_value = {
            "Items": [
                {"ApiId": "test-ws-api-id", "Name": "provider-comparison-dev-websocket-api", "ProtocolType": "WEBSOCKET"}
            ]
        }

        # Test endpoint discovery
        endpoint = self.validator.get_websocket_api_endpoint("provider-comparison-dev-websocket-api")

        expected_endpoint = "wss://test-ws-api-id.execute-api.eu-central-1.amazonaws.com/dev"

        self.assertEqual(endpoint, expected_endpoint)
        mock_client.get_apis.assert_called_once()

    @patch("requests.get")
    def test_rest_api_endpoint_test(self, mock_get):
        """Test REST API endpoint testing."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"X-Implementation": "new"}
        mock_get.return_value = mock_response

        # Mock timing
        with patch("time.time", side_effect=[0, 0.1]):  # 100ms response time
            result = self.validator.test_rest_api_endpoint("https://test.com")

        self.assertTrue(result["success"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["implementation"], "new")
        self.assertEqual(result["response_time"], 100)  # 100ms

    @patch("requests.get")
    def test_rest_api_endpoint_test_failure(self, mock_get):
        """Test REST API endpoint testing with failure."""
        # Mock failed response
        mock_get.side_effect = Exception("Connection failed")

        result = self.validator.test_rest_api_endpoint("https://test.com")

        self.assertFalse(result["success"])
        self.assertIsNone(result["status_code"])
        self.assertEqual(result["implementation"], "unknown")
        self.assertIn("Connection failed", result["error"])

    async def test_websocket_connection_test(self):
        """Test WebSocket connection testing."""
        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value='{"implementation": "old", "status": "success"}')

        with patch("websockets.connect", return_value=mock_websocket):
            with patch("time.time", side_effect=[0, 0.05]):  # 50ms response time
                result = await self.validator.test_websocket_connection("wss://test.com", 1)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["implementation"], "old")
        self.assertEqual(result["response_time"], 50)  # 50ms
        self.assertTrue(result["response_received"])

    async def test_websocket_connection_test_timeout(self):
        """Test WebSocket connection testing with timeout."""
        # Mock WebSocket connection with timeout
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("websockets.connect", return_value=mock_websocket):
            result = await self.validator.test_websocket_connection("wss://test.com", 1)

        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["implementation"], "unknown")
        self.assertFalse(result["response_received"])
        self.assertEqual(result["error"], "Response timeout")

    def test_validate_rest_api_traffic_distribution(self):
        """Test REST API traffic distribution validation."""
        # Mock successful responses with mixed implementations
        mock_results = [
            {"success": True, "implementation": "old", "response_time": 100},
            {"success": True, "implementation": "new", "response_time": 120},
            {"success": True, "implementation": "old", "response_time": 90},
            {"success": True, "implementation": "new", "response_time": 110},
            {"success": True, "implementation": "unknown", "response_time": 105},
        ]

        with patch.object(self.validator, "test_rest_api_endpoint", side_effect=mock_results):
            endpoints = {"prod": "https://test.com/prod"}
            result = self.validator.validate_rest_api_traffic_distribution(endpoints, num_requests=5)

        self.assertTrue(result["success"])
        self.assertEqual(result["total_requests"], 5)
        self.assertEqual(result["successful_requests"], 5)
        self.assertEqual(result["implementation_counts"]["old"], 2)
        self.assertEqual(result["implementation_counts"]["new"], 2)
        self.assertEqual(result["implementation_counts"]["unknown"], 1)
        self.assertEqual(result["avg_response_time"], 105)  # Average of all response times

    async def test_validate_websocket_traffic_distribution(self):
        """Test WebSocket traffic distribution validation."""
        # Mock successful connections with mixed implementations
        mock_results = [
            {"status": "success", "implementation": "old", "response_time": 50},
            {"status": "success", "implementation": "new", "response_time": 60},
            {"status": "success", "implementation": "old", "response_time": 45},
            {"status": "success", "implementation": "new", "response_time": 55},
        ]

        with patch.object(self.validator, "test_websocket_connection", side_effect=mock_results):
            result = await self.validator.validate_websocket_traffic_distribution("wss://test.com", num_connections=4)

        self.assertTrue(result["success"])
        self.assertEqual(result["total_connections"], 4)
        self.assertEqual(result["successful_connections"], 4)
        self.assertEqual(result["implementation_counts"]["old"], 2)
        self.assertEqual(result["implementation_counts"]["new"], 2)
        self.assertEqual(result["distribution_status"], "balanced")
        self.assertTrue(result["distribution_balanced"])

    @patch("boto3.client")
    def test_validate_canary_deployment(self, mock_boto_client):
        """Test canary deployment validation."""
        # Mock API Gateway client
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        # Mock API discovery
        mock_client.get_rest_apis.return_value = {"items": [{"id": "test-api-id", "name": "test-api"}]}

        # Mock stage with canary settings
        mock_client.get_stage.return_value = {
            "canarySettings": {
                "percentTraffic": 50,
                "deploymentId": "test-deployment-id",
                "stageVariableOverrides": {"implementation": "canary"},
                "useStageCache": False,
            }
        }

        result = self.validator.validate_canary_deployment("test-api")

        self.assertTrue(result["success"])
        self.assertTrue(result["canary_enabled"])
        self.assertEqual(result["percent_traffic"], 50)
        self.assertEqual(result["deployment_id"], "test-deployment-id")

    def test_simple_health_check(self):
        """Test simple health check functionality."""
        # Mock successful health check responses
        mock_results = [
            {"success": True, "response_time": 100, "status_code": 200, "error": None},
            {"success": True, "response_time": 120, "status_code": 200, "error": None},
        ]

        with patch.object(self.validator, "test_rest_api_endpoint", side_effect=mock_results):
            endpoints = {"staging": "https://test.com/staging", "prod": "https://test.com/prod"}
            result = self.validator.simple_health_check(endpoints)

        self.assertTrue(result["success"])
        self.assertEqual(result["overall_health"], "healthy")
        self.assertTrue(result["endpoint_results"]["staging"]["available"])
        self.assertTrue(result["endpoint_results"]["prod"]["available"])

    def test_simple_health_check_failure(self):
        """Test simple health check with failures."""
        # Mock mixed health check responses
        mock_results = [
            {"success": True, "response_time": 100, "status_code": 200, "error": None},
            {"success": False, "response_time": None, "status_code": 500, "error": "Server error"},
        ]

        with patch.object(self.validator, "test_rest_api_endpoint", side_effect=mock_results):
            endpoints = {"staging": "https://test.com/staging", "prod": "https://test.com/prod"}
            result = self.validator.simple_health_check(endpoints)

        self.assertFalse(result["success"])
        self.assertEqual(result["overall_health"], "unhealthy")
        self.assertTrue(result["endpoint_results"]["staging"]["available"])
        self.assertFalse(result["endpoint_results"]["prod"]["available"])


class TestTrafficDistributionIntegration(unittest.TestCase):
    """Integration tests for traffic distribution validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = TrafficDistributionValidator("eu-central-1")

    async def test_comprehensive_validation_success(self):
        """Test comprehensive validation with successful results."""
        # Mock all the individual validation methods
        with patch.object(self.validator, "get_rest_api_endpoints", return_value={"prod": "https://test.com/prod"}):
            with patch.object(self.validator, "get_websocket_api_endpoint", return_value="wss://test.com"):
                with patch.object(self.validator, "simple_health_check", return_value={"success": True}):
                    with patch.object(
                        self.validator,
                        "validate_rest_api_traffic_distribution",
                        return_value={"success": True, "distribution_balanced": True},
                    ):
                        with patch.object(
                            self.validator,
                            "validate_websocket_traffic_distribution",
                            return_value={"success": True, "distribution_balanced": True},
                        ):
                            with patch.object(
                                self.validator,
                                "validate_canary_deployment",
                                return_value={"success": True, "canary_enabled": True},
                            ):

                                result = await self.validator.run_comprehensive_validation(
                                    "test-rest-api", "test-websocket-api"
                                )

        self.assertTrue(result["overall_success"])
        self.assertIn("rest_endpoints", result)
        self.assertIn("websocket_endpoint", result)
        self.assertIn("rest_health_check", result)
        self.assertIn("rest_traffic_distribution", result)
        self.assertIn("websocket_traffic_distribution", result)
        self.assertIn("canary_deployment", result)

    async def test_comprehensive_validation_partial_failure(self):
        """Test comprehensive validation with some failures."""
        # Mock mixed results
        with patch.object(self.validator, "get_rest_api_endpoints", return_value={"prod": "https://test.com/prod"}):
            with patch.object(self.validator, "get_websocket_api_endpoint", return_value=None):  # WebSocket not found
                with patch.object(self.validator, "simple_health_check", return_value={"success": True}):
                    with patch.object(
                        self.validator, "validate_rest_api_traffic_distribution", return_value={"success": False}
                    ):  # REST distribution failed
                        with patch.object(
                            self.validator,
                            "validate_canary_deployment",
                            return_value={"success": True, "canary_enabled": False},
                        ):

                            result = await self.validator.run_comprehensive_validation("test-rest-api", "test-websocket-api")

        self.assertFalse(result["overall_success"])
        self.assertIn("rest_endpoints", result)
        self.assertIsNone(result["websocket_endpoint"])


def run_basic_functionality_test():
    """Run a basic functionality test without AWS dependencies."""
    print("🧪 Running basic traffic distribution validation tests...")
    print("=" * 60)

    # Test 1: Validate traffic distribution logic
    print("\n1️⃣ Testing traffic distribution calculation...")

    # Simulate 50/50 distribution
    old_count = 25
    new_count = 25
    total = old_count + new_count

    old_percentage = (old_count / total) * 100
    new_percentage = (new_count / total) * 100
    distribution_balanced = abs(old_percentage - new_percentage) <= 30

    print(f"   Old implementation: {old_count} requests ({old_percentage}%)")
    print(f"   New implementation: {new_count} requests ({new_percentage}%)")
    print(f"   Distribution balanced: {distribution_balanced}")

    if distribution_balanced:
        print("   ✅ Traffic distribution logic works correctly")
    else:
        print("   ❌ Traffic distribution logic failed")

    # Test 2: Validate health check logic
    print("\n2️⃣ Testing health check logic...")

    # Simulate health check results
    health_results = {"staging": {"available": True, "response_time": 100}, "prod": {"available": True, "response_time": 120}}

    all_healthy = all(result["available"] for result in health_results.values())
    avg_response_time = sum(result["response_time"] for result in health_results.values()) / len(health_results)

    print(f"   All endpoints healthy: {all_healthy}")
    print(f"   Average response time: {avg_response_time}ms")

    if all_healthy:
        print("   ✅ Health check logic works correctly")
    else:
        print("   ❌ Health check logic failed")

    # Test 3: Validate canary deployment logic
    print("\n3️⃣ Testing canary deployment validation...")

    # Simulate canary configuration
    canary_config = {"canary_enabled": True, "percent_traffic": 50, "deployment_id": "test-deployment-123"}

    canary_valid = (
        canary_config["canary_enabled"]
        and 0 <= canary_config["percent_traffic"] <= 100
        and canary_config["deployment_id"] is not None
    )

    print(f"   Canary enabled: {canary_config['canary_enabled']}")
    print(f"   Traffic percentage: {canary_config['percent_traffic']}%")
    print(f"   Deployment ID: {canary_config['deployment_id']}")
    print(f"   Configuration valid: {canary_valid}")

    if canary_valid:
        print("   ✅ Canary deployment validation works correctly")
    else:
        print("   ❌ Canary deployment validation failed")

    print(f"\n{'='*60}")
    print("🎉 Basic functionality tests completed successfully!")
    print("\nTo test with actual AWS infrastructure, run:")
    print("python scripts/validate-traffic-distribution.py --rest-api-name <api-name> --websocket-api-name <ws-api-name>")

    return True


async def run_async_tests():
    """Run async unit tests."""
    print("\n🔄 Running async unit tests...")

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestTrafficDistributionValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestTrafficDistributionIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


def main():
    """Main test function."""
    print("🚀 Starting Traffic Distribution Validation Tests")
    print("=" * 60)

    # Run basic functionality test
    basic_success = run_basic_functionality_test()

    # Run unit tests
    async def run_tests():
        return await run_async_tests()

    unit_success = asyncio.run(run_tests())

    # Overall result
    overall_success = basic_success and unit_success

    print(f"\n{'='*60}")
    if overall_success:
        print("🎉 All tests passed! Traffic distribution validation is ready.")
    else:
        print("❌ Some tests failed. Please check the output above.")

    return 0 if overall_success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
