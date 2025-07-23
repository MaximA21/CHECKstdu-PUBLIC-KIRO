"""Lambda handler for API Gateway authorization using dependency injection."""

import os
from typing import Dict, Any, Optional

from ..controllers.base_controller import BaseController
from ...application.use_cases.authorization_use_case import AuthorizationUseCase
from ...application.interfaces.logging import ILogger
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import DomainException


class AuthorizerHandler(BaseController):
    """Lambda handler for API Gateway authorization."""
    
    def __init__(
        self,
        authorization_use_case: AuthorizationUseCase,
        logger: ILogger
    ):
        super().__init__(logger)
        self._authorization_use_case = authorization_use_case
    
    async def handle_request(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle authorization request."""
        start_time = self._log_request_start("Authorization", {})
        
        try:
            # Extract query parameters
            query_params = event.get('queryStringParameters', {}) or {}
            
            if not query_params:
                self._logger.warning("No query parameters found")
                return await self._authorization_use_case.authorize_request(
                    token="",
                    method_arn=event['methodArn']
                )
            
            # Extract token
            token = query_params.get('token', '')
            
            self._logger.debug("Authorization request received", {
                "has_token": bool(token),
                "token_length": len(token) if token else 0
            })
            
            # Extract address data if present
            address = None
            if all(key in query_params for key in ['street', 'houseNumber', 'city', 'postalCode']):
                try:
                    address = Address(
                        street=query_params['street'],
                        house_number=query_params['houseNumber'],
                        city=query_params['city'],
                        postal_code=query_params['postalCode'],
                        country='DE'
                    )
                    
                    self._logger.debug("Address extracted for validation", {
                        "address": address.full_address
                    })
                    
                except Exception as e:
                    self._logger.warning("Failed to create address from query parameters", {
                        "error": str(e)
                    })
            
            # Execute authorization use case
            result = await self._authorization_use_case.authorize_request(
                token=token,
                method_arn=event['methodArn'],
                address=address
            )
            
            # Log success
            effect = result.get('policyDocument', {}).get('Statement', [{}])[0].get('Effect', 'Unknown')
            self._log_request_success("Authorization", {
                "effect": effect,
                "has_address": address is not None
            }, start_time)
            
            return result
            
        except DomainException as e:
            self._log_request_error("Authorization", {}, start_time, e)
            # Return deny policy on domain errors
            return await self._authorization_use_case.authorize_request(
                token="",
                method_arn=event.get('methodArn', '*')
            )
            
        except Exception as e:
            self._log_request_error("Authorization", {}, start_time, e)
            # Return deny policy on unexpected errors
            return {
                'principalId': 'user',
                'policyDocument': {
                    'Version': '2012-10-17',
                    'Statement': [{
                        'Action': 'execute-api:Invoke',
                        'Effect': 'Deny',
                        'Resource': event.get('methodArn', '*')
                    }]
                },
                'context': {
                    'message': 'Internal error'
                }
            }


# Lambda entry point function
def lambda_handler(event, context):
    """Lambda entry point for API Gateway authorization."""
    from ...shared.dependency_injection.bootstrap import get_container
    
    # Get DI container
    container = get_container()
    
    # Get Google Maps API key from environment
    google_maps_api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
    
    # Create authorization use case with API key
    authorization_use_case = AuthorizationUseCase(
        logger=container.get_logger("authorization_use_case"),
        google_maps_api_key=google_maps_api_key
    )
    
    # Create handler with dependencies
    handler = AuthorizerHandler(
        authorization_use_case=authorization_use_case,
        logger=container.get_logger("authorizer")
    )
    
    # Handle request
    import asyncio
    return asyncio.run(handler.handle_request(event))