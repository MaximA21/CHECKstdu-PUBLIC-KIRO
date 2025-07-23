"""Base controller classes for different entry point types."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
import json
import time
from datetime import datetime

from ...application.interfaces.logging import ILogger
from ...shared.exceptions.domain import DomainException
from ...shared.exceptions.infrastructure import InfrastructureException


class BaseController(ABC):
    """Abstract base controller for all presentation layer controllers."""

    def __init__(self, logger: ILogger):
        self._logger = logger

    @abstractmethod
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming request and return response."""
        pass

    def _log_request_start(self, operation: str, context: Dict[str, Any]) -> float:
        """Log request start and return start time."""
        start_time = time.time()
        self._logger.info(f"{operation} started", context)
        return start_time

    def _log_request_success(self, operation: str, context: Dict[str, Any], start_time: float) -> None:
        """Log successful request completion."""
        execution_time = (time.time() - start_time) * 1000
        context.update({"execution_time_ms": round(execution_time, 1), "status": "success"})
        self._logger.info(f"{operation} completed", context)

    def _log_request_error(self, operation: str, context: Dict[str, Any], start_time: float, error: Exception) -> None:
        """Log request error."""
        execution_time = (time.time() - start_time) * 1000
        context.update({"execution_time_ms": round(execution_time, 1), "status": "error", "error": str(error)})
        self._logger.error(f"{operation} failed", context, exception=error)

    def _handle_exception(self, error: Exception) -> Dict[str, Any]:
        """Handle exceptions and return appropriate error response."""
        if isinstance(error, DomainException):
            return self._create_error_response(400, str(error))
        elif isinstance(error, InfrastructureException):
            return self._create_error_response(503, "Service temporarily unavailable")
        else:
            return self._create_error_response(500, "Internal server error")

    @abstractmethod
    def _create_success_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Create success response in the appropriate format."""
        pass

    @abstractmethod
    def _create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create error response in the appropriate format."""
        pass


class HTTPController(BaseController):
    """Base controller for HTTP-based requests (Lambda API Gateway, HTTP servers)."""

    def _create_success_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Create HTTP success response."""
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=300",
            },
            "body": json.dumps(data, separators=(",", ":"), default=self._json_serializer),
        }

    def _create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create HTTP error response."""
        return {
            "statusCode": status_code,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": message}),
        }

    def _extract_path_parameter(self, event: Dict[str, Any], parameter_name: str) -> Optional[str]:
        """Extract path parameter from HTTP event."""
        path_parameters = event.get("pathParameters", {})
        return path_parameters.get(parameter_name) if path_parameters else None

    def _extract_query_parameter(self, event: Dict[str, Any], parameter_name: str) -> Optional[str]:
        """Extract query parameter from HTTP event."""
        query_parameters = event.get("queryStringParameters", {})
        return query_parameters.get(parameter_name) if query_parameters else None

    def _extract_request_body(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract and parse request body from HTTP event."""
        body = event.get("body")
        if not body:
            return None

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime and other objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class WebSocketController(BaseController):
    """Base controller for WebSocket-based requests."""

    def _create_success_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Create WebSocket success response."""
        return {
            "statusCode": status_code,
            "body": json.dumps(
                {"action": "response", "data": data, "timestamp": datetime.utcnow().isoformat()}, default=self._json_serializer
            ),
        }

    def _create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create WebSocket error response."""
        return {
            "statusCode": status_code,
            "body": json.dumps({"action": "error", "error": message, "timestamp": datetime.utcnow().isoformat()}),
        }

    def _extract_connection_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract connection ID from WebSocket event."""
        request_context = event.get("requestContext", {})
        return request_context.get("connectionId")

    def _extract_route_key(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract route key from WebSocket event."""
        request_context = event.get("requestContext", {})
        return request_context.get("routeKey")

    def _extract_message_body(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract and parse message body from WebSocket event."""
        body = event.get("body")
        if not body:
            return None

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime and other objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class ContainerController(BaseController):
    """Base controller for container-based HTTP requests."""

    def _create_success_response(self, data: Any, status_code: int = 200) -> Dict[str, Any]:
        """Create container HTTP success response."""
        return {
            "status_code": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=300",
            },
            "data": data,
        }

    def _create_error_response(self, status_code: int, message: str) -> Dict[str, Any]:
        """Create container HTTP error response."""
        return {
            "status_code": status_code,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "error": message,
        }

    def _extract_path_parameter(self, request_data: Dict[str, Any], parameter_name: str) -> Optional[str]:
        """Extract path parameter from container request."""
        path_params = request_data.get("path_params", {})
        return path_params.get(parameter_name)

    def _extract_query_parameter(self, request_data: Dict[str, Any], parameter_name: str) -> Optional[str]:
        """Extract query parameter from container request."""
        query_params = request_data.get("query_params", {})
        return query_params.get(parameter_name)

    def _extract_request_body(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract request body from container request."""
        return request_data.get("body")
