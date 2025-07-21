import sys
import os

# Add src directory to path for importing the new DI-based handler
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import the new DI-based handler
from presentation.lambda_handlers.connect_handler import lambda_handler as di_lambda_handler


def lambda_handler(event, context):
    """Lambda entry point that delegates to DI-based handler."""
    return di_lambda_handler(event, context)
"""
    # In DynamoDB speichern
    try:
        session_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        item = {
            'session_id': session_id,
            'connection_id': connection_id,
            'timestamp': timestamp,
            'status': 'connected',
            'address': {
                'street': street,
                'house_number': house_number,
                'city': city,
                'postal_code': postal_code
            } if all([street, house_number, city, postal_code]) else {}
        }

        # Eindeutige Share-ID für den Teilen-Link generieren
        share_id = str(uuid.uuid4())[:8]  # Kürzere Version für den Link
        item['share_id'] = share_id

        # Log session details at DEBUG level
        logger.debug(f"Generated session ID: {session_id}")
        logger.debug(f"Generated share ID: {share_id}")
        logger.debug(f"Session timestamp: {timestamp}")
        logger.debug(f"DynamoDB item: {json.dumps(item, default=str)}")

        # In DynamoDB speichern
        table.put_item(Item=item)

        # Connection saved successfully at INFO level
        logger.info(f"Connection session saved successfully - Connection: {connection_id}, Session: {session_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Verbunden',
                'session_id': session_id,
                'share_id': share_id
            })
        }
    except Exception as e:
        logger.error(f"Failed to save connection session: {str(e)}")
        return {'statusCode': 500, 'body': 'Internal server error'}
        """
