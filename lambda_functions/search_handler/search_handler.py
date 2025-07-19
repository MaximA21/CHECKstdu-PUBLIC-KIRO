import json
import os
import boto3
import logging
import uuid
from datetime import datetime

# Konfiguriere Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS-Clients
sqs = boto3.client('sqs')
#dynamodb = boto3.resource('dynamodb')
#apigw_management = boto3.client('apigatewaymanagementapi',
  #                              endpoint_url=f"https://{os.environ.get('APIGW_ENDPOINT')}")

# Redis-Client (für ElastiCache)
#redis_host = os.environ.get('ELASTICACHE_HOST')
#redis_port = 6379
#redis_client = None

#if redis_host:
 #   try:
  #      redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)
   #     logger.info(f"Redis-Verbindung hergestellt: {redis_host}:{redis_port}")
   # except Exception as e:
    #    logger.error(f"Fehler bei Redis-Verbindung: {str(e)}")

# Umgebungsvariablen
#TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
#REQUEST_ID_PREFIX = os.environ.get('REQUEST_ID_PREFIX', 'req')

# DynamoDB-Tabelle
#table = dynamodb.Table(TABLE_NAME)

'''
def check_cache(address):
    """Prüft, ob Ergebnisse für diese Adresse im Cache sind"""
    if not redis_client:
        return None

    # Cache-Schlüssel generieren
    cache_key = f"addr:{address['street']}:{address['house_number']}:{address['city']}:{address['postal_code']}"

    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info(f"Cache-Treffer für {cache_key}")
            return json.loads(cached_data)
        else:
            logger.info(f"Kein Cache-Eintrag für {cache_key}")
            return None
    except Exception as e:
        logger.error(f"Fehler beim Cache-Zugriff: {str(e)}")
        return None


def send_to_client(connection_id, message):
    """Sendet eine Nachricht an einen verbundenen Client"""
    try:
        apigw_management.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode('utf-8')
        )
        logger.info(f"Nachricht an {connection_id} gesendet")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Senden an {connection_id}: {str(e)}")
        return False
'''

def lambda_handler(event, context):
    logger.info("Search-Handler aufgerufen")
    logger.info(f"Event: {json.dumps(event)}")

    # Verbindungs-ID extrahieren
    connection_id = event.get('requestContext', {}).get('connectionId')
    if not connection_id:
        logger.error("Keine Connection-ID gefunden")
        return {'statusCode': 400, 'body': 'Connection-ID fehlt'}

    try:
        # Suchanfrage aus dem Body extrahieren
        body = json.loads(event.get('body', '{}'))

        # Adressdaten validieren
        address = body.get('address', {})
        if not all(key in address for key in ['street', 'house_number', 'city', 'postal_code']):
            error_msg = {'error': 'Unvollständige Adressdaten'}
           # send_to_client(connection_id, error_msg)
            return {'statusCode': 400, 'body': json.dumps(error_msg)}

#test
        # Eindeutige Anfrage-ID generieren
        request_id = str(uuid.uuid4())
        share_token = str(uuid.uuid4())[:8]

        # Nachricht an SQS-Queue senden
        if SQS_QUEUE_URL:
            message = {
                'request_id': request_id,
                'connection_id': connection_id,
                'address': address,
                'share_token': share_token,
                'timestamp': datetime.utcnow().isoformat()
            }

            sqs.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps(message)
            )

            logger.info(f"Anfrage {request_id} an SQS gesendet")

            # In einer echten Implementierung würden wir hier auch eine Bestätigung an den Client senden
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Suchanfrage verarbeitet',
                    'request_id': request_id,
                    'share_token': share_token
                })
            }
        else:
            logger.error("SQS_QUEUE_URL nicht konfiguriert")
            return {'statusCode': 500, 'body': json.dumps({'error': 'Server nicht konfiguriert'})}

    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Interner Serverfehler'})}

        # Verbindungs-ID in DynamoDB suchen
     #   response = table.scan(
      #      FilterExpression='connection_id = :cid',
       #     ExpressionAttributeValues={':cid': connection_id}
        #)

       # items = response.get('Items', [])
        #if not items:
         #   error_msg = {'error': 'Sitzung nicht gefunden'}
          #  send_to_client(connection_id, error_msg)
           # return {'statusCode': 404, 'body': json.dumps(error_msg)}
'''''
        session = items[0]
        session_id = session.get('session_id')
        share_id = session.get('share_id')

        # Cache prüfen für schnelle Antwort
        cached_results = check_cache(address)
        if cached_results:
            # Cache-Ergebnisse direkt zurücksenden
            send_to_client(connection_id, {
                'type': 'RESULTS',
                'results': cached_results,
                'from_cache': True,
                'share_url': f"/share/{share_id}" if share_id else None
            })

            # Sitzung aktualisieren
            table.update_item(
                Key={'session_id': session_id},
                UpdateExpression='SET last_search = :addr, last_results = :res, updated_at = :time',
                ExpressionAttributeValues={
                    ':addr': address,
                    ':res': cached_results,
                    ':time': datetime.utcnow().isoformat()
                }
            )

            return {'statusCode': 200, 'body': 'Cache-Ergebnisse gesendet'}

        # Eindeutige Anfrage-ID generieren
#        request_id = f"{REQUEST_ID_PREFIX}-{uuid.uuid4()}"

        # Nachricht an SQS-Queue senden
        message = {
            'request_id': request_id,
            'session_id': session_id,
            'connection_id': connection_id,
            'address': address,
            'timestamp': datetime.utcnow().isoformat()
        }

        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )

        logger.info(f"Anfrage {request_id} an SQS gesendet für Session {session_id}")

        # Bestätigung an Client senden
        send_to_client(connection_id, {
            'type': 'SEARCH_INITIATED',
            'request_id': request_id,
            'message': 'Suche gestartet'
        })

        # Sitzung aktualisieren
        table.update_item(
            Key={'session_id': session_id},
            UpdateExpression='SET current_request = :req, last_search = :addr, updated_at = :time',
            ExpressionAttributeValues={
                ':req': request_id,
                ':addr': address,
                ':time': datetime.utcnow().isoformat()
            }
        )

        return {'statusCode': 200, 'body': 'Suchanfrage verarbeitet'}

    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung: {str(e)}")
        error_msg = {'error': 'Interner Serverfehler'}
        send_to_client(connection_id, error_msg)
        return {'statusCode': 500, 'body': json.dumps(error_msg)}
        
        '''