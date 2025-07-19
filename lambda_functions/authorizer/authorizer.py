import json
import os
import boto3
import urllib.request
import urllib.parse
import logging

# Konfiguriere Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Google Maps API Key aus Umgebungsvariablen
GOOGLE_MAPS_API_KEY = ""  # os.environ.get('GOOGLE_MAPS_API_KEY')


def validate_address(street, house_number, city, postal_code, country_code="DE"):
    """Validiert eine Adresse mit der Google Maps Geocoding API"""
    if not GOOGLE_MAPS_API_KEY:
        logger.error("Google Maps API Key fehlt")
        return False

    # Adresse formatieren
    address = f"{street} {house_number}, {postal_code} {city}, {country_code}"

    # Anfrage an Google Maps API vorbereiten
    endpoint = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": GOOGLE_MAPS_API_KEY
    }
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"

    try:
        # Anfrage senden
        with urllib.request.urlopen(url) as response:
            result = json.loads(response.read().decode())

        # Ergebnis auswerten
        if result["status"] == "OK" and len(result["results"]) > 0:
            logger.info(f"Adresse validiert: {address}")
            return True
        else:
            logger.warning(f"Adresse ungültig: {address}, Status: {result['status']}")
            return False
    except Exception as e:
        logger.error(f"Fehler bei Adressvalidierung: {str(e)}")
        # Im Fehlerfall: Validierung erfolgreich, um die Benutzerfreundlichkeit nicht zu beeinträchtigen
        return True


def lambda_handler(event, context):
    logger.info("Authorizer aufgerufen")
    logger.info(f"Event: {json.dumps(event)}")

    # Verbindungsdetails
    query_params = event.get('queryStringParameters', {}) or {}
    if not query_params:
        logger.warning("Keine Query-Parameter gefunden")
        return generate_policy('Deny', event['methodArn'])

    # Token aus Query-Parametern extrahieren
    token = query_params.get('token')
    if not token:
        logger.warning("Token fehlt")
        return generate_policy('Deny', event['methodArn'])

    # In einer echten Anwendung: Token-Validierung gegen eine Datenbank oder einen Auth-Service
    # Hier einfach: Überprüfen, ob Token vorhanden (später erweitern)
    if token:
        # Adressdaten aus Query-Parametern extrahieren (falls vorhanden)
        street = query_params.get('street')
        house_number = query_params.get('houseNumber')
        city = query_params.get('city')
        postal_code = query_params.get('postalCode')

        # Wenn Adressdaten vorhanden sind, validieren
        if all([street, house_number, city, postal_code]):
            if not validate_address(street, house_number, city, postal_code):
                return generate_policy('Deny', event['methodArn'], 'Ungültige Adresse')

        # Token akzeptieren
        return generate_policy('Allow', event['methodArn'])

    # Token ablehnen
    return generate_policy('Deny', event['methodArn'])


def generate_policy(effect, resource, message=""):
    """Generiert eine IAM Policy für die API Gateway Authorisierung"""
    auth_response = {
        'principalId': 'user',  # Platzhalter, könnte eine User-ID sein
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }]
        },
        'context': {
            'message': message
        }
    }

    return auth_response