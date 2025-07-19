import json
import logging

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def normalize_german_characters(text: str) -> str:
    """Convert German characters to ASCII equivalents for WebWunder API"""
    if not text:
        return text

    # German character mappings
    replacements = {
        'ß': 'ss',
        'ä': 'ae', 'Ä': 'Ae',
        'ö': 'oe', 'Ö': 'Oe',
        'ü': 'ue', 'Ü': 'Ue'
    }

    normalized = text
    for german_char, ascii_equiv in replacements.items():
        normalized = normalized.replace(german_char, ascii_equiv)

    return normalized


def lambda_handler(event, context):
    """🔧 Address Normalizer for WebWunder API compatibility"""

    try:
        logger.info("🔧 Address normalizer called")
        logger.info(f"Input event: {json.dumps(event)}")

        # Extract input data
        address = event.get('address', {})

        # Normalize each address field
        normalized_address = {
            'street': normalize_german_characters(address.get('street', '')),
            'house_number': address.get('house_number', ''),  # Numbers don't need normalization
            'city': normalize_german_characters(address.get('city', '')),
            'postal_code': address.get('postal_code', '')  # Postal codes don't need normalization
        }

        # Log the normalization for debugging
        original_street = address.get('street', '')
        original_city = address.get('city', '')
        normalized_street = normalized_address['street']
        normalized_city = normalized_address['city']

        if original_street != normalized_street:
            logger.info(f"🔄 Street normalized: '{original_street}' → '{normalized_street}'")
        if original_city != normalized_city:
            logger.info(f"🔄 City normalized: '{original_city}' → '{normalized_city}'")

        # Return the complete event with normalized address
        result = {
            **event,  # Preserve all original data
            'normalized_address': normalized_address,
            'connection_types': ["FIBER", "DSL", "CABLE"]
        }

        logger.info(f"✅ Address normalization completed")
        logger.info(f"Output: {json.dumps(result)}")

        return result

    except Exception as e:
        logger.error(f"❌ Error in address normalizer: {e}")
        # Return original event on error to avoid breaking the workflow
        return {
            **event,
            'normalized_address': event.get('address', {}),
            'connection_types': ["FIBER", "DSL", "CABLE"],
            'normalization_error': str(e)
        }