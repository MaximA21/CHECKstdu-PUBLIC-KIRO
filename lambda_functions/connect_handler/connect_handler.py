import json
import os
import boto3
import uuid
import logging
from datetime import datetime

# Konfiguriere Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB-Client
#dynamodb = boto3.resource('dynamodb')
#TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
#table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    logger.info("Connect-Handler aufgerufen")
    logger.info(f"Event: {json.dumps(event)}")

    connection_id = event.get('requestContext', {}).get('connectionId')
    if not connection_id:
        logger.error("Keine Connection-ID gefunden")
        return {'statusCode': 400, 'body': 'Connection-ID fehlt'}

    # Query-Parameter extrahieren (falls verfügbar)
    query_params = event.get('queryStringParameters', {}) or {}
    street = query_params.get('street', '')
    house_number = query_params.get('houseNumber', '')
    city = query_params.get('city', '')
    postal_code = query_params.get('postalCode', '')
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Verbunden', 'connection_id': connection_id})
    }
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

        # In DynamoDB speichern
        table.put_item(Item=item)

        logger.info(f"Verbindung gespeichert: {connection_id}, Session: {session_id}, Share-ID: {share_id}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Verbunden',
                'session_id': session_id,
                'share_id': share_id
            })
        }
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Verbindung: {str(e)}")
        return {'statusCode': 500, 'body': 'Interner Serverfehler'}
        """
