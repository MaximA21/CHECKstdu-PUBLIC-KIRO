"""Authorization use case for API Gateway authorization."""

from typing import Dict, Any, Optional
import urllib.request
import urllib.parse
import json

from ..interfaces.logging import ILogger
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import AuthorizationException, DomainException


class AuthorizationUseCase:
    """Use case for handling API Gateway authorization."""

    def __init__(self, logger: ILogger, google_maps_api_key: Optional[str] = None):
        self._logger = logger
        self._google_maps_api_key = google_maps_api_key

    async def authorize_request(self, token: str, method_arn: str, address: Optional[Address] = None) -> Dict[str, Any]:
        """
        Authorize API Gateway request.

        Args:
            token: Authorization token
            method_arn: API Gateway method ARN
            address: Optional address to validate

        Returns:
            Dict containing authorization policy

        Raises:
            AuthorizationException: If authorization fails
        """
        try:
            self._logger.info(
                "Processing authorization request",
                {"token_length": len(token) if token else 0, "has_address": address is not None},
            )

            # Basic token validation
            if not token:
                self._logger.info("Authorization denied: No token provided")
                return self._generate_policy("Deny", method_arn, "Token required")

            # If address is provided, validate it
            if address:
                self._logger.debug("Validating address", {"address": address.full_address})

                if not await self._validate_address(address):
                    self._logger.info("Authorization denied: Invalid address", {"address": address.full_address})
                    return self._generate_policy("Deny", method_arn, "Invalid address")

                self._logger.info("Address validation successful")

            # Token is valid, grant access
            self._logger.info("Authorization granted")
            return self._generate_policy("Allow", method_arn)

        except Exception as e:
            self._logger.error("Authorization error", {"error": str(e)}, exception=e)
            raise AuthorizationException(f"Authorization failed: {str(e)}")

    async def _validate_address(self, address: Address) -> bool:
        """
        Validate address using Google Maps Geocoding API.

        Args:
            address: Address to validate

        Returns:
            True if address is valid, False otherwise
        """
        if not self._google_maps_api_key:
            self._logger.warning("Google Maps API key not configured, skipping address validation")
            return True  # Allow request to proceed for better user experience

        try:
            # Format address for Google Maps API
            formatted_address = (
                f"{address.street} {address.house_number}, {address.postal_code} {address.city}, {address.country}"
            )

            # Prepare API request
            endpoint = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": formatted_address, "key": self._google_maps_api_key}
            url = f"{endpoint}?{urllib.parse.urlencode(params)}"

            self._logger.debug("Sending address validation request to Google Maps API")

            # Send request
            with urllib.request.urlopen(url) as response:
                result = json.loads(response.read().decode())

            # Evaluate result
            status = result.get("status")
            results_count = len(result.get("results", []))

            self._logger.debug("Google Maps API response", {"status": status, "results_count": results_count})

            if status == "OK" and results_count > 0:
                self._logger.info("Address validation successful")
                return True
            else:
                self._logger.info("Address validation failed", {"status": status, "results_count": results_count})
                return False

        except Exception as e:
            self._logger.error("Address validation error", {"address": address.full_address, "error": str(e)}, exception=e)
            # Return True on error to avoid blocking users due to API issues
            return True

    def _generate_policy(self, effect: str, resource: str, message: str = "") -> Dict[str, Any]:
        """
        Generate IAM policy for API Gateway authorization.

        Args:
            effect: "Allow" or "Deny"
            resource: API Gateway resource ARN
            message: Optional message for context

        Returns:
            IAM policy document
        """
        return {
            "principalId": "user",  # Could be a user ID in real implementation
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [{"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}],
            },
            "context": {"message": message},
        }
