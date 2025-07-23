"""Lambda handler for processing results using dependency injection."""

from typing import Dict, Any

from ..controllers.base_controller import HTTPController
from ...application.use_cases.process_results_use_case import ProcessResultsUseCase
from ...application.interfaces.logging import ILogger
from ...shared.exceptions.domain import DomainException


class ResultsHandler(HTTPController):
    """Lambda handler for processing search results."""
    
    def __init__(
        self,
        process_results_use_case: ProcessResultsUseCase,
        logger: ILogger
    ):
        super().__init__(logger)
        self._process_results_use_case = process_results_use_case
    
    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle results processing request."""
        start_time = self._log_request_start("Process Results", {})
        
        try:
            # Extract request data
            request_body = self._extract_request_body(event)
            if not request_body:
                return self._create_error_response(400, "Request body required")
            
            # Extract required fields
            request_id = request_body.get("request_id")
            provider_name = request_body.get("provider_name")
            raw_results = request_body.get("results")
            
            if not all([request_id, provider_name, raw_results]):
                return self._create_error_response(400, "request_id, provider_name, and results are required")
            
            # Extract optional fields
            connection_id = request_body.get("connection_id")
            share_token = request_body.get("share_token")
            address_data = request_body.get("address_data")
            metadata = request_body.get("metadata")
            
            # Execute processing use case
            result = await self._process_results_use_case.execute(
                request_id=request_id,
                provider_name=provider_name,
                raw_results=raw_results,
                connection_id=connection_id,
                share_token=share_token,
                address_data=address_data,
                metadata=metadata
            )
            
            # Log success
            self._log_request_success("Process Results", {
                "request_id": request_id,
                "provider_name": provider_name,
                "offers_processed": result.get("offers_processed", 0)
            }, start_time)
            
            return self._create_success_response(result)
            
        except DomainException as e:
            self._log_request_error("Process Results", {}, start_time, e)
            return self._create_error_response(400, str(e))
            
        except Exception as e:
            self._log_request_error("Process Results", {}, start_time, e)
            return self._handle_exception(e)


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for results processing."""
    from ...shared.dependency_injection.bootstrap import get_container
    from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
    
    # Get DI container
    container = get_container()
    
    # Get process results use case and inject connection management
    process_results_use_case = container.get(ProcessResultsUseCase)
    connection_management_use_case = container.get(ConnectionManagementUseCase)
    
    # Inject connection management use case
    process_results_use_case._connection_management_use_case = connection_management_use_case
    
    # Create handler with dependencies
    handler = ResultsHandler(
        process_results_use_case=process_results_use_case,
        logger=container.get_logger("results_handler")
    )
    
    # Handle request
    import asyncio
    return asyncio.run(handler.handle_request(event))