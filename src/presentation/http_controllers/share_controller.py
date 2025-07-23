"""HTTP controllers for container deployment scenarios."""

from typing import Any, Dict

from ...application.interfaces.logging import ILogger
from ...application.use_cases.share_results_use_case import ShareResultsUseCase
from ...shared.exceptions.domain import ShareResultsException, ShareTokenNotFoundException
from ..controllers.base_controller import ContainerController


class ShareController(ContainerController):
    """HTTP controller for sharing search results in container deployment."""

    def __init__(self, share_results_use_case: ShareResultsUseCase, logger: ILogger):
        super().__init__(logger)
        self._share_results_use_case = share_results_use_case

    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle share API request."""
        start_time = self._log_request_start("Share API", {})

        try:
            # Extract share token from path parameters
            share_token = self._extract_path_parameter(request_data, "share_token")

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

    async def get_statistics(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle share statistics request."""
        start_time = self._log_request_start("Share Stats", {})

        try:
            # Extract share token from path parameters
            share_token = self._extract_path_parameter(request_data, "share_token")

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

    async def extend_expiration(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle share expiration extension request."""
        start_time = self._log_request_start("Extend Share", {})

        try:
            # Extract share token from path parameters
            share_token = self._extract_path_parameter(request_data, "share_token")

            if not share_token:
                return self._create_error_response(400, "Share token required")

            # Extract extension days from request body
            request_body = self._extract_request_body(request_data)
            if not request_body:
                return self._create_error_response(400, "Request body required")

            days = request_body.get("days")
            if not days or not isinstance(days, int):
                return self._create_error_response(400, "Extension days (integer) required")

            # Extend expiration
            result = await self._share_results_use_case.extend_share_expiration(share_token, days)

            # Log success
            self._log_request_success("Extend Share", {"share_token": share_token, "days_extended": days}, start_time)

            return self._create_success_response(result)

        except ShareTokenNotFoundException as e:
            self._log_request_error(
                "Extend Share", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._create_error_response(404, "Share link not found or expired")

        except ShareResultsException as e:
            self._log_request_error(
                "Extend Share", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._create_error_response(400, str(e))

        except Exception as e:
            self._log_request_error(
                "Extend Share", {"share_token": share_token if "share_token" in locals() else "unknown"}, start_time, e
            )
            return self._handle_exception(e)
