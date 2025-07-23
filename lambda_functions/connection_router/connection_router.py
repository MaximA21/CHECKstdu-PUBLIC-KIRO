"""
Connection Router Lambda Function
Implements 50/50 traffic distribution between old and new WebSocket implementations
"""

import json
import os
import hashlib
import boto3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

# Environment variables
ROUTING_TABLE_NAME = os.environ["ROUTING_TABLE_NAME"]
OLD_CONNECT_LAMBDA = os.environ["OLD_CONNECT_LAMBDA"]
NEW_CONNECT_LAMBDA = os.environ["NEW_CONNECT_LAMBDA"]
OLD_SEARCH_LAMBDA = os.environ["OLD_SEARCH_LAMBDA"]
NEW_SEARCH_LAMBDA = os.environ["NEW_SEARCH_LAMBDA"]
TRAFFIC_SPLIT_PERCENTAGE = int(os.environ.get("TRAFFIC_SPLIT_PERCENTAGE", "50"))

# DynamoDB table
routing_table = dynamodb.Table(ROUTING_TABLE_NAME)


def lambda_handler(event, context):
    """
    Main Lambda handler for connection routing.
    Routes WebSocket connections to old or new implementation based on 50/50 split.
    """
    try:
        # Handle warmer requests efficiently
        if event.get("warmer"):
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Lambda warmed successfully", "function": "connection_router"}),
            }

        logger.info(f"Connection router invoked with event: {json.dumps(event, default=str)}")

        # Extract connection information
        connection_id = event.get("requestContext", {}).get("connectionId")
        route_key = event.get("requestContext", {}).get("routeKey")

        if not connection_id:
            logger.error("No connection ID found in event")
            return {"statusCode": 400, "body": json.dumps({"error": "Connection ID missing"})}

        logger.info(f"Processing route '{route_key}' for connection {connection_id}")

        # Determine which implementation to use
        implementation = determine_implementation(connection_id, route_key)

        # Route to appropriate Lambda function
        if route_key == "$connect":
            response = route_connect_request(event, implementation)
        elif route_key == "search":
            response = route_search_request(event, implementation)
            # Update connection activity for search requests
            update_connection_activity(connection_id, increment_result_count=False)
        else:
            logger.error(f"Unknown route key: {route_key}")
            return {"statusCode": 400, "body": json.dumps({"error": f"Unknown route: {route_key}"})}

        # Log routing decision
        logger.info(f"Routed connection {connection_id} to {implementation} implementation for route {route_key}")

        return response

    except Exception as e:
        logger.error(f"Error in connection router: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


def determine_implementation(connection_id: str, route_key: str) -> str:
    """
    Determine which implementation (old/new) to use for a connection.
    For $connect, uses hash-based routing for 50/50 split.
    For other routes, uses stored routing decision.
    """
    try:
        if route_key == "$connect":
            # For new connections, use hash-based routing for consistent 50/50 split
            implementation = hash_based_routing(connection_id)

            # Store routing decision for this connection
            store_routing_decision(connection_id, implementation)

            return implementation
        else:
            # For existing connections, use stored routing decision
            stored_implementation = get_stored_routing_decision(connection_id)

            if stored_implementation:
                return stored_implementation
            else:
                # Fallback to hash-based routing if no stored decision
                logger.warning(f"No stored routing decision for connection {connection_id}, using hash-based fallback")
                implementation = hash_based_routing(connection_id)
                store_routing_decision(connection_id, implementation)
                return implementation

    except Exception as e:
        logger.error(f"Error determining implementation for connection {connection_id}: {str(e)}")
        # Default to new implementation on error
        return "new"


def hash_based_routing(connection_id: str) -> str:
    """
    Use hash-based routing to achieve consistent 50/50 traffic split.
    """
    # Create hash of connection ID
    hash_value = hashlib.md5(connection_id.encode()).hexdigest()

    # Convert first 8 characters to integer
    hash_int = int(hash_value[:8], 16)

    # Use modulo to determine routing (50/50 split)
    if hash_int % 100 < TRAFFIC_SPLIT_PERCENTAGE:
        return "new"
    else:
        return "old"


def store_routing_decision(connection_id: str, implementation: str) -> None:
    """
    Store routing decision in DynamoDB for consistency across requests.
    Also initializes connection tracking for limit enforcement.
    """
    try:
        # TTL set to 3 hours (connections should not last longer than 2 minutes)
        ttl = int((datetime.utcnow() + timedelta(hours=3)).timestamp())
        current_time = datetime.utcnow().isoformat()

        routing_table.put_item(
            Item={
                "connection_id": connection_id,
                "implementation": implementation,
                "created_at": current_time,
                "ttl": ttl,
                # Connection tracking fields for limit enforcement
                "result_count": 0,
                "last_activity": current_time,
                "status": "active",
            }
        )

        logger.debug(f"Stored routing decision with tracking: {connection_id} -> {implementation}")

    except Exception as e:
        logger.error(f"Error storing routing decision for {connection_id}: {str(e)}")


def get_stored_routing_decision(connection_id: str) -> Optional[str]:
    """
    Retrieve stored routing decision from DynamoDB.
    """
    try:
        response = routing_table.get_item(Key={"connection_id": connection_id})

        if "Item" in response:
            implementation = response["Item"]["implementation"]
            logger.debug(f"Retrieved routing decision: {connection_id} -> {implementation}")
            return implementation
        else:
            logger.debug(f"No stored routing decision found for {connection_id}")
            return None

    except Exception as e:
        logger.error(f"Error retrieving routing decision for {connection_id}: {str(e)}")
        return None


def route_connect_request(event: Dict[str, Any], implementation: str) -> Dict[str, Any]:
    """
    Route $connect request to appropriate Lambda function.
    """
    target_function = NEW_CONNECT_LAMBDA if implementation == "new" else OLD_CONNECT_LAMBDA

    logger.info(f"Routing connect request to {target_function} ({implementation} implementation)")

    try:
        # Invoke target Lambda function
        response = lambda_client.invoke(
            FunctionName=target_function, InvocationType="RequestResponse", Payload=json.dumps(event)
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Add implementation info to response for monitoring
        if isinstance(payload.get("body"), str):
            try:
                body = json.loads(payload["body"])
                body["implementation"] = implementation
                payload["body"] = json.dumps(body)
            except:
                pass

        logger.info(f"Connect request routed successfully to {implementation} implementation")
        return payload

    except Exception as e:
        logger.error(f"Error routing connect request to {target_function}: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to route connect request"})}


