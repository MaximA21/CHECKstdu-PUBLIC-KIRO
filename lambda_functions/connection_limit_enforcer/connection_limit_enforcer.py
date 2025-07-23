"""
Connection Limit Enforcer Lambda Function
Periodically checks and enforces connection limits for all active WebSocket connections
"""

import json
import logging
import os
import sys
from datetime import datetime

import boto3

# Add src to path for imports
sys.path.append("/opt/python")
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
cloudwatch = boto3.client("cloudwatch")

try:
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
    from src.shared.dependency_injection.bootstrap import get_container
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for development/testing
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
    from src.shared.dependency_injection.bootstrap import get_container


def lambda_handler(event, context):
    """
    Lambda handler for periodic connection limit enforcement.
    This function is triggered by CloudWatch Events (EventBridge) on a schedule.
    """
    try:
        # Handle warmer requests efficiently
        if event.get("warmer"):
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Lambda warmed successfully", "function": "connection_limit_enforcer"}),
            }

        logger.info("Starting connection limit enforcement")

        # Get DI container
        container = get_container()

        # Get connection management use case
        connection_management_use_case = container.get(ConnectionManagementUseCase)

        # Enforce connection limits for all active connections
        import asyncio

        enforcement_result = asyncio.run(connection_management_use_case.enforce_connection_limits_for_all())

        # Log results
        logger.info(
            "Connection limit enforcement completed",
            {
                "connections_checked": enforcement_result.get("connections_checked", 0),
                "connections_disconnected": enforcement_result.get("connections_disconnected", 0),
                "errors": enforcement_result.get("errors", 0),
            },
        )

        # Send custom metrics to CloudWatch
        import asyncio

        asyncio.run(send_enforcement_metrics(enforcement_result))

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Connection limit enforcement completed", "result": enforcement_result}),
        }

    except Exception as e:
        logger.error(f"Error in connection limit enforcer: {str(e)}", exc_info=True)

        # Send error metric to CloudWatch
        try:
            cloudwatch.put_metric_data(
                Namespace="WebSocket/ConnectionLimits",
                MetricData=[{"MetricName": "EnforcementErrors", "Value": 1, "Unit": "Count", "Timestamp": datetime.utcnow()}],
            )
        except:
            pass  # Don't fail if metrics can't be sent

        return {"statusCode": 500, "body": json.dumps({"error": "Connection limit enforcement failed", "message": str(e)})}


async def send_enforcement_metrics(enforcement_result: dict):
    """Send enforcement metrics to CloudWatch."""
    try:
        metric_data = []

        # Connections checked metric
        if "connections_checked" in enforcement_result:
            metric_data.append(
                {
                    "MetricName": "ConnectionsChecked",
                    "Value": enforcement_result["connections_checked"],
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow(),
                }
            )

        # Connections disconnected metric
        if "connections_disconnected" in enforcement_result:
            metric_data.append(
                {
                    "MetricName": "ConnectionsDisconnected",
                    "Value": enforcement_result["connections_disconnected"],
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow(),
                }
            )

        # Errors metric
        if "errors" in enforcement_result:
            metric_data.append(
                {
                    "MetricName": "EnforcementErrors",
                    "Value": enforcement_result["errors"],
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow(),
                }
            )

        # Send metrics to CloudWatch
        if metric_data:
            cloudwatch.put_metric_data(Namespace="WebSocket/ConnectionLimits", MetricData=metric_data)

            logger.debug(f"Sent {len(metric_data)} metrics to CloudWatch")

    except Exception as e:
        logger.warning(f"Failed to send enforcement metrics: {str(e)}")


def cleanup_handler(event, context):
    """
    Alternative handler for cleanup operations.
    Can be used for more aggressive cleanup of stale connections.
    """
    try:
        logger.info("Starting connection cleanup")

        # Import DI components
        from src.application.use_cases.connection_management_use_case import ConnectionManagementUseCase
        from src.shared.dependency_injection.bootstrap import get_container

        # Get DI container
        container = get_container()

        # Get connection management use case
        connection_management_use_case = container.get(ConnectionManagementUseCase)

        # Clean up stale connections (30 minutes timeout)
        import asyncio

        cleanup_result = asyncio.run(connection_management_use_case.cleanup_stale_connections(timeout_minutes=30))

        logger.info("Connection cleanup completed", cleanup_result)

        return {"statusCode": 200, "body": json.dumps({"message": "Connection cleanup completed", "result": cleanup_result})}

    except Exception as e:
        logger.error(f"Error in connection cleanup: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "Connection cleanup failed", "message": str(e)})}
