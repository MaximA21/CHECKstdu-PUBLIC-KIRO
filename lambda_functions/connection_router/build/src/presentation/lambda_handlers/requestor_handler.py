"""Lambda handler for requestor using dependency injection."""

from typing import Dict, Any

from ..controllers.base_controller import HTTPController
from ...application.use_cases.requestor_use_case import RequestorUseCase
from ...application.interfaces.logging import ILogger
from ...shared.exceptions.domain import DomainException


class RequestorHandler(HTTPController):
    """Lambda handler for processing search requests and starting workflows."""
    
    def __init__(
        self,
        requestor_use_case: RequestorUseCase,
        logger: ILogger
    ):
        super().__init__(logger)
        self._requestor_use_case = requestor_use_case
    
    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle requestor request."""
        start_time = self._log_request_start("Requestor", {})
        
        try:
            # Extract request data from SQS message body
            request_body = self._extract_request_body(event)
            if not request_body:
                return self._create_error_response(400, "Request body required")
            
            # Execute requestor use case
            execution_id = await self._requestor_use_case.execute(request_body)
            
            # Log success
            self._log_request_success("Requestor", {
                "request_id": request_body.get("request_id"),
                "execution_id": execution_id
            }, start_time)
            
            return self._create_success_response({
                "execution_id": execution_id,
                "message": "Workflow started successfully"
            })
            
        except DomainException as e:
            self._log_request_error("Requestor", {}, start_time, e)
            return self._create_error_response(400, str(e))
            
        except Exception as e:
            self._log_request_error("Requestor", {}, start_time, e)
            return self._handle_exception(e)


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for requestor handler."""
    from ...shared.dependency_injection.bootstrap import get_container
    
    # Get DI container
    container = get_container()
    
    # Create handler with dependencies
    handler = RequestorHandler(
        requestor_use_case=container.get(RequestorUseCase),
        logger=container.get_logger("requestor_handler")
    )
    
    # Handle request
    import asyncio
    return asyncio.run(handler.handle_request(event))