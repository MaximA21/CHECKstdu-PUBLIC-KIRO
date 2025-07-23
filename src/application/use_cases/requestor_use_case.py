"""Use case for handling search requests and starting workflows."""

from typing import Dict, Any
from datetime import datetime

from ..interfaces.messaging import IWorkflowOrchestrator
from ..interfaces.logging import ILogger
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import DomainException


class RequestorUseCase:
    """Use case for processing search requests and starting provider workflows."""

    def __init__(self, workflow_orchestrator: IWorkflowOrchestrator, logger: ILogger):
        self._workflow_orchestrator = workflow_orchestrator
        self._logger = logger

    async def execute(self, request_data: Dict[str, Any]) -> str:
        """
        Execute search request by starting provider workflow.

        Args:
            request_data: Search request data containing request_id, address, etc.

        Returns:
            str: Workflow execution ID
        """
        request_id = request_data.get("request_id")

        try:
            self._logger.info(f"Processing search request: {request_id}")

            # Validate required fields
            if not request_id:
                raise DomainException("Request ID is required")

            address_data = request_data.get("address")
            if not address_data:
                raise DomainException("Address data is required")

            # Validate address
            address = Address(
                street=address_data.get("street", ""),
                house_number=address_data.get("house_number", ""),
                city=address_data.get("city", ""),
                postal_code=address_data.get("postal_code", ""),
                country=address_data.get("country", "DE"),
            )

            # Prepare workflow input
            workflow_input = {
                "request_id": request_id,
                "connection_id": request_data.get("connection_id"),
                "address": {
                    "street": address.street,
                    "house_number": address.house_number,
                    "city": address.city,
                    "postal_code": address.postal_code,
                    "country": address.country,
                },
                "share_token": request_data.get("share_token"),
                "timestamp": request_data.get("timestamp", datetime.utcnow().isoformat()),
            }

            # Start workflow execution
            execution_name = f"req-{request_id}"
            if len(execution_name) > 80:  # Step Functions name limit
                execution_name = execution_name[:80]

            execution_id = await self._workflow_orchestrator.start_workflow(
                workflow_name="provider-search-workflow", input_data=workflow_input, execution_name=execution_name
            )

            self._logger.info(f"Started workflow execution: {execution_id} for request: {request_id}")

            return execution_id

        except DomainException:
            raise
        except Exception as e:
            self._logger.error(f"Failed to process search request {request_id}: {str(e)}")
            raise DomainException(f"Failed to process search request: {str(e)}")
