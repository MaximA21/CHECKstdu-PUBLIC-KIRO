"""Lambda handler for WebSocket connections using dependency injection."""

from typing import Dict, Any

from ..controllers.base_controller import WebSocketController
from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from ...application.interfaces.logging import ILogger
from ...domain.entities.connection_session import SessionConnectionType
from ...shared.exceptions.domain import DomainException


class ConnectHandler(WebSocketController):
    """Lambda handler for WebSocket connection establishment."""
    
    def __init__(
        self,
        connection_management_use_case: ConnectionManagementUseCase,
        logger: ILogger
    ):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case
    
    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebSocket connection request."""
        start_time = self._log_request_start("WebSocket Connect", {})
        
        try:
            # Extract connection ID
            connection_id = self._extract_connection_id(event)
            if not connection_id:
                self._logger.error("No connection ID found in event")
                return self._create_error_response(400, "Connection ID missing")
            
            # Extract query parameters for connection metadata
            query_params = event.get("queryStringParameters", {}) or {}
            
            # Extract address components if provided
            client_info = {}
            if query_params:
                address_components = {}
                for key in ['street', 'houseNumber', 'city', 'postalCode']:
                    if key in query_params:
                        address_components[key] = query_params[key]
                
                if address_components:
                    client_info['address_components'] = address_components
                
                # Log address components for debugging
                if address_components:
                    self._logger.debug("Address components received", {
                        "connection_id": connection_id,
                        "address_components": address_components
                    })
            
            # Execute connection use case
            result = await self._connection_management_use_case.handle_connect(
                connection_id=connection_id,
                connection_type=SessionConnectionType.WEBSOCKET,
                client_info=client_info if client_info else None
            )
            
            # Log success
            self._log_request_success("WebSocket Connect", {
                "connection_id": connection_id,
                "has_address_info": bool(client_info)
            }, start_time)
            
            return self._create_success_response({
                "message": "Verbunden",
                "connection_id": connection_id,
                "status": result["status"]
            })
            
        except DomainException as e:
            self._log_request_error("WebSocket Connect", {
                "connection_id": connection_id if 'connection_id' in locals() else 'unknown'
            }, start_time, e)
            return self._create_error_response(400, str(e))
            
        except Exception as e:
            self._log_request_error("WebSocket Connect", {
                "connection_id": connection_id if 'connection_id' in locals() else 'unknown'
            }, start_time, e)
            return self._handle_exception(e)


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for WebSocket connections."""
    from ...shared.dependency_injection.bootstrap import get_container
    
    # Get DI container
    container = get_container()
    
    # Create handler with dependencies
    handler = ConnectHandler(
        connection_management_use_case=container.get(ConnectionManagementUseCase),
        logger=container.get_logger("connect_handler")
    )
    
    # Handle request
    import asyncio
    return asyncio.run(handler.handle_request(event))