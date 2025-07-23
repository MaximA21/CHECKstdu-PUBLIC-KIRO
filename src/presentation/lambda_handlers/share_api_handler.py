"""Lambda handler for share API using dependency injection."""

from typing import Any, Dict

from ...application.interfaces.logging import ILogger
from ...application.use_cases.share_results_use_case import ShareResultsUseCase
from ...shared.exceptions.domain import ShareResultsException, ShareTokenNotFoundException
from ..controllers.base_controller import HTTPController


class ShareApiHandler(HTTPController):
    """Lambda handler for sharing search results."""

    def __init__(self, share_results_use_case: ShareResultsUseCase, logger: ILogger):
        super().__init__(logger)
        self._share_results_use_case = share_results_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle share API request."""
        start_time = self._log_request_start("Share API", {})

        try:
            # Extract share token from path parameters
            share_token = self._extract_path_parameter(event, "share_token")

            if not share_token:
                self._logger.info("Share API request failed: Share token required")
                return self._create_error_response(400, "Share token required")

            # Execute use case
            result = await self._share_results_use_case.execute(share_token)

            # Log success
            self._log_request_success(
                "Share API", {"share_token": share_token, "total_offers": result.get("total_offers", 0)}, start_time
            )

            return self._create_success_response(result)

        except ShareTokenNotFoundException as e:
            self._log_request_error(
                "Share API", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._create_error_response(404, "Share link not found or expired")

        except ShareResultsException as e:
            self._log_request_error(
                "Share API", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error(
                "Share API", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._handle_exception(e)


class ShareStatsHandler(HTTPController):
    """Lambda handler for share statistics."""

    def __init__(self, share_results_use_case: ShareResultsUseCase, logger: ILogger):
        super().__init__(logger)
        self._share_results_use_case = share_results_use_case

    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle share statistics request."""
        start_time = self._log_request_start("Share Stats", {})

        try:
            # Extract share token from path parameters
            share_token = self._extract_path_parameter(event, "share_token")

            if not share_token:
                return self._create_error_response(400, "Share token required")

            # Get statistics
            stats = await self._share_results_use_case.get_share_statistics(share_token)

            # Log success
            self._log_request_success("Share Stats", {"share_token": share_token}, start_time)

            return self._create_success_response(stats)

        except ShareTokenNotFoundException as e:
            self._log_request_error(
                "Share Stats", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._create_error_response(404, "Share link not found or expired")

        except Exception as e:
            self._log_request_error(
                "Share Stats", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._handle_exception(e)


# Lambda entry point functions
def lambda_handler(event, context):
    """Main Lambda entry point for share API."""
    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = ShareApiHandler(
        share_results_use_case=container.get(ShareResultsUseCase), logger=container.get_logger("share_api")
    )

    # Handle request
    import asyncio

    return asyncio.run(handler.handle_request(event))


def stats_lambda_handler(event, context):
    """Lambda entry point for share statistics."""
    from ...shared.dependency_injection.bootstrap import get_container

    # Get DI container
    container = get_container()

    # Create handler with dependencies
    handler = ShareStatsHandler(
        share_results_use_case=container.get(ShareResultsUseCase), logger=container.get_logger("share_stats")
    )

    # Handle request
    import asyncio

    return asyncio.run(handler.handle_request(event))
