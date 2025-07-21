import json
import time
import hmac
import hashlib
import logging
import sys
import os

# Add src directory to path for importing new logging infrastructure
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from infrastructure.logging.legacy_logging_config import get_lambda_logger

# Configure logger with centralized configuration
logger = get_lambda_logger('ping_perfect_signer')


def generate_hmac_signature(request_body: str, secret: str) -> tuple:
    """Generate HMAC-SHA256 signature for Ping Perfect API"""

    # 1. Generate timestamp (Unix seconds)
    timestamp = int(time.time())

    # 2. Create string to sign: timestamp + ":" + request_body
    string_to_sign = f"{timestamp}:{request_body}"

    # 3. Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    logger.debug(f"🔐 Generated signature for timestamp {timestamp}")
    logger.debug(f"String to sign: {string_to_sign}")
    logger.debug(f"Signature: {signature}")

    return signature, timestamp


def lambda_handler(event, context):
    """🔐 Ping Perfect HMAC Signature Generator (returns signature to Step Functions)"""

    try:
        logger.info("🔐 Ping Perfect signature generator started")
        logger.debug(f"Input event: {json.dumps(event)}")

        # Extract data from event
        address = event.get('address', {})
        request_id = event.get('request_id')
        connection_id = event.get('connection_id')
        share_token = event.get('share_token')
        wants_fiber = event.get('wants_fiber', True)

        logger.debug(f"Extracted parameters - request_id: {request_id}, wants_fiber: {wants_fiber}")
        logger.debug(f"Address details: {json.dumps(address)}")

        # Get credentials from environment variables
        import os
        client_id = os.environ.get('PING_PERFECT_CLIENT_ID', '9A26C2B5')
        secret = os.environ.get('PING_PERFECT_SECRET', 'C6F8B73B5566FCFD2B47D58C93D75AEF')

        logger.debug(f"Using client_id: {client_id}")

        if not client_id or not secret:
            logger.error("❌ Missing Ping Perfect credentials")
            return {
                'success': False,
                'error': 'Missing API credentials'
            }

        # Prepare request body (EXACT formatting for signature consistency)
        request_body = {
            "street": address.get('street', ''),
            "houseNumber": address.get('house_number', ''),
            "city": address.get('city', ''),
            "plz": address.get('postal_code', ''),
            "wantsFiber": wants_fiber
        }

        # Convert to JSON string (no spaces for consistency)
        request_body_json = json.dumps(request_body, separators=(',', ':'))
        logger.debug(f"Request body JSON: {request_body_json}")

        # Generate signature
        signature, timestamp = generate_hmac_signature(request_body_json, secret)

        logger.info(f"✅ Signature generation completed successfully")
        logger.debug(f"Generated signature parameters - timestamp: {timestamp}, client_id: {client_id}")
        logger.debug(f"Final signature: {signature}")

        # Return all data needed for Step Functions HTTP call
        return {
            'success': True,
            'request_id': request_id,
            'connection_id': connection_id,
            'share_token': share_token,
            'address': address,
            'wants_fiber': wants_fiber,
            'signature': signature,
            'timestamp': str(timestamp),
            'client_id': client_id,
            'request_body': request_body_json,
            'api_endpoint': 'https://pingperfect.gendev7.check24.fun/internet/angebote/data'
        }

    except Exception as e:
        logger.error(f"❌ Error generating Ping Perfect signature: {e}")
        return {
            'success': False,
            'error': str(e),
            'request_id': event.get('request_id'),
            'connection_id': event.get('connection_id'),
            'share_token': event.get('share_token'),
            'wants_fiber': event.get('wants_fiber', True)
        }