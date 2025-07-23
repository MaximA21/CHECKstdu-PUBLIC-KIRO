"""VerbynDich provider service adapter implementation."""

import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ...application.interfaces.providers import IVerbynDich, ProviderStatus, ProviderType
from ...domain.entities.provider_offer import ConnectionType, OfferStatus, ProviderOffer
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import InvalidAddressException, ProviderUnavailableException


class VerbynDichAdapter(IVerbynDich):
    """VerbynDich provider service adapter with nested array parsing capabilities."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize VerbynDich adapter."""
        self._logger = logger or logging.getLogger(__name__)
        self._supported_regions = ["DE", "AT", "CH"]
        self._status = ProviderStatus.AVAILABLE
        self._rate_limit_remaining = 1000
        self._call_count = 0

    async def get_offers(self, address: Address) -> List[ProviderOffer]:
        """Get internet offers for a specific address."""
        if not await self.validate_address(address):
            raise InvalidAddressException(f"Address not supported by VerbynDich: {address.full_address}")

        if self._status != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableException(f"VerbynDich provider is {self._status.value}")

        try:
            # Get API data for the address
            api_data = await self.get_api_data_for_address(address)

            # Parse nested array data into offers
            offers = await self.parse_nested_array_data(api_data)

            self._call_count += 1
            self._rate_limit_remaining -= 1

            self._logger.info(f"VerbynDich: Retrieved {len(offers)} offers for {address.full_address}")
            return offers

        except Exception as e:
            self._logger.error(f"VerbynDich: Failed to get offers for {address.full_address}: {e}")
            raise ProviderUnavailableException(f"VerbynDich service error: {str(e)}")

    async def parse_nested_array_data(self, json_data: Dict[str, Any]) -> List[ProviderOffer]:
        """Parse nested array data from VerbynDich provider."""
        try:
            # Flatten the deeply nested array structure
            flattened_offers = self._flatten_nested_array(json_data)

            offers = []
            for item in flattened_offers:
                if isinstance(item, dict) and item.get("valid") and item.get("product"):
                    try:
                        # Parse the description text
                        parsed_data = self._parse_description(item.get("description", ""))

                        # Calculate upload speed (assume 10% of download for DSL, 20% for others)
                        download_speed = parsed_data["speed_mbps"]
                        if parsed_data["connection_type"] == "DSL":
                            upload_speed = max(1, download_speed // 10)
                        else:
                            upload_speed = max(1, download_speed // 5)

                        offer = ProviderOffer(
                            provider_name="VerbynDich",
                            product_id=item.get("product", "unknown"),
                            speed_download_mbps=download_speed,
                            speed_upload_mbps=upload_speed,
                            monthly_cost_euros=Decimal(str(parsed_data["monthly_cost_euros"])),
                            connection_type=self._normalize_connection_type(parsed_data["connection_type"]),
                            contract_duration_months=parsed_data["contract_duration_months"],
                            setup_fee_euros=None,  # Not specified in VerbynDich descriptions
                            status=OfferStatus.AVAILABLE,
                        )

                        # Add additional features
                        offer.add_feature("tv_included", parsed_data["tv_included"])
                        offer.add_feature("discount_percent", parsed_data["discount_percent"])
                        offer.add_feature("max_discount_euros", parsed_data["max_discount_euros"])
                        offer.add_feature(
                            "after_two_years_cost_euros", Decimal(str(parsed_data["after_two_years_cost_euros"]))
                        )
                        offer.add_feature("age_restriction", parsed_data["age_restriction"])
                        offer.add_feature("data_limit_gb", parsed_data["data_limit"])

                        offers.append(offer)

                    except Exception as e:
                        self._logger.warning(f"Failed to parse VerbynDich offer: {e}")
                        continue

            self._logger.info(f"VerbynDich: Parsed {len(offers)} offers from nested structure")
            return offers

        except Exception as e:
            self._logger.error(f"Failed to parse VerbynDich nested array data: {e}")
            return []

    async def get_api_data_for_address(self, address: Address) -> Dict[str, Any]:
        """Get API data for a specific address."""
        # In a real implementation, this would make an HTTP request to VerbynDich API
        # For now, we'll simulate the response with nested array structure
        self._logger.debug(f"Getting API data for address: {address.full_address}")

        # Mock nested array data for demonstration
        return {
            "results": [
                [
                    [
                        {
                            "valid": True,
                            "product": "verbyndich_dsl_25",
                            "description": "Für nur 24€ im Monat erhalten Sie eine DSL-Verbindung mit einer Geschwindigkeit von 25 Mbit/s. Mindestvertragslaufzeit 12 Monate. Rabatt von 8% auf Ihre monatliche Rechnung. Der maximale Rabatt beträgt 107€. Ab dem 24. Monat beträgt der monatliche Preis 25€.",
                        }
                    ]
                ],
                [
                    {
                        "valid": True,
                        "product": "verbyndich_cable_100",
                        "description": "Für nur 39€ im Monat erhalten Sie eine Cable-Verbindung mit einer Geschwindigkeit von 100 Mbit/s. Fernsehsender enthalten. Mindestvertragslaufzeit 24 Monate. Ab 250GB pro Monat wird die Geschwindigkeit gedrosselt.",
                    }
                ],
                {
                    "valid": True,
                    "product": "verbyndich_fiber_500",
                    "description": "Für nur 59€ im Monat erhalten Sie eine Fiber-Verbindung mit einer Geschwindigkeit von 500 Mbit/s. Fernsehsender enthalten. Mindestvertragslaufzeit 24 Monate. Nur für Personen unter 27 Jahren.",
                },
            ]
        }

    async def validate_address(self, address: Address) -> bool:
        """Validate if an address is supported by VerbynDich."""
        if address.country not in self._supported_regions:
            return False

        # Additional validation logic could be added here
        return True

    async def get_provider_status(self) -> ProviderStatus:
        """Get current status of VerbynDich provider."""
        return self._status

    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "VerbynDich"

    @property
    def provider_type(self) -> ProviderType:
        """Get the type of the provider."""
        return ProviderType.API_BASED

    @property
    def supported_regions(self) -> List[str]:
        """Get list of supported regions/countries."""
        return self._supported_regions.copy()

    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limiting information for VerbynDich."""
        return {
            "remaining_requests": self._rate_limit_remaining,
            "total_calls": self._call_count,
            "provider_type": "API_BASED",
        }

    def _flatten_nested_array(self, nested_data: Any) -> List[Any]:
        """Recursively flatten deeply nested arrays from API response."""

        def _flatten(obj):
            if isinstance(obj, list):
                for item in obj:
                    yield from _flatten(item)
            elif isinstance(obj, dict):
                # Check if this dict contains the data we want
                if "results" in obj:
                    yield from _flatten(obj["results"])
                else:
                    yield obj
            else:
                yield obj

        return list(_flatten(nested_data))

    def _parse_description(self, description: str) -> Dict[str, Any]:
        """Parse VerbynDich description text to extract structured data."""
        # Initialize with defaults
        result = {
            "speed_mbps": 0,
            "monthly_cost_euros": 0.0,
            "after_two_years_cost_euros": 0.0,
            "contract_duration_months": 12,
            "connection_type": "Unknown",
            "tv_included": False,
            "discount_percent": 0,
            "max_discount_euros": 0,
            "age_restriction": None,
            "data_limit": None,
        }

        try:
            # Extract monthly cost: "Für nur 24€ im Monat"
            cost_match = re.search(r"Für nur (\d+)€ im Monat", description)
            if cost_match:
                result["monthly_cost_euros"] = float(cost_match.group(1))

            # Extract speed: "Geschwindigkeit von 25 Mbit/s"
            speed_match = re.search(r"Geschwindigkeit von (\d+) Mbit/s", description)
            if speed_match:
                result["speed_mbps"] = int(speed_match.group(1))

            # Extract connection type: "DSL-Verbindung", "Cable-Verbindung", "Fiber-Verbindung"
            if "DSL-Verbindung" in description:
                result["connection_type"] = "DSL"
            elif "Cable-Verbindung" in description:
                result["connection_type"] = "Cable"
            elif "Fiber-Verbindung" in description:
                result["connection_type"] = "Fiber"

            # Extract TV inclusion: "Fernsehsender enthalten"
            if "Fernsehsender enthalten" in description:
                result["tv_included"] = True

            # Extract contract duration: "Mindestvertragslaufzeit 12 Monate"
            contract_match = re.search(r"Mindestvertragslaufzeit (\d+) Monate", description)
            if contract_match:
                result["contract_duration_months"] = int(contract_match.group(1))

            # Extract discount: "Rabatt von 8% auf Ihre monatliche Rechnung"
            discount_match = re.search(r"Rabatt von (\d+)% auf", description)
            if discount_match:
                result["discount_percent"] = int(discount_match.group(1))

            # Extract max discount: "Der maximale Rabatt beträgt 107€"
            max_discount_match = re.search(r"maximale Rabatt beträgt (\d+)€", description)
            if max_discount_match:
                result["max_discount_euros"] = int(max_discount_match.group(1))

            # Extract after-discount price: "Ab dem 24. Monat beträgt der monatliche Preis 25€"
            after_price_match = re.search(r"Ab dem \d+\. Monat beträgt der monatliche Preis (\d+)€", description)
            if after_price_match:
                result["after_two_years_cost_euros"] = float(after_price_match.group(1))
            else:
                # If no after-price mentioned, assume same as monthly cost
                result["after_two_years_cost_euros"] = result["monthly_cost_euros"]

            # Extract age restriction: "nur für Personen unter 27 Jahren"
            if "nur für Personen unter 27 Jahren" in description:
                result["age_restriction"] = 27

            # Extract data limit: "Ab 250GB pro Monat wird die Geschwindigkeit gedrosselt"
            data_limit_match = re.search(r"Ab (\d+)GB pro Monat wird die Geschwindigkeit gedrosselt", description)
            if data_limit_match:
                result["data_limit"] = int(data_limit_match.group(1))

        except Exception as e:
            self._logger.warning(f"Failed to parse VerbynDich description: {e}")

        return result

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