def route_search_request(event: Dict[str, Any], implementation: str) -> Dict[str, Any]:
    """
    Route search request to appropriate Lambda function.
    """
    target_function = NEW_SEARCH_LAMBDA if implementation == "new" else OLD_SEARCH_LAMBDA

    logger.info(f"Routing search request to {target_function} ({implementation} implementation)")

    try:
        # Invoke target Lambda function
        response = lambda_client.invoke(
            FunctionName=target_function, InvocationType="RequestResponse", Payload=json.dumps(event)
        )

        # Parse response
        payload = json.loads(response["Payload"].read())

        # Add implementation info to response for monitoring
        if isinstance(payload.get("body"), str):
            try:
                body = json.loads(payload["body"])
                body["implementation"] = implementation
                payload["body"] = json.dumps(body)
            except:
                pass

        logger.info(f"Search request routed successfully to {implementation} implementation")
        return payload

    except Exception as e:
        logger.error(f"Error routing search request to {target_function}: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to route search request"})}


def update_connection_activity(connection_id: str, increment_result_count: bool = False) -> None:
    """
    Update connection activity timestamp and optionally increment result count.
    Used for connection limit enforcement.
    """
    try:
        current_time = datetime.utcnow().isoformat()

        if increment_result_count:
            # Increment result count and update last activity
            routing_table.update_item(
                Key={"connection_id": connection_id},
                UpdateExpression="SET last_activity = :time, result_count = result_count + :inc",
                ExpressionAttributeValues={":time": current_time, ":inc": 1},
            )
            logger.debug(f"Incremented result count for connection {connection_id}")
        else:
            # Just update last activity
            routing_table.update_item(
                Key={"connection_id": connection_id},
                UpdateExpression="SET last_activity = :time",
                ExpressionAttributeValues={":time": current_time},
            )
            logger.debug(f"Updated activity for connection {connection_id}")

    except Exception as e:
        logger.error(f"Error updating connection activity for {connection_id}: {str(e)}")


def cleanup_expired_routing_records():
    """
    Clean up expired routing records (called periodically).
    Note: TTL should handle this automatically, but this provides manual cleanup if needed.
    """
    try:
        # Scan for expired records
        current_time = datetime.utcnow()

        response = routing_table.scan()
        items = response.get("Items", [])

        deleted_count = 0
        for item in items:
            created_at = datetime.fromisoformat(item["created_at"])
            if (current_time - created_at).total_seconds() > 3600:  # 1 hour
                routing_table.delete_item(Key={"connection_id": item["connection_id"]})
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} expired routing records")

    except Exception as e:
        logger.error(f"Error cleaning up routing records: {str(e)}")
