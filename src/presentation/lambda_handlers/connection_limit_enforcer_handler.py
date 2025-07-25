"""Lambda handler for enforcing WebSocket connection limits."""

from typing import Any, Dict

from ...application.interfaces.logging import ILogger
from ...application.use_cases.connection_management_use_case import ConnectionManagementUseCase
from ...shared.exceptions.domain import DomainException
from ..controllers.base_controller import HTTPController


class ConnectionLimitEnforcerHandler(HTTPController):
    """Lambda handler for enforcing WebSocket connection limits."""

    def __init__(self, connection_management_use_case: ConnectionManagementUseCase, logger: ILogger):
        super().__init__(logger)
        self._connection_management_use_case = connection_management_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle connection limit enforcement request."""
        start_time = self._log_request_start("Connection Limit Enforcement", {})

        try:
            # Check if this is a scheduled CloudWatch event
            source = event.get("source")
            if source == "aws.events":
                self._logger.info("Processing scheduled connection limit enforcement")
            else:
                self._logger.info("Processing manual connection limit enforcement")

            # Execute connection limit enforcement
            result = await self._connection_management_use_case.enforce_connection_limits_for_all()

            # Log success
            self._log_request_success(
                "Connection Limit Enforcement",
                {
                    "connections_checked": result.get("connections_checked", 0),
                    "connections_disconnected": result.get("connections_disconnected", 0),
                    "errors": result.get("errors", 0),
                },
                start_time,
            )

            return self._create_success_response({"message": "Connection limit enforcement completed", "statistics": result})

        except DomainException as e:
            self._log_request_error("Connection Limit Enforcement", {}, start_time, e)
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error("Connection Limit Enforcement", {}, start_time, e)
            return self._handle_exception(e)


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for connection limit enforcement."""
    import asyncio

    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = ConnectionLimitEnforcerHandler(
        connection_management_use_case=container.get(ConnectionManagementUseCase),
        logger=container.get_logger("connection_limit_enforcer"),
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
