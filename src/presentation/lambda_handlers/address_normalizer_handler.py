"""Lambda handler for address normalization using dependency injection."""

import time
from typing import Any, Dict

from ...application.interfaces.logging import ILogger
from ...application.use_cases.address_normalization_use_case import AddressNormalizationUseCase
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import DomainException
from ..controllers.base_controller import BaseController


class AddressNormalizerHandler(BaseController):
    """Lambda handler for address normalization."""

    def __init__(self, address_normalization_use_case: AddressNormalizationUseCase, logger: ILogger):
        super().__init__(logger)
        self._address_normalization_use_case = address_normalization_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle address normalization request."""
        start_time = time.time()

        try:
            self._logger.info("Address normalizer started")
            self._logger.debug("Input event received", {"event": event})

            # Extract address data
            address_data = event.get("address", {})
            if not address_data:
                self._logger.error("No address data found in event")
                # Return original event with error to avoid breaking workflow
                return {
                    **event,
                    "normalized_address": {},
                    "connection_types": ["FIBER", "DSL", "CABLE"],
                    "normalization_error": "No address data provided",
                }

            # Create address value object
            try:
                address = Address(
                    street=address_data.get("street", ""),
                    house_number=address_data.get("house_number", ""),
                    city=address_data.get("city", ""),
                    postal_code=address_data.get("postal_code", ""),
                    country=address_data.get("country", "DE"),
                )
            except Exception as e:
                self._logger.error("Failed to create address object", {"address_data": address_data, "error": str(e)})
                # Return original event with error
                return {
                    **event,
                    "normalized_address": address_data,
                    "connection_types": ["FIBER", "DSL", "CABLE"],
                    "normalization_error": f"Invalid address data: {str(e)}",
                }

            # Execute normalization use case
            result = await self._address_normalization_use_case.normalize_for_webwunder(address)

            # Merge with original event data
            response = {**event, **result}  # Preserve all original data  # Add normalization results

            # Calculate and log performance timing
            processing_time = (time.time() - start_time) * 1000
            self._logger.info(
                "Address normalization completed successfully",
                {
                    "processing_time_ms": round(processing_time, 1),
                    "normalization_applied": result.get("normalization_applied", False),
                },
            )

            return response

        except DomainException as e:
            processing_time = (time.time() - start_time) * 1000
            self._logger.error(
                "Address normalization failed", {"processing_time_ms": round(processing_time, 1), "error": str(e)}, exception=e
            )

            # Return original event with error to avoid breaking workflow
            return {
                **(event or {}),
                "normalized_address": (event or {}).get("address", {}) if event else {},
                "connection_types": ["FIBER", "DSL", "CABLE"],
                "normalization_error": str(e),
            }

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._logger.error(
                "Unexpected error in address normalizer",
                {"processing_time_ms": round(processing_time, 1), "error": str(e)},
                exception=e,
            )

            # Return original event with error to avoid breaking workflow
            return {
                **(event or {}),
                "normalized_address": (event or {}).get("address", {}) if event else {},
                "connection_types": ["FIBER", "DSL", "CABLE"],
                "normalization_error": f"Unexpected error: {str(e)}",
            }


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for address normalization."""
    import asyncio

    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = AddressNormalizerHandler(
        address_normalization_use_case=container.get(AddressNormalizationUseCase),
        logger=container.get_logger("address_normalizer"),
    )

    # Handle request - check if event loop is already running
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context (like tests), create a task
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, handler.handle_request(event))
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        return asyncio.run(handler.handle_request(event))
