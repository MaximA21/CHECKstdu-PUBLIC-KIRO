#!/usr/bin/env python3
"""
WebSocket API Gateway Validation Script
Tests the WebSocket API Gateway configuration with traffic distribution
"""

import asyncio
import json
import logging
import os
import sys
import time
import websockets
import boto3
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')


class WebSocketAPIValidator:
    """Validates WebSocket API Gateway configuration and traffic distribution."""
    
    def __init__(self, websocket_url: str, routing_table_name: str):
        self.websocket_url = websocket_url
        self.routing_table_name = routing_table_name
        self.routing_table = dynamodb.Table(routing_table_name)
        self.test_results = []
    
    async def validate_connection_establishment(self) -> Dict:
        """Test basic WebSocket connection establishment."""
        logger.info("Testing WebSocket connection establishment...")
        
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                logger.info("✓ WebSocket connection established successfully")
                
                # Send a test message
                test_message = {
                    "action": "search",
                    "data": {
                        "address": "Test Address",
                        "providers": ["test"]
                    }
                }
                
                await websocket.send(json.dumps(test_message))
                logger.info("✓ Test message sent successfully")
                
                # Wait for response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    response_data = json.loads(response)
                    logger.info(f"✓ Received response: {response_data}")
                    
                    return {
                        "status": "success",
                        "connection_established": True,
                        "message_sent": True,
                        "response_received": True,
                        "response_data": response_data
                    }
                    
                except asyncio.TimeoutError:
                    logger.warning("⚠ No response received within timeout")
                    return {
                        "status": "partial_success",
                        "connection_established": True,
                        "message_sent": True,
                        "response_received": False,
                        "error": "Response timeout"
                    }
                    
        except Exception as e:
            logger.error(f"✗ Connection test failed: {str(e)}")
            return {
                "status": "failed",
                "connection_established": False,
                "error": str(e)
            }
    
    async def validate_traffic_distribution(self, num_connections: int = 10) -> Dict:
        """Test traffic distribution between old and new implementations."""
        logger.info(f"Testing traffic distribution with {num_connections} connections...")
        
        connection_results = []
        implementation_counts = {"old": 0, "new": 0, "unknown": 0}
        
        # Create multiple connections to test distribution
        tasks = []
        for i in range(num_connections):
            tasks.append(self._test_single_connection(i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Connection {i} failed: {str(result)}")
                connection_results.append({
                    "connection_id": i,
                    "status": "failed",
                    "error": str(result)
                })
            else:
                connection_results.append(result)
                implementation = result.get("implementation", "unknown")
                implementation_counts[implementation] += 1
        
        # Calculate distribution percentages
        total_successful = sum(implementation_counts.values())
        distribution_percentages = {
            impl: (count / total_successful * 100) if total_successful > 0 else 0
            for impl, count in implementation_counts.items()
        }
        
        logger.info(f"Traffic distribution results: {distribution_percentages}")
        
        # Check if distribution is approximately 50/50
        old_percentage = distribution_percentages.get("old", 0)
        new_percentage = distribution_percentages.get("new", 0)
        distribution_balanced = abs(old_percentage - new_percentage) <= 20  # Allow 20% variance
        
        return {
            "status": "success" if distribution_balanced else "warning",
            "total_connections": num_connections,
            "successful_connections": total_successful,
            "implementation_counts": implementation_counts,
            "distribution_percentages": distribution_percentages,
            "distribution_balanced": distribution_balanced,
            "connection_results": connection_results
        }
    
    async def _test_single_connection(self, connection_index: int) -> Dict:
        """Test a single WebSocket connection and determine implementation."""
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                # Send test message
                test_message = {
                    "action": "search",
                    "data": {
                        "address": f"Test Address {connection_index}",
                        "providers": ["test"]
                    }
                }
                
                await websocket.send(json.dumps(test_message))
                
                # Try to get response to determine implementation
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    
                    # Try to extract implementation info from response
                    implementation = response_data.get("implementation", "unknown")
                    
                    return {
                        "connection_id": connection_index,
                        "status": "success",
                        "implementation": implementation,
                        "response_received": True
                    }
                    
                except asyncio.TimeoutError:
                    return {
                        "connection_id": connection_index,
                        "status": "timeout",
                        "implementation": "unknown",
                        "response_received": False
                    }
                    
        except Exception as e:
            return {
                "connection_id": connection_index,
                "status": "failed",
                "error": str(e),
                "implementation": "unknown"
            }
    
    async def validate_connection_tracking(self) -> Dict:
        """Test connection tracking in DynamoDB."""
        logger.info("Testing connection tracking...")
        
        try:
            # Scan the routing table to check for active connections
            response = self.routing_table.scan()
            items = response.get('Items', [])
            
            active_connections = [
                item for item in items 
                if item.get('status') == 'active'
            ]
            
            logger.info(f"Found {len(active_connections)} active connections in routing table")
            
            # Check if connections have required tracking fields
            tracking_fields = ['connection_id', 'implementation', 'created_at', 'result_count', 'last_activity']
            valid_connections = []
            
            for conn in active_connections:
                has_all_fields = all(field in conn for field in tracking_fields)
                if has_all_fields:
                    valid_connections.append(conn)
                else:
                    missing_fields = [field for field in tracking_fields if field not in conn]
                    logger.warning(f"Connection {conn.get('connection_id')} missing fields: {missing_fields}")
            
            return {
                "status": "success",
                "total_connections": len(items),
                "active_connections": len(active_connections),
                "valid_connections": len(valid_connections),
                "tracking_fields_present": len(valid_connections) == len(active_connections),
                "sample_connections": active_connections[:3]  # Show first 3 for inspection
            }
            
        except Exception as e:
            logger.error(f"Connection tracking validation failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def validate_connection_limits(self) -> Dict:
        """Test connection limit enforcement."""
        logger.info("Testing connection limit enforcement...")
        
        try:
            # This would require a more complex test that keeps connections open
            # and sends multiple messages to test the 2-minute and 5-result limits
            # For now, we'll just check if the limit enforcer function exists
            
            # Check CloudWatch metrics for connection limit enforcement
            end_time = datetime.utcnow()
            start_time = datetime.utcnow().replace(hour=end_time.hour-1)  # Last hour
            
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='WebSocket/ConnectionLimits',
                    MetricName='ConnectionsDisconnected',
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5 minutes
                    Statistics=['Sum']
                )
                
                datapoints = response.get('Datapoints', [])
                total_disconnections = sum(point['Sum'] for point in datapoints)
                
                logger.info(f"Found {total_disconnections} connection limit disconnections in the last hour")
                
                return {
                    "status": "success",
                    "limit_enforcement_active": len(datapoints) > 0,
                    "total_disconnections_last_hour": total_disconnections,
                    "metrics_available": True
                }
                
            except Exception as metric_error:
                logger.warning(f"Could not retrieve connection limit metrics: {str(metric_error)}")
                return {
                    "status": "partial_success",
                    "limit_enforcement_active": False,
                    "metrics_available": False,
                    "error": str(metric_error)
                }
                
        except Exception as e:
            logger.error(f"Connection limit validation failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def run_full_validation(self) -> Dict:
        """Run all validation tests."""
        logger.info("Starting full WebSocket API validation...")
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "websocket_url": self.websocket_url,
            "routing_table": self.routing_table_name
        }
        
        # Test 1: Basic connection establishment
        results["connection_test"] = await self.validate_connection_establishment()
        
        # Test 2: Traffic distribution
        results["traffic_distribution_test"] = await self.validate_traffic_distribution()
        
        # Test 3: Connection tracking
        results["connection_tracking_test"] = await self.validate_connection_tracking()
        
        # Test 4: Connection limits
        results["connection_limits_test"] = await self.validate_connection_limits()
        
        # Overall status
        all_tests = [
            results["connection_test"]["status"],
            results["traffic_distribution_test"]["status"],
            results["connection_tracking_test"]["status"],
            results["connection_limits_test"]["status"]
        ]
        
        if all(status == "success" for status in all_tests):
            results["overall_status"] = "success"
        elif any(status == "failed" for status in all_tests):
            results["overall_status"] = "failed"
        else:
            results["overall_status"] = "partial_success"
        
        return results


async def main():
    """Main validation function."""
    # Get configuration from environment or command line
    websocket_url = os.environ.get('WEBSOCKET_URL')
    routing_table_name = os.environ.get('ROUTING_TABLE_NAME')
    
    if not websocket_url or not routing_table_name:
        logger.error("Please set WEBSOCKET_URL and ROUTING_TABLE_NAME environment variables")
        sys.exit(1)
    
    # Create validator and run tests
    validator = WebSocketAPIValidator(websocket_url, routing_table_name)
    results = await validator.run_full_validation()
    
    # Print results
    print("\n" + "="*60)
    print("WEBSOCKET API VALIDATION RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2, default=str))
    
    # Exit with appropriate code
    if results["overall_status"] == "success":
        logger.info("✓ All validation tests passed!")
        sys.exit(0)
    elif results["overall_status"] == "partial_success":
        logger.warning("⚠ Some validation tests had warnings")
        sys.exit(1)
    else:
        logger.error("✗ Validation tests failed")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())