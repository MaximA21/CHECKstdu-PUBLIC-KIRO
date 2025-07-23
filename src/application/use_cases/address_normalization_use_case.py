"""Address normalization use case for API compatibility."""

from typing import Dict, Any

from ..interfaces.logging import ILogger
from ...domain.value_objects.address import Address
from ...shared.exceptions.domain import DomainException


class AddressNormalizationUseCase:
    """Use case for normalizing addresses for different provider APIs."""

    def __init__(self, logger: ILogger):
        self._logger = logger

    async def normalize_for_webwunder(self, address: Address) -> Dict[str, Any]:
        """
        Normalize address for WebWunder API compatibility.

        Args:
            address: Address to normalize

        Returns:
            Dict containing normalized address and metadata

        Raises:
            DomainException: If address normalization fails
        """
        try:
            self._logger.info("Starting address normalization for WebWunder", {"original_address": address.full_address})

            # Normalize German characters for WebWunder API
            normalized_address = Address(
                street=self._normalize_german_characters(address.street),
                house_number=address.house_number,  # Numbers don't need normalization
                city=self._normalize_german_characters(address.city),
                postal_code=address.postal_code,  # Postal codes don't need normalization
                country=address.country,
            )

            # Log normalization changes
            if address.street != normalized_address.street:
                self._logger.debug("Street normalized", {"original": address.street, "normalized": normalized_address.street})

            if address.city != normalized_address.city:
                self._logger.debug("City normalized", {"original": address.city, "normalized": normalized_address.city})

            result = {
                "normalized_address": {
                    "street": normalized_address.street,
                    "house_number": normalized_address.house_number,
                    "city": normalized_address.city,
                    "postal_code": normalized_address.postal_code,
                    "country": normalized_address.country,
                },
                "connection_types": ["FIBER", "DSL", "CABLE"],
                "normalization_applied": (
                    address.street != normalized_address.street or address.city != normalized_address.city
                ),
            }

            self._logger.info(
                "Address normalization completed successfully", {"normalization_applied": result["normalization_applied"]}
            )

            return result

        except Exception as e:
            self._logger.error("Address normalization failed", {"address": address.full_address, "error": str(e)}, exception=e)
            raise DomainException(f"Failed to normalize address: {str(e)}")

    def _normalize_german_characters(self, text: str) -> str:
        """Convert German characters to ASCII equivalents for WebWunder API."""
        if not text:
            return text

        # German character mappings
        replacements = {"ß": "ss", "ä": "ae", "Ä": "Ae", "ö": "oe", "Ö": "Oe", "ü": "ue", "Ü": "Ue"}

        normalized = text
        for german_char, ascii_equiv in replacements.items():
            normalized = normalized.replace(german_char, ascii_equiv)

        return normalized
