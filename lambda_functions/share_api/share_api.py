import json
import os
import boto3
import logging
from decimal import Decimal
from datetime import datetime

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables
RESULTS_TABLE_NAME = os.environ.get('RESULTS_TABLE_NAME')
results_table = dynamodb.Table(RESULTS_TABLE_NAME) if RESULTS_TABLE_NAME else None


def decimal_to_float(obj):
    """Convert Decimal values back to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: decimal_to_float(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    else:
        return obj


def lambda_handler(event, context):
    """🔗 Share API - Get results by share token"""
    logger.info("🔗 Share API called")

    try:
        # Extract share token from path
        path_parameters = event.get('pathParameters', {})
        share_token = path_parameters.get('share_token') if path_parameters else None

        if not share_token:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Share token required'})
            }

        if not results_table:
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Database not configured'})
            }

        # Query DynamoDB using GSI
        response = results_table.query(
            IndexName='ShareTokenIndex',
            KeyConditionExpression='share_token = :token',
            ExpressionAttributeValues={':token': share_token}
        )

        items = response.get('Items', [])

        if not items:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Share link not found or expired'})
            }

        # Aggregate results from all providers for this search
        all_offers = []
        search_metadata = {}

        for item in items:
            # Convert Decimals back to floats for JSON
            offers = decimal_to_float(item.get('offers', []))
            all_offers.extend(offers)

            # Set metadata from first item
            if not search_metadata:
                search_metadata = {
                    'request_id': item.get('request_id'),
                    'timestamp': item.get('timestamp'),
                    'address': decimal_to_float(item.get('address', {})),
                    'total_providers': len(items)
                }

        # Sort offers by best value (price/speed ratio)
        try:
            all_offers.sort(key=lambda x: x.get('monthly_cost_euros', 999) / max(x.get('speed_mbps', 1), 1))
        except:
            pass  # Keep original order if sorting fails

        result = {
            'share_token': share_token,
            'metadata': search_metadata,
            'offers': all_offers,
            'total_offers': len(all_offers),
            'generated_at': datetime.utcnow().isoformat(),
            'share_url': f"/share/{share_token}"
        }

        logger.info(f"✅ Served {len(all_offers)} offers for share token {share_token}")

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=300'  # Cache for 5 minutes
            },
            'body': json.dumps(result, separators=(',', ':'))
        }

    except Exception as e:
        logger.error(f"Error in share API: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }