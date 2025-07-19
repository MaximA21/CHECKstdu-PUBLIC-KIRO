import json
import os
import boto3
import logging

# Konfiguriere Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS-Clients
sqs = boto3.client('sqs')
sfn = boto3.client('stepfunctions')

# Umgebungsvariablen
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')


def lambda_handler(event, context):
    logger.info("Requestor Handler aufgerufen")
    logger.info(f"Event: {json.dumps(event)}")

    # SQS-Trigger-Event verarbeiten
    if not SQS_QUEUE_URL or not STATE_MACHINE_ARN:
        logger.error("SQS_QUEUE_URL oder STATE_MACHINE_ARN nicht konfiguriert")
        return {"statusCode": 500, "body": "Konfigurationsfehler"}

    for record in event.get('Records', []):
        try:
            # Nachricht aus SQS verarbeiten
            message_body = record.get('body')
            if not message_body:
                logger.warning("Leere Nachricht übersprungen")
                continue

            request_data = json.loads(message_body)
            logger.info(f"Verarbeite Anfrage: {request_data.get('request_id')}")

            # Step Functions starten
            execution_input = {
                "request_id": request_data.get('request_id'),
                "connection_id": request_data.get('connection_id'),
                "address": request_data.get('address'),
                "share_token": request_data.get('share_token'),
                "timestamp": request_data.get('timestamp')
            }

            execution_name = f"req-{request_data.get('request_id', 'unknown')}"
            if len(execution_name) > 80:  # Step Functions hat ein Limit für den Namen
                execution_name = execution_name[:80]

            response = sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(execution_input)
            )

            logger.info(f"Step Functions gestartet: {response.get('executionArn')}")

        except Exception as e:
            logger.error(f"Fehler bei der Verarbeitung: {str(e)}")
            # Die Nachricht wird wieder in die Queue gestellt, da wir keine explizite Bestätigung senden

    return {"statusCode": 200, "body": "Erfolgreich verarbeitet"}