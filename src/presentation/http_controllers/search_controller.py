"""HTTP controller for search operations in container deployment."""

from typing import Dict, Any

from ..controllers.base_controller import ContainerController
from ...application.use_cases.search_offers_use_case import SearchOffersUseCase
from ...application.interfaces.logging import ILogger
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import DomainException


class SearchController(ContainerController):
    """HTTP controller for search offers in container deployment."""
    
    def __init__(
        self,
        search_offers_use_case: SearchOffersUseCase,
        logger: ILogger
    ):
        super().__init__(logger)
        self._search_offers_use_case = search_offers_use_case
    
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search offers request."""
        start_time = self._log_request_start("Search Offers", {})
        
        try:
            # Extract request body
            request_body = self._extract_request_body(request_data)
            if not request_body:
                return self._create_error_response(400, "Request body required")
            
            # Extract address information
            address_data = request_body.get("address")
            if not address_data:
                return self._create_error_response(400, "Address information required")
            
            # Create address value object
            address = Address(
                street=address_data.get("street", ""),
                house_number=address_data.get("house_number", ""),
                city=address_data.get("city", ""),
                postal_code=address_data.get("postal_code", ""),
                country=address_data.get("country", "DE")
            )
            
            # Extract connection ID for WebSocket notifications (optional in container deployment)
            connection_id = request_body.get("connection_id")
            
            # Execute search use case
            result = await self._search_offers_use_case.execute(address, connection_id)
            
            # Log success
            self._log_request_success("Search Offers", {
                "request_id": result.get("request_id"),
                "address": address.full_address,
                "connection_id": connection_id
            }, start_time)
            
            return self._create_success_response(result)
            
        except DomainException as e:
            self._log_request_error("Search Offers", {}, start_time, e)
            return self._create_error_response(400, str(e))
            
        except Exception as e:
            self._log_request_error("Search Offers", {}, start_time, e)
            return self._handle_exception(e)
    
    async def get_search_status(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search status request."""
        start_time = self._log_request_start("Search Status", {})
        
        try:
            # Extract request ID from path parameters
            request_id = self._extract_path_parameter(request_data, "request_id")
            
            if not request_id:
                return self._create_error_response(400, "Request ID required")
            
            # Get search status (this would need to be implemented in the use case)
            # For now, return a placeholder response
            result = {
                "request_id": request_id,
                "status": "processing",
                "message": "Search status endpoint not yet implemented"
            }
            
            # Log success
            self._log_request_success("Search Status", {
                "request_id": request_id
            }, start_time)
            
            return self._create_success_response(result)
            
        except Exception as e:
            self._log_request_error("Search Status", {
                "request_id": request_id if 'request_id' in locals() else 'unknown'
            }, start_time, e)
            return self._handle_exception(e)