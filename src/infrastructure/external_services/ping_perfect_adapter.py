"""PingPerfect provider service adapter implementation."""

import hashlib
import hmac
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ...application.interfaces.providers import IPingPerfect, ProviderStatus, ProviderType
from ...domain.entities.provider_offer import ConnectionType, OfferStatus, ProviderOffer
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import InvalidAddressException, ProviderUnavailableException


class PingPerfectAdapter(IPingPerfect):
    """PingPerfect provider service adapter with signed request capabilities."""

    def __init__(
        self, api_key: Optional[str] = None, secret_key: Optional[str] = None, logger: Optional[logging.Logger] = None
    ):
        """Initialize PingPerfect adapter."""
        self._logger = logger or logging.getLogger(__name__)
        self._api_key = api_key or "mock_api_key"
        self._secret_key = secret_key or "mock_secret_key"
        self._supported_regions = ["DE", "AT", "CH"]
        self._status = ProviderStatus.AVAILABLE
        self._rate_limit_remaining = 1000
        self._call_count = 0
        self._call_types = ["fiber", "non_fiber"]  # Supported call types

    async def get_offers(self, address: Address) -> List[ProviderOffer]:
        """Get internet offers for a specific address."""
        if not await self.validate_address(address):
            raise InvalidAddressException(f"Address not supported by PingPerfect: {address.full_address}")

        if self._status != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableException(f"PingPerfect provider is {self._status.value}")

        try:
            # Get signed offers for the address
            offers = await self.get_signed_offers(address)

            self._call_count += 1
            self._rate_limit_remaining -= 1

            self._logger.info(f"PingPerfect: Retrieved {len(offers)} offers for {address.full_address}")
            return offers

        except Exception as e:
            self._logger.error(f"PingPerfect: Failed to get offers for {address.full_address}: {e}")
            raise ProviderUnavailableException(f"PingPerfect service error: {str(e)}")

    async def get_signed_offers(self, address: Address) -> List[ProviderOffer]:
        """Get offers using signed requests."""
        try:
            # Get aggregated response from fiber and non-fiber calls
            aggregated_response = await self._get_aggregated_response(address)

            # Parse the aggregated response
            all_offers = await self._parse_aggregated_response(aggregated_response)

            # Add signature metadata to offers
            for offer in all_offers:
                request_data = {
                    "address": address.full_address,
                    "timestamp": datetime.utcnow().isoformat(),
                    "product_id": offer.product_id,
                }
                signature = await self.sign_request(request_data)
                offer.add_feature("request_signature", signature)
                offer.add_feature("verified", True)
                offer.add_feature("api_key", self._api_key)

            return all_offers

        except Exception as e:
            self._logger.error(f"PingPerfect: Failed to get signed offers: {e}")
            return []

    async def sign_request(self, request_data: Dict[str, Any]) -> str:
        """Sign a request for PingPerfect API."""
        try:
            # Create a canonical string from request data
            canonical_string = self._create_canonical_string(request_data)

            # Create HMAC signature
            signature = hmac.new(
                self._secret_key.encode("utf-8"), canonical_string.encode("utf-8"), hashlib.sha256
            ).hexdigest()

            self._logger.debug(f"Generated signature for request: {signature[:8]}...")
            return signature

        except Exception as e:
            self._logger.error(f"Failed to sign request: {e}")
            return "invalid_signature"

    async def _get_aggregated_response(self, address: Address) -> List[Dict[str, Any]]:
        """Get aggregated response from fiber and non-fiber calls."""
        # In a real implementation, this would make multiple API requests
        # For now, we'll simulate the response structure
        self._logger.debug(f"Getting aggregated response for address: {address.full_address}")

        # Mock aggregated response for demonstration
        return [
            {"call_type": "fiber", "wants_fiber": True, "offers": self._get_mock_offers_data("fiber")},
            {"call_type": "non_fiber", "wants_fiber": False, "offers": self._get_mock_offers_data("non_fiber")},
        ]

    async def _parse_aggregated_response(self, aggregated_response: List[Dict]) -> List[ProviderOffer]:
        """Parse PingPerfect aggregated response from fiber and non-fiber calls."""
        all_offers = []

        try:
            self._logger.debug(f"Parsing PingPerfect aggregated response with {len(aggregated_response)} call types")

            for call_data in aggregated_response:
                call_type = call_data.get("call_type", "unknown")
                wants_fiber = call_data.get("wants_fiber", False)
                offers_data = call_data.get("offers", [])

                if not offers_data:
                    self._logger.warning(f"No offers data for call_type={call_type}")
                    continue

                self._logger.debug(f"Processing {call_type} call (wantsFiber={wants_fiber}) with {len(offers_data)} offers")

                # Parse this call's offers
                call_offers = await self._parse_offers_data(offers_data, call_type)
                all_offers.extend(call_offers)

                self._logger.info(f"Parsed {len(call_offers)} offers for {call_type}")

            self._logger.info(f"Total PingPerfect offers across all calls: {len(all_offers)}")
            return all_offers

        except Exception as e:
            self._logger.error(f"Error parsing PingPerfect aggregated response: {e}")
            return []

    async def _parse_offers_data(self, offers_data: List[Dict], call_type: str) -> List[ProviderOffer]:
        """Parse PingPerfect offers array into ProviderOffer objects."""
        offers = []

        try:
            for i, offer_data in enumerate(offers_data, 1):
                try:
                    # Extract data according to PingPerfect response format
                    provider_name = offer_data.get("providerName", "PingPerfect")

                    # Product info
                    product_info = offer_data.get("productInfo", {})
                    speed = self._safe_int(product_info.get("speed", 0))
                    contract_duration = self._safe_int(product_info.get("contractDurationInMonths", 0))
                    connection_type = product_info.get("connectionType", "Unknown")
                    tv_package = product_info.get("tv", "")

                    # Pricing info
                    pricing_details = offer_data.get("pricingDetails", {})
                    monthly_cost = self._safe_int(pricing_details.get("monthlyCostInCent", 0))
                    installation_service = pricing_details.get("installationService", "no")

                    # Normalize connection type to match other providers
                    normalized_connection_type = self._normalize_connection_type(connection_type)

                    # Calculate upload speed
                    if normalized_connection_type == ConnectionType.FIBER:
                        upload_speed = max(1, speed // 2)  # Fiber typically has better upload
                    elif normalized_connection_type == ConnectionType.DSL:
                        upload_speed = max(1, speed // 10)
                    else:
                        upload_speed = max(1, speed // 5)

                    # Create ProviderOffer object
                    offer = ProviderOffer(
                        provider_name=provider_name,
                        product_id=f"ping_perfect_{normalized_connection_type.value.lower()}_{i}",
                        speed_download_mbps=speed,
                        speed_upload_mbps=upload_speed,
                        monthly_cost_euros=Decimal(monthly_cost) / 100,
                        connection_type=normalized_connection_type,
                        contract_duration_months=contract_duration,
                        setup_fee_euros=None,  # Not specified in PingPerfect response
                        status=OfferStatus.AVAILABLE,
                    )

                    # Add additional features
                    offer.add_feature("installation_service", installation_service.lower() in ["yes", "true", "1"])
                    offer.add_feature("tv_included", bool(tv_package.strip()))
                    offer.add_feature("call_type", call_type)
                    offer.add_feature("wants_fiber", call_type == "fiber")
                    offer.add_feature("voucher_type", "")  # PingPerfect doesn't seem to have vouchers
                    offer.add_feature("voucher_value_euros", Decimal("0"))

                    offers.append(offer)

                    self._logger.debug(
                        f"Parsed PingPerfect offer {i}: {provider_name} - {speed} Mbps - {monthly_cost / 100:.2f}€ - {normalized_connection_type.value}"
                    )

                except Exception as e:
                    self._logger.error(f"Error parsing PingPerfect offer {i}: {e}")
                    continue

            return offers

        except Exception as e:
            self._logger.error(f"Error parsing PingPerfect offers: {e}")
            return []

    async def validate_address(self, address: Address) -> bool:
        """Validate if an address is supported by PingPerfect."""
        if address.country not in self._supported_regions:
            return False

        # Additional validation logic could be added here
        return True

    async def get_provider_status(self) -> ProviderStatus:
        """Get current status of PingPerfect provider."""
        return self._status

    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "PingPerfect"

    @property
    def provider_type(self) -> ProviderType:
        """Get the type of the provider."""
        return ProviderType.API_BASED

    @property
    def supported_regions(self) -> List[str]:
        """Get list of supported regions/countries."""
        return self._supported_regions.copy()

    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limiting information for PingPerfect."""
        return {
            "remaining_requests": self._rate_limit_remaining,
            "total_calls": self._call_count,
            "provider_type": "API_BASED",
            "call_types_supported": self._call_types,
            "api_key": self._api_key,
        }

    def _create_canonical_string(self, request_data: Dict[str, Any]) -> str:
        """Create canonical string for signing."""
        # Sort the request data by key for consistent signing
        sorted_items = sorted(request_data.items())
        canonical_parts = []

        for key, value in sorted_items:
            canonical_parts.append(f"{key}={value}")

        return "&".join(canonical_parts)

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to integer."""
        if value is None or value == "":
            return default
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return default

    def _normalize_connection_type(self, connection_type: str) -> ConnectionType:
        """Normalize connection type string to ConnectionType enum."""
        if not connection_type:
            return ConnectionType.UNKNOWN

        connection_upper = connection_type.upper()

        if connection_upper in ["DSL", "ADSL", "VDSL"]:
            return ConnectionType.DSL
        elif connection_upper in ["CABLE", "COAX"]:
            return ConnectionType.CABLE
        elif connection_upper in ["FIBER", "FIBRE", "FTTH", "FTTB"]:
            return ConnectionType.FIBER
        elif connection_upper in ["SATELLITE", "SAT"]:
            return ConnectionType.SATELLITE
        elif connection_upper in ["MOBILE", "LTE", "5G", "4G"]:
            return ConnectionType.MOBILE
        else:
            return ConnectionType.UNKNOWN

    def _get_mock_offers_data(self, call_type: str) -> List[Dict[str, Any]]:
        """Generate mock offers data for testing."""
        if call_type == "fiber":
            return [
                {
                    "providerName": "PingPerfect",
                    "productInfo": {
                        "speed": 1000,
                        "contractDurationInMonths": 24,
                        "connectionType": "Fiber",
                        "tv": "Premium TV Package",
                    },
                    "pricingDetails": {"monthlyCostInCent": 5999, "installationService": "yes"},
                },
                {
                    "providerName": "PingPerfect",
                    "productInfo": {"speed": 500, "contractDurationInMonths": 12, "connectionType": "Fiber", "tv": ""},
                    "pricingDetails": {"monthlyCostInCent": 4999, "installationService": "no"},
                },
            ]
        else:  # non_fiber
            return [
                {
                    "providerName": "PingPerfect",
                    "productInfo": {"speed": 100, "contractDurationInMonths": 24, "connectionType": "Cable", "tv": "Basic TV"},
                    "pricingDetails": {"monthlyCostInCent": 3999, "installationService": "yes"},
                },
                {
                    "providerName": "PingPerfect",
                    "productInfo": {"speed": 50, "contractDurationInMonths": 12, "connectionType": "DSL", "tv": ""},
                    "pricingDetails": {"monthlyCostInCent": 2999, "installationService": "no"},
                },
            ]
