"""WebWunder provider service adapter implementation."""

import logging
import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ...application.interfaces.providers import IWebWunder, ProviderStatus, ProviderType
from ...domain.entities.provider_offer import ConnectionType, OfferStatus, ProviderOffer
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import InvalidAddressException, ProviderUnavailableException


class WebWunderAdapter(IWebWunder):
    """WebWunder provider service adapter with XML SOAP parsing capabilities."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize WebWunder adapter."""
        self._logger = logger or logging.getLogger(__name__)
        self._supported_regions = ["DE", "AT", "CH"]
        self._status = ProviderStatus.AVAILABLE
        self._rate_limit_remaining = 1000
        self._call_count = 0
        self._connection_types = ["DSL", "Cable", "Fiber"]  # Supported connection types

    async def get_offers(self, address: Address) -> List[ProviderOffer]:
        """Get internet offers for a specific address."""
        if not await self.validate_address(address):
            raise InvalidAddressException(f"Address not supported by WebWunder: {address.full_address}")

        if self._status != ProviderStatus.AVAILABLE:
            raise ProviderUnavailableException(f"WebWunder provider is {self._status.value}")

        try:
            # Get offers with metadata for the address
            offers_data = await self.get_offers_with_metadata(address)

            # Extract offers from metadata response
            offers = offers_data.get("offers", [])

            self._call_count += 1
            self._rate_limit_remaining -= 1

            self._logger.info(f"WebWunder: Retrieved {len(offers)} offers for {address.full_address}")
            return offers

        except Exception as e:
            self._logger.error(f"WebWunder: Failed to get offers for {address.full_address}: {e}")
            raise ProviderUnavailableException(f"WebWunder service error: {str(e)}")

    async def get_offers_with_metadata(self, address: Address) -> Dict[str, Any]:
        """Get offers with additional metadata from WebWunder."""
        try:
            # Get aggregated response from multiple connection types
            aggregated_response = await self._get_aggregated_response(address)

            # Parse the aggregated response
            all_offers = await self._parse_aggregated_response(aggregated_response)

            # Calculate metadata
            metadata = self._calculate_metadata(aggregated_response, all_offers)

            return {
                "offers": all_offers,
                "metadata": metadata,
                "address_metadata": {
                    "coverage_quality": "good",  # Would be calculated from actual data
                    "infrastructure_age": 5,
                    "competition_level": "medium",
                },
            }

        except Exception as e:
            self._logger.error(f"WebWunder: Failed to get offers with metadata: {e}")
            return {"offers": [], "metadata": {}, "address_metadata": {}}

    async def _get_aggregated_response(self, address: Address) -> List[Dict[str, Any]]:
        """Get aggregated response from multiple connection types."""
        # In a real implementation, this would make multiple SOAP requests
        # For now, we'll simulate the response structure
        self._logger.debug(f"Getting aggregated response for address: {address.full_address}")

        # Mock aggregated response for demonstration
        return [
            {"connection_type": "DSL", "response_data": self._get_mock_soap_response("DSL")},
            {"connection_type": "Cable", "response_data": self._get_mock_soap_response("Cable")},
            {"connection_type": "Fiber", "response_data": self._get_mock_soap_response("Fiber")},
        ]

    async def _parse_aggregated_response(self, aggregated_response: List[Dict]) -> List[ProviderOffer]:
        """Parse WebWunder aggregated response from multiple connection types."""
        all_offers = []

        try:
            self._logger.debug(f"Parsing WebWunder aggregated response with {len(aggregated_response)} connection types")

            for connection_data in aggregated_response:
                connection_type = connection_data.get("connection_type", "Unknown")
                xml_response = connection_data.get("response_data", "")

                if not xml_response:
                    self._logger.warning(f"No response data for {connection_type}")
                    continue

                self._logger.debug(f"Processing {connection_type} connection type")

                # Parse this connection type's XML response
                connection_offers = await self._parse_xml_response(xml_response, connection_type)
                all_offers.extend(connection_offers)

                self._logger.info(f"Found {len(connection_offers)} offers for {connection_type}")

            self._logger.info(f"Total WebWunder offers across all connection types: {len(all_offers)}")
            return all_offers

        except Exception as e:
            self._logger.error(f"Error parsing WebWunder aggregated response: {e}")
            return []

    async def _parse_xml_response(self, xml_response: str, connection_type: str = "Unknown") -> List[ProviderOffer]:
        """Parse single WebWunder SOAP XML response into ProviderOffer objects."""
        offers = []

        try:
            root = ET.fromstring(xml_response)

            # Register namespaces to handle XML properly
            namespaces = {
                "ns2": "http://webwunder.gendev7.check24.fun/offerservice",
                "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            }

            # Find all product elements
            product_elements = root.findall(".//ns2:products", namespaces)

            if not product_elements:
                # Fallback: try without namespace prefix
                product_elements = root.findall(".//products")

            self._logger.debug(f"Found {len(product_elements)} products for {connection_type}")

            for i, product_elem in enumerate(product_elements, 1):
                try:
                    # Extract basic product info with namespace handling
                    product_id = self._get_xml_text(product_elem, "productId", namespaces)
                    provider_name = self._get_xml_text(product_elem, "providerName", namespaces)

                    # Find productInfo element
                    product_info = product_elem.find("ns2:productInfo", namespaces)
                    if product_info is None:
                        product_info = product_elem.find("productInfo")

                    if product_info is not None:
                        # Extract product details
                        speed = self._safe_int(self._get_xml_text(product_info, "speed", namespaces))
                        monthly_cost = self._safe_int(self._get_xml_text(product_info, "monthlyCostInCent", namespaces))
                        monthly_cost_25th = self._safe_int(
                            self._get_xml_text(product_info, "monthlyCostInCentFrom25thMonth", namespaces)
                        )
                        contract_duration = self._safe_int(
                            self._get_xml_text(product_info, "contractDurationInMonths", namespaces)
                        )
                        xml_connection_type = self._get_xml_text(product_info, "connectionType", namespaces)

                        # Use connection type from Step Functions if XML doesn't have it
                        raw_connection_type = xml_connection_type or connection_type or "Unknown"
                        final_connection_type = self._normalize_connection_type(raw_connection_type)

                        # Calculate upload speed
                        if final_connection_type == ConnectionType.DSL:
                            upload_speed = max(1, speed // 10)
                        elif final_connection_type == ConnectionType.FIBER:
                            upload_speed = max(1, speed // 2)  # Fiber typically has better upload
                        else:
                            upload_speed = max(1, speed // 5)

                        # Handle voucher information
                        voucher_elem = product_info.find("ns2:voucher", namespaces)
                        if voucher_elem is None:
                            voucher_elem = product_info.find("voucher")

                        voucher_type = ""
                        voucher_value = 0

                        if voucher_elem is not None:
                            voucher_percentage = self._get_xml_text(voucher_elem, "percentage", namespaces)
                            voucher_max_discount = self._safe_int(
                                self._get_xml_text(voucher_elem, "maxDiscountInCent", namespaces)
                            )

                            if voucher_percentage:
                                voucher_type = f"{voucher_percentage}% discount"
                                voucher_value = voucher_max_discount

                        # Create ProviderOffer object
                        offer = ProviderOffer(
                            provider_name=provider_name or "WebWunder",
                            product_id=product_id or f"webwunder_{connection_type.lower()}_{i}",
                            speed_download_mbps=speed,
                            speed_upload_mbps=upload_speed,
                            monthly_cost_euros=Decimal(monthly_cost) / 100,
                            connection_type=final_connection_type,
                            contract_duration_months=contract_duration,
                            setup_fee_euros=None,  # Not specified in WebWunder API
                            status=OfferStatus.AVAILABLE,
                        )

                        # Add additional features
                        offer.add_feature("installation_service", True)  # Installation doesn't matter per test
                        offer.add_feature("tv_included", False)  # Not specified in WebWunder API
                        offer.add_feature("voucher_type", voucher_type)
                        offer.add_feature("voucher_value_euros", Decimal(voucher_value) / 100)
                        offer.add_feature("after_two_years_cost_euros", Decimal(monthly_cost_25th or monthly_cost) / 100)
                        offer.add_feature("connection_type_source", connection_type)

                        offers.append(offer)

                        self._logger.debug(
                            f"Parsed {connection_type} offer {i}: {provider_name} - {speed} Mbps - {monthly_cost / 100:.2f}€"
                        )

                except Exception as e:
                    self._logger.error(f"Error parsing {connection_type} product {i}: {e}")
                    continue

            return offers

        except ET.ParseError as e:
            self._logger.error(f"WebWunder XML parsing error for {connection_type}: {e}")
            self._logger.error(f"XML content preview: {xml_response[:500]}...")
            return []
        except Exception as e:
            self._logger.error(f"Error parsing WebWunder XML for {connection_type}: {e}")
            return []

    async def validate_address(self, address: Address) -> bool:
        """Validate if an address is supported by WebWunder."""
        if address.country not in self._supported_regions:
            return False

        # Additional validation logic could be added here
        return True

    async def get_provider_status(self) -> ProviderStatus:
        """Get current status of WebWunder provider."""
        return self._status

    @property
    def provider_name(self) -> str:
        """Get the name of the provider."""
        return "WebWunder"

    @property
    def provider_type(self) -> ProviderType:
        """Get the type of the provider."""
        return ProviderType.HYBRID

    @property
    def supported_regions(self) -> List[str]:
        """Get list of supported regions/countries."""
        return self._supported_regions.copy()

    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limiting information for WebWunder."""
        return {
            "remaining_requests": self._rate_limit_remaining,
            "total_calls": self._call_count,
            "provider_type": "HYBRID",
            "connection_types_supported": self._connection_types,
        }

    def _get_xml_text(self, element: ET.Element, tag_name: str, namespaces: Dict[str, str]) -> str:
        """Helper function to extract text from XML element with namespace fallback."""
        try:
            # Try with namespace first
            elem = element.find(f"ns2:{tag_name}", namespaces)
            if elem is not None and elem.text:
                return elem.text.strip()

            # Fallback: try without namespace
            elem = element.find(tag_name)
            if elem is not None and elem.text:
                return elem.text.strip()

            return ""
        except Exception:
            return ""

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to integer."""
        if value is None or value == "":
            return default
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return default

    def _normalize_connection_type(self, connection_type: str) -> ConnectionType:
        """Normalize connection type to consistent format."""
        if not connection_type:
            return ConnectionType.UNKNOWN

        connection_type_upper = connection_type.upper()

        if connection_type_upper == "FIBER":
            return ConnectionType.FIBER
        elif connection_type_upper == "DSL":
            return ConnectionType.DSL
        elif connection_type_upper == "CABLE":
            return ConnectionType.CABLE
        elif connection_type_upper == "SATELLITE":
            return ConnectionType.SATELLITE
        elif connection_type_upper in ["MOBILE", "LTE", "5G"]:
            return ConnectionType.MOBILE
        else:
            return ConnectionType.UNKNOWN

    def _calculate_metadata(self, aggregated_response: List[Dict], offers: List[ProviderOffer]) -> Dict[str, Any]:
        """Calculate metadata from aggregated response and offers."""
        successful_connections = len([r for r in aggregated_response if r.get("response_data")])

        return {
            "successful_connections": successful_connections,
            "connection_types_attempted": len(aggregated_response),
            "total_offers": len(offers),
            "connection_types_with_offers": len(
                set(
                    offer.get_feature("connection_type_source")
                    for offer in offers
                    if offer.has_feature("connection_type_source")
                )
            ),
            "processing_method": "xml_soap",
        }

    def _get_mock_soap_response(self, connection_type: str) -> str:
        """Generate mock SOAP response for testing."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns2="http://webwunder.gendev7.check24.fun/offerservice">
    <soap:Body>
        <ns2:getOffersResponse>
            <ns2:products>
                <ns2:productId>webwunder_{connection_type.lower()}_basic</ns2:productId>
                <ns2:providerName>WebWunder</ns2:providerName>
                <ns2:productInfo>
                    <ns2:speed>{50 if connection_type == 'DSL' else 100 if connection_type == 'Cable' else 500}</ns2:speed>
                    <ns2:monthlyCostInCent>{3999 if connection_type == 'DSL' else 4999 if connection_type == 'Cable' else 5999}</ns2:monthlyCostInCent>
                    <ns2:monthlyCostInCentFrom25thMonth>{4499 if connection_type == 'DSL' else 5499 if connection_type == 'Cable' else 6499}</ns2:monthlyCostInCentFrom25thMonth>
                    <ns2:contractDurationInMonths>24</ns2:contractDurationInMonths>
                    <ns2:connectionType>{connection_type}</ns2:connectionType>
                    <ns2:voucher>
                        <ns2:percentage>10</ns2:percentage>
                        <ns2:maxDiscountInCent>1000</ns2:maxDiscountInCent>
                    </ns2:voucher>
                </ns2:productInfo>
            </ns2:products>
        </ns2:getOffersResponse>
    </soap:Body>
</soap:Envelope>"""
