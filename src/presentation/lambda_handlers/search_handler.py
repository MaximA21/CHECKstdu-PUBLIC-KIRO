"""Lambda handler for search requests using dependency injection."""

from typing import Dict, Any

from ..controllers.base_controller import HTTPController
from ...application.use_cases.search_offers_use_case import SearchOffersUseCase
from ...application.interfaces.logging import ILogger
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import DomainException


class SearchHandler(HTTPController):
    """Lambda handler for search offers requests."""

    def __init__(self, search_offers_use_case: SearchOffersUseCase, logger: ILogger):
        super().__init__(logger)
        self._search_offers_use_case = search_offers_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search offers request."""
        start_time = self._log_request_start("Search Offers", {})

        try:
            # Extract request body
            request_body = self._extract_request_body(event)
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
                country=address_data.get("country", "DE"),
            )

            # Extract connection ID for WebSocket notifications
            connection_id = request_body.get("connection_id")

            # Execute search use case
            result = await self._search_offers_use_case.execute(address, connection_id)

            # Log success
            self._log_request_success(
                "Search Offers",
                {"request_id": result.get("request_id"), "address": address.full_address, "connection_id": connection_id},
                start_time,
            )

            return self._create_success_response(result)

        except DomainException as e:
            self._log_request_error("Search Offers", {}, start_time, e)
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error("Search Offers", {}, start_time, e)
            return self._handle_exception(e)


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for search offers."""
    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = SearchHandler(
        search_offers_use_case=container.get(SearchOffersUseCase), logger=container.get_logger("search_handler")
    )

    # Handle request
    import asyncio

    return asyncio.run(handler.handle_request(event))
