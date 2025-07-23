"""Lambda handler for WebSocket disconnections using dependency injection."""

from typing import Dict, Any

from ..controllers.base_controller import WebSocketController
from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from ...application.interfaces.logging import ILogger
from ...shared.exceptions.domain import DomainException


class DisconnectHandler(WebSocketController):
    """Lambda handler for WebSocket disconnection."""
    
    def __init__(
        self,
        connection_management_use_case: ConnectionManagementUseCase,
        logger: ILogger
    ):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case
    
    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebSocket disconnection request."""
        start_time = self._log_request_start("WebSocket Disconnect", {})
        
        try:
            # Extract connection ID
            connection_id = self._extract_connection_id(event)
            if not connection_id:
                self._logger.error("No connection ID found in event")
                return self._create_error_response(400, "Connection ID missing")
            
            # Check connection status before disconnecting
            connection_status = await self._connection_management_use_case.get_connection_status(connection_id)
            
            # Determine disconnect reason
            disconnect_reason = "Client disconnected"
            if connection_status.get("should_disconnect_due_to_limits", False):
                disconnect_reason = f"Limit enforcement: {connection_status.get('disconnect_reason', 'Unknown limit')}"
            
            # Execute disconnection use case
            result = await self._connection_management_use_case.handle_disconnect(
                connection_id=connection_id,
                reason=disconnect_reason
            )
            
            # Add connection statistics to result
            if connection_status.get("status") != "not_found":
                result["connection_statistics"] = {
                    "result_count": connection_status.get("result_count", 0),
                    "max_results": connection_status.get("max_results", 5),
                    "connection_duration_minutes": connection_status.get("connection_duration_minutes", 0),
                    "max_connection_minutes": connection_status.get("max_connection_minutes", 2),
                    "was_limit_enforced": connection_status.get("should_disconnect_due_to_limits", False)
                }
            
            # Log success
            self._log_request_success("WebSocket Disconnect", {
                "connection_id": connection_id,
                "duration_seconds": result.get("duration_seconds", 0)
            }, start_time)
            
            return self._create_success_response({
                "message": "Getrennt",
                "connection_id": connection_id,
                "status": result["status"]
            })
            
        except DomainException as e:
            self._log_request_error("WebSocket Disconnect", {
                "connection_id": connection_id if 'connection_id' in locals() else 'unknown'
            }, start_time, e)
            return self._create_error_response(400, str(e))
            
        except Exception as e:
            self._log_request_error("WebSocket Disconnect", {
                "connection_id": connection_id if 'connection_id' in locals() else 'unknown'
            }, start_time, e)
            return self._handle_exception(e)


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for WebSocket disconnections."""
    from ...shared.dependency_injection.bootstrap import get_container
    
    # Get DI container
    container = get_container()
    
    # Create handler with dependencies
    handler = DisconnectHandler(
        connection_management_use_case=container.get(ConnectionManagementUseCase),
        logger=container.get_logger("disconnect_handler")
    )
    
    # Handle request
    import asyncio
    return asyncio.run(handler.handle_request(event))