import json  # Fallback JSON
import os
import uuid
from decimal import Decimal

import boto3
import logging
import time
from io import StringIO
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
#webwunder
import xml.etree.ElementTree as ET

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
apigateway_management = boto3.client('apigatewaymanagementapi',
                                     endpoint_url=f"https://{os.environ.get('WEBSOCKET_API_ENDPOINT')}")

dynamodb = boto3.resource('dynamodb')

# Environment variables
RESULTS_TABLE_NAME = os.environ.get('RESULTS_TABLE_NAME')
ANALYTICS_TABLE_NAME = os.environ.get('ANALYTICS_TABLE_NAME')

# DynamoDB tables
results_table = dynamodb.Table(RESULTS_TABLE_NAME) if RESULTS_TABLE_NAME else None
analytics_table = dynamodb.Table(ANALYTICS_TABLE_NAME) if ANALYTICS_TABLE_NAME else None

# Try to import high-performance libraries, fall back to standard library
try:
    import orjson

    HAS_ORJSON = True
    logger.info("✅ Using orjson for ultra-fast JSON processing")
except ImportError as e:
    logger.warning(f"⚠️  orjson not available ({e}), falling back to standard json")
    HAS_ORJSON = False

try:
    import polars as pl

    HAS_POLARS = True
    logger.info("✅ Using Polars for ultra-fast data processing")
except ImportError as e:
    logger.warning(f"⚠️  Polars not available ({e}), falling back to pure Python")
    HAS_POLARS = False

# Initialize HAS_PANDAS to False since we're not using it
HAS_PANDAS = False


@dataclass
class UnifiedOffer:
    """Unified offer structure for all providers"""
    provider_name: str
    product_id: str
    speed_mbps: int
    monthly_cost_cents: int
    after_two_years_cost_cents: int
    contract_duration_months: int
    connection_type: str
    installation_service: bool
    tv_included: bool
    voucher_type: str
    voucher_value: int

    def to_dict_optimized(self) -> Dict[str, Any]:
        """Optimized dict conversion"""
        return {
            'provider_name': self.provider_name,
            'product_id': self.product_id,
            'speed_mbps': self.speed_mbps,
            'monthly_cost_euros': round(self.monthly_cost_cents / 100.0, 2),
            'after_two_years_cost_euros': round(self.after_two_years_cost_cents / 100.0, 2),
            'contract_duration_months': self.contract_duration_months,
            'connection_type': self.connection_type,
            'installation_service': self.installation_service,
            'tv_included': self.tv_included,
            'voucher_type': self.voucher_type,
            'voucher_value_euros': round(self.voucher_value / 100.0, 2)
        }


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer"""
    if value is None or value == '':
        return default
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any) -> bool:
    """Safely convert value to boolean"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in ['true', '1', 'yes', 'on']
    return bool(value)


def flatten_nested_array(nested_data):
    """Recursively flatten deeply nested arrays from Step Functions"""

    def _flatten(obj):
        if isinstance(obj, list):
            for item in obj:
                yield from _flatten(item)
        else:
            yield obj

    return list(_flatten(nested_data))


def parse_verbyndich_description(description: str) -> dict:
    """Parse VerbynDich description text to extract structured data"""
    import re

    # Initialize with defaults
    result = {
        'speed_mbps': 0,
        'monthly_cost_euros': 0.0,
        'after_two_years_cost_euros': 0.0,
        'contract_duration_months': 12,
        'connection_type': 'Unknown',
        'tv_included': False,
        'discount_percent': 0,
        'max_discount_euros': 0,
        'age_restriction': None,
        'data_limit': None
    }

    try:
        # Extract monthly cost: "Für nur 24€ im Monat"
        cost_match = re.search(r'Für nur (\d+)€ im Monat', description)
        if cost_match:
            result['monthly_cost_euros'] = float(cost_match.group(1))

        # Extract speed: "Geschwindigkeit von 25 Mbit/s"
        speed_match = re.search(r'Geschwindigkeit von (\d+) Mbit/s', description)
        if speed_match:
            result['speed_mbps'] = int(speed_match.group(1))

        # Extract connection type: "DSL-Verbindung", "Cable-Verbindung", "Fiber-Verbindung"
        if 'DSL-Verbindung' in description:
            result['connection_type'] = 'DSL'
        elif 'Cable-Verbindung' in description:
            result['connection_type'] = 'Cable'
        elif 'Fiber-Verbindung' in description:
            result['connection_type'] = 'Fiber'

        # Extract TV inclusion: "Fernsehsender enthalten"
        if 'Fernsehsender enthalten' in description:
            result['tv_included'] = True

        # Extract contract duration: "Mindestvertragslaufzeit 12 Monate"
        contract_match = re.search(r'Mindestvertragslaufzeit (\d+) Monate', description)
        if contract_match:
            result['contract_duration_months'] = int(contract_match.group(1))

        # Extract discount: "Rabatt von 8% auf Ihre monatliche Rechnung"
        discount_match = re.search(r'Rabatt von (\d+)% auf', description)
        if discount_match:
            result['discount_percent'] = int(discount_match.group(1))

        # Extract max discount: "Der maximale Rabatt beträgt 107€"
        max_discount_match = re.search(r'maximale Rabatt beträgt (\d+)€', description)
        if max_discount_match:
            result['max_discount_euros'] = int(max_discount_match.group(1))

        # Extract after-discount price: "Ab dem 24. Monat beträgt der monatliche Preis 25€"
        after_price_match = re.search(r'Ab dem \d+\. Monat beträgt der monatliche Preis (\d+)€', description)
        if after_price_match:
            result['after_two_years_cost_euros'] = float(after_price_match.group(1))
        else:
            # If no after-price mentioned, assume same as monthly cost
            result['after_two_years_cost_euros'] = result['monthly_cost_euros']

        # Extract age restriction: "nur für Personen unter 27 Jahren"
        if 'nur für Personen unter 27 Jahren' in description:
            result['age_restriction'] = 27

        # Extract data limit: "Ab 250GB pro Monat wird die Geschwindigkeit gedrosselt"
        data_limit_match = re.search(r'Ab (\d+)GB pro Monat wird die Geschwindigkeit gedrosselt', description)
        if data_limit_match:
            result['data_limit'] = int(data_limit_match.group(1))

    except Exception as e:
        logger.warning(f"Failed to parse VerbynDich description: {e}")

    return result


def parse_verbyndich_offers(raw_response) -> List[UnifiedOffer]:
    """Parse VerbynDich nested array response and extract offers"""
    try:
        # Flatten the deeply nested array structure
        flattened_offers = flatten_nested_array(raw_response)

        offers = []
        for item in flattened_offers:
            if isinstance(item, dict) and item.get('valid') and item.get('product'):
                # Parse the description text
                parsed_data = parse_verbyndich_description(item.get('description', ''))

                # Create unified offer
                offer = UnifiedOffer(
                    provider_name='VerbynDich',
                    product_id=item.get('product', 'unknown'),
                    speed_mbps=parsed_data['speed_mbps'],
                    monthly_cost_cents=int(parsed_data['monthly_cost_euros'] * 100),
                    after_two_years_cost_cents=int(parsed_data['after_two_years_cost_euros'] * 100),
                    contract_duration_months=parsed_data['contract_duration_months'],
                    connection_type=parsed_data['connection_type'],
                    installation_service=False,  # Not mentioned in descriptions
                    tv_included=parsed_data['tv_included'],
                    voucher_type='absolute' if parsed_data['discount_percent'] > 0 else '',
                    voucher_value=parsed_data['max_discount_euros']
                )
                offers.append(offer)

        logger.info(f"📡 VerbynDich: Parsed {len(offers)} offers from nested structure")
        return offers

    except Exception as e:
        logger.error(f"Failed to parse VerbynDich offers: {e}")
        return []


def parse_byteme_csv_lazy_optimized(csv_data: str) -> List[UnifiedOffer]:
    """🚀 LAZY POLARS - Query optimization + predicate pushdown"""
    try:
        logger.info("⚡ Using LAZY Polars for ultra-optimized CSV parsing")

        # Step 1: For lazy operations, we need to use read_csv first, then lazy operations
        # scan_csv requires a file path, not StringIO
        df = pl.read_csv(StringIO(csv_data))
        lazy_df = df.lazy()  # Convert to LazyFrame AFTER reading

        # Get row count efficiently
        original_count = len(df)
        logger.info(f"ByteMe returned {original_count} total offers")

        # Step 2: Build the optimization pipeline - data type safe filtering
        optimized_pipeline = (
            lazy_df
            # Do deduplication FIRST before any filtering
            .unique(subset=['productId'], keep='first')  # Deduplication first!
            # Only filter out null productIds (no string comparison for numeric columns)
            .filter(pl.col('productId').is_not_null())
            .with_columns([
                # All transformations in one pass - MAXIMUM EFFICIENCY
                pl.col('speed').cast(pl.Int32, strict=False).fill_null(0).alias('speed_clean'),
                pl.col('monthlyCostInCent').cast(pl.Int32, strict=False).fill_null(0).alias('monthly_cost_clean'),
                pl.col('afterTwoYearsMonthlyCost').cast(pl.Int32, strict=False).fill_null(0).alias(
                    'after_two_years_clean'),
                pl.col('durationInMonths').cast(pl.Int32, strict=False).fill_null(0).alias('duration_clean'),
                pl.col('voucherValue').cast(pl.Int32, strict=False).fill_null(0).alias('voucher_value_clean'),

                # String operations - optimized
                pl.col('providerName').fill_null('Unknown').alias('provider_clean'),
                pl.col('connectionType').fill_null('Unknown').alias('connection_clean'),
                pl.col('voucherType').fill_null('').alias('voucher_type_clean'),

                # Boolean operations - type-safe
                pl.col('installationService').cast(pl.Utf8).str.to_lowercase().is_in(['true', '1', 'yes']).alias(
                    'installation_clean'),
                pl.col('tv').fill_null('').str.strip_chars().ne('').alias('tv_included_clean')
            ])
            .select([
                # Only select columns we actually need - reduces memory
                'productId',
                'provider_clean',
                'speed_clean',
                'monthly_cost_clean',
                'after_two_years_clean',
                'duration_clean',
                'connection_clean',
                'installation_clean',
                'tv_included_clean',
                'voucher_type_clean',
                'voucher_value_clean'
            ])
        )

        # Step 3: Execute the ENTIRE optimized pipeline in ONE go! ⚡
        logger.info("🔥 Executing optimized lazy pipeline...")
        start_time = time.time()

        result_df = optimized_pipeline.collect()

        execution_time = (time.time() - start_time) * 1000  # ms
        logger.info(f"⚡ Lazy execution completed in {execution_time:.1f}ms")

        unique_count = len(result_df)
        logger.info(f"After optimization: {unique_count} unique valid offers")

        # Step 4: Convert to objects (this is now the bottleneck, not data processing!)
        offers = []
        for row in result_df.to_dicts():
            offers.append(UnifiedOffer(
                provider_name=row['provider_clean'],
                product_id=str(row['productId']),
                speed_mbps=row['speed_clean'],
                monthly_cost_cents=row['monthly_cost_clean'],
                after_two_years_cost_cents=row['after_two_years_clean'],
                contract_duration_months=row['duration_clean'],
                connection_type=row['connection_clean'],
                installation_service=row['installation_clean'],
                tv_included=row['tv_included_clean'],
                voucher_type=row['voucher_type_clean'],
                voucher_value=row['voucher_value_clean']
            ))

        logger.info(f"🚀 LAZY Polars processed {len(offers)} offers with query optimization")
        return offers

    except Exception as e:
        logger.error(f"Lazy Polars parsing failed: {e}")
        # Fallback to regular Polars
        return parse_byteme_csv_polars(csv_data)


def parse_byteme_csv_polars(csv_data: str) -> List[UnifiedOffer]:
    """REGULAR Polars parsing (fallback)"""
    try:
        logger.info("🚀 Using regular Polars for CSV parsing")

        df = pl.read_csv(StringIO(csv_data))
        original_count = len(df)
        logger.info(f"ByteMe returned {original_count} total offers")

        df_unique = df.unique(subset=['productId'], keep='first')
        unique_count = len(df_unique)
        logger.info(f"After deduplication: {unique_count} unique offers")

        df_clean = df_unique.with_columns([
            pl.col('speed').cast(pl.Int32, strict=False).fill_null(0).alias('speed_clean'),
            pl.col('monthlyCostInCent').cast(pl.Int32, strict=False).fill_null(0).alias('monthly_cost_clean'),
            pl.col('afterTwoYearsMonthlyCost').cast(pl.Int32, strict=False).fill_null(0).alias('after_two_years_clean'),
            pl.col('durationInMonths').cast(pl.Int32, strict=False).fill_null(0).alias('duration_clean'),
            pl.col('voucherValue').cast(pl.Int32, strict=False).fill_null(0).alias('voucher_value_clean'),
            pl.col('installationService').cast(pl.Utf8).str.to_lowercase().is_in(['true', '1', 'yes']).alias(
                'installation_clean'),
            pl.col('providerName').fill_null('Unknown').alias('provider_clean'),
            pl.col('connectionType').fill_null('Unknown').alias('connection_clean'),
            pl.col('voucherType').fill_null('').alias('voucher_type_clean'),
            pl.col('tv').fill_null('').str.strip_chars().ne('').alias('tv_included_clean')
        ])

        offers = []
        for row in df_clean.to_dicts():
            offers.append(UnifiedOffer(
                provider_name=row['provider_clean'],
                product_id=str(row['productId']),
                speed_mbps=row['speed_clean'],
                monthly_cost_cents=row['monthly_cost_clean'],
                after_two_years_cost_cents=row['after_two_years_clean'],
                contract_duration_months=row['duration_clean'],
                connection_type=row['connection_clean'],
                installation_service=row['installation_clean'],
                tv_included=row['tv_included_clean'],
                voucher_type=row['voucher_type_clean'],
                voucher_value=row['voucher_value_clean']
            ))

        logger.info(f"🚀 Regular Polars processed {len(offers)} offers")
        return offers

    except Exception as e:
        logger.error(f"Regular Polars parsing failed: {e}")
        return parse_byteme_csv_pure_python(csv_data)


def parse_byteme_csv_pure_python(csv_data: str) -> List[UnifiedOffer]:
    """Pure Python fallback parsing"""
    try:
        logger.info("🐍 Using pure Python for CSV parsing")

        lines = csv_data.strip().split('\n')
        if len(lines) < 2:
            return []

        header = [col.strip() for col in lines[0].split(',')]
        col_map = {col: i for i, col in enumerate(header)}

        offers = []
        seen_ids = set()

        for line in lines[1:]:
            fields = [field.strip() for field in line.split(',')]
            if len(fields) != len(header):
                continue

            product_id = fields[col_map.get('productId', 0)]
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            offers.append(UnifiedOffer(
                provider_name=fields[col_map.get('providerName', 1)] or 'Unknown',
                product_id=product_id,
                speed_mbps=safe_int(fields[col_map.get('speed', 2)]),
                monthly_cost_cents=safe_int(fields[col_map.get('monthlyCostInCent', 3)]),
                after_two_years_cost_cents=safe_int(fields[col_map.get('afterTwoYearsMonthlyCost', 4)]),
                contract_duration_months=safe_int(fields[col_map.get('durationInMonths', 5)]),
                connection_type=fields[col_map.get('connectionType', 6)] or 'Unknown',
                installation_service=safe_bool(fields[col_map.get('installationService', 7)]),
                tv_included=bool(fields[col_map.get('tv', 8)].strip()),
                voucher_type=fields[col_map.get('voucherType', 10)] or '',
                voucher_value=safe_int(fields[col_map.get('voucherValue', 11)])
            ))

        logger.info(f"🐍 Pure Python processed {len(offers)} offers")
        return offers

    except Exception as e:
        logger.error(f"Pure Python parsing failed: {e}")
        return []


def parse_byteme_csv_ultra_optimized(csv_data: str) -> List[UnifiedOffer]:
    """Parse ByteMe CSV with the fastest available method"""

    if HAS_POLARS:
        # Try lazy first (should be fastest)
        start_time = time.time()
        result = parse_byteme_csv_lazy_optimized(csv_data)
        total_time = (time.time() - start_time) * 1000
        logger.info(f"🚀 Total processing time: {total_time:.1f}ms")
        return result
    else:
        return parse_byteme_csv_pure_python(csv_data)


def send_to_websocket(connection_id: str, message: Dict[str, Any]) -> bool:
    """OPTIMIZED WebSocket sender with best available JSON serializer"""
    try:
        if HAS_ORJSON:
            json_data = orjson.dumps(message)
            if isinstance(json_data, bytes):
                data = json_data
            else:
                data = json_data.encode('utf-8')
        else:
            json_str = json.dumps(message, separators=(',', ':'))
            data = json_str.encode('utf-8')

        apigateway_management.post_to_connection(
            ConnectionId=connection_id,
            Data=data
        )
        logger.info(f"⚡ Message sent to WebSocket {connection_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WebSocket message to {connection_id}: {e}")
        return False


def store_results_in_db(request_id: str, provider_name: str, offers_data: List[Dict], share_token: str,
                        session_id: str = None, address: Dict = None) -> str:
    """Store results in DynamoDB and return share token"""
    if not results_table:
        logger.warning("DynamoDB not configured, skipping storage")
        return None

    try:
        # Calculate expiry (30 days from now)
        expires_at = int((datetime.utcnow() + timedelta(days=30)).timestamp())

        offers_data_decimal = convert_floats_to_decimal(offers_data)
        address_decimal = convert_floats_to_decimal(address or {})

        # Store in DynamoDB
        item = {
            'request_id': request_id,
            'provider_name': provider_name,
            'share_token': share_token,
            'session_id': session_id or 'anonymous',
            'search_date': datetime.utcnow().strftime('%Y-%m-%d'),
            'timestamp': datetime.utcnow().isoformat(),
            'expires_at': expires_at,
            'offers': offers_data_decimal,
            'total_offers': len(offers_data),
            'address': address_decimal or {},
            'performance_metrics': {
                'processing_method': 'lazy_polars' if HAS_POLARS else 'pure_python',
                'libraries_used': {
                    'polars': HAS_POLARS,
                    'orjson': HAS_ORJSON
                }
            }
        }

        results_table.put_item(Item=item)

        logger.info(f"✅ Stored {len(offers_data)} offers in DB with share token: {share_token}")
        return share_token

    except Exception as e:
        logger.error(f"Failed to store results in DB: {e}")
        return None


def update_analytics(provider_name: str, offer_count: int, processing_time_ms: float):
    """Update analytics data"""
    if not analytics_table:
        return

    try:
        today = datetime.utcnow().strftime('%Y-%m-%d')

        processing_time_decimal = Decimal(str(processing_time_ms))

        # Update daily provider stats
        analytics_table.update_item(
            Key={
                'metric_type': f'provider_daily_{provider_name}',
                'time_period': today
            },
            UpdateExpression='ADD search_count :inc, total_offers :offers, total_processing_time_ms :time',
            ExpressionAttributeValues={
                ':inc': 1,
                ':offers': offer_count,
                ':time': processing_time_decimal
            }
        )

        # Update overall daily stats
        analytics_table.update_item(
            Key={
                'metric_type': 'daily_searches',
                'time_period': today
            },
            UpdateExpression='ADD total_searches :inc, total_offers :offers',
            ExpressionAttributeValues={
                ':inc': 1,
                ':offers': offer_count
            }
        )

        logger.info(f"📊 Updated analytics for {provider_name}")

    except Exception as e:
        logger.error(f"Failed to update analytics: {e}")


def lambda_handler(event, context):
    """🚀 LAZY OPTIMIZED Results Handler"""

    # Handle warmer requests efficiently - exit early
    if event.get('warmer'):
        logger.info("🔥 Lambda warmer ping received - keeping function warm")
        # Import libraries to ensure they're loaded in memory
        if HAS_POLARS:
            logger.info("✅ Polars loaded and ready")
        if HAS_ORJSON:
            logger.info("✅ orjson loaded and ready")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Lambda warmed successfully",
                "timestamp": datetime.utcnow().isoformat(),
                "libraries": {
                    "polars": HAS_POLARS,
                    "orjson": HAS_ORJSON
                }
            })
        }

    logger.info("⚡ LAZY OPTIMIZED Results Handler started")
    logger.info(f"Libraries available: orjson={HAS_ORJSON}, polars={HAS_POLARS}")

    for record in event.get('Records', []):
        try:
            # Fast JSON parsing
            if HAS_ORJSON:
                message_body = orjson.loads(record.get('body', '{}'))
            else:
                message_body = json.loads(record.get('body', '{}'))

            logger.info(f"🔥 Processing result for request: {message_body.get('request_id')}")

            request_id = message_body.get('request_id')
            connection_id = message_body.get('connection_id')
            provider_name = message_body.get('provider_name')
            status = message_body.get('status')
            share_token = message_body.get('share_token')
            session_id = message_body.get('session_id')  # From search request
            address = message_body.get('address')  # From search request

            if status == 'success':
                raw_response = message_body.get('raw_response', '')

                if provider_name == 'byteme':
                    start_time = time.time()
                    offers = parse_byteme_csv_ultra_optimized(raw_response)
                    processing_time = (time.time() - start_time) * 1000
                    offers_data = [offer.to_dict_optimized() for offer in offers]

                elif provider_name == 'verbyndich':
                    start_time = time.time()
                    offers = parse_verbyndich_offers(raw_response)
                    processing_time = (time.time() - start_time) * 1000
                    offers_data = [offer.to_dict_optimized() for offer in offers]

                elif provider_name == 'servus_speed':
                    start_time = time.time()
                    offers = parse_servus_speed_json(raw_response)
                    processing_time = (time.time() - start_time) * 1000
                    offers_data = [offer.to_dict_optimized() for offer in offers]

                elif provider_name == 'webwunder':
                    start_time = time.time()
                    # raw_response is an array of connection type responses from Step Functions
                    offers = parse_webwunder_aggregated(raw_response)
                    processing_time = (time.time() - start_time) * 1000
                    offers_data = [offer.to_dict_optimized() for offer in offers]

                    # Log metadata about connection type processing
                    metadata = message_body.get('metadata', {})
                    logger.info(
                        f"📊 WebWunder processed {metadata.get('successful_connections', 0)}/{metadata.get('connection_types_attempted', 3)} connection types")

                elif provider_name == 'ping_perfect':
                    start_time = time.time()
                    # raw_response is an array of call responses (fiber + non-fiber)
                    offers = parse_ping_perfect_aggregated(raw_response)
                    processing_time = (time.time() - start_time) * 1000
                    offers_data = [offer.to_dict_optimized() for offer in offers]

                    # Log metadata about call processing
                    metadata = message_body.get('metadata', {})
                    logger.info(
                        f"📊 Ping Perfect processed {metadata.get('successful_calls', 0)}/{metadata.get('call_types_attempted', 2)} call types")

                else:
                    logger.warning(f"Unknown provider: {provider_name}")
                    continue

                # 🗄️ STORE IN DATABASE
                final_share_token = store_results_in_db(
                    request_id=request_id,
                    provider_name=provider_name,
                    offers_data=offers_data,
                    session_id=session_id,
                    share_token=share_token,
                    address=address
                )

                # 📊 UPDATE ANALYTICS
                update_analytics(provider_name, len(offers_data), processing_time)

                websocket_message = {
                    'type': 'PROVIDER_RESULT',
                    'request_id': request_id,
                    'provider': provider_name,
                    'status': 'success',
                    'offers': offers_data,
                    'total_offers': len(offers_data),
                    'timestamp': datetime.utcnow().isoformat(),
                    'processing_method': 'lazy_polars' if HAS_POLARS else 'pure_python',
                    'share_token': final_share_token,  # 🔗 SHARE LINK!
                    'share_url': f"/share/{final_share_token}" if final_share_token else None,
                    'performance': {
                        'processing_time_ms': round(processing_time, 1)
                    }
                }

            else:
                websocket_message = {
                    'type': 'PROVIDER_RESULT',
                    'request_id': request_id,
                    'provider': provider_name,
                    'status': 'failed',
                    'error': message_body.get('error_details', 'Unknown error'),
                    'offers': [],
                    'timestamp': datetime.utcnow().isoformat()
                }

            send_to_websocket(connection_id, websocket_message)

        except Exception as e:
            logger.error(f"🔥 Error processing record: {e}")
            continue

    return {"statusCode": 200, "body": "🚀 LAZY OPTIMIZED results processed"}


def convert_floats_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj


def parse_servus_speed_json(json_data: List[Dict]) -> List[UnifiedOffer]:
    """Parse Servus Speed JSON response to unified offer format"""
    try:
        logger.info("🚀 Processing Servus Speed JSON data")

        if not isinstance(json_data, list):
            logger.warning("Servus Speed data is not a list, skipping")
            return []

        offers = []
        processed_count = 0

        for product_data in json_data:
            try:
                if not isinstance(product_data, dict) or 'servusSpeedProduct' not in product_data:
                    continue

                product = product_data['servusSpeedProduct']

                # Extract product info
                product_info = product.get('productInfo', {})
                pricing_details = product.get('pricingDetails', {})

                # Monthly cost is already discounted according to the user
                monthly_cost_cents = safe_int(pricing_details.get('monthlyCostInCent', 0))

                # For Servus Speed, after two years cost is same as monthly (no promotional pricing)
                after_two_years_cost = monthly_cost_cents

                # Get discount value for voucher info (even though price is already discounted)
                discount_cents = safe_int(product.get('discount', 0))

                offer = UnifiedOffer(
                    provider_name=safe_string(product.get('providerName', 'Servus Speed')),
                    product_id=f"servus_{processed_count}",  # Generate unique ID
                    speed_mbps=safe_int(product_info.get('speed', 0)),
                    monthly_cost_cents=monthly_cost_cents,  # Already discounted
                    after_two_years_cost_cents=after_two_years_cost,
                    contract_duration_months=safe_int(product_info.get('contractDurationInMonths', 0)),
                    connection_type=safe_string(product_info.get('connectionType', 'Unknown')),
                    installation_service=safe_bool(pricing_details.get('installationService', False)),
                    tv_included=bool(product_info.get('tv', '').strip()),  # Has TV if not empty
                    voucher_type='absolute' if discount_cents > 0 else '',
                    voucher_value=discount_cents  # Show original discount amount
                )

                offers.append(offer)
                processed_count += 1

            except Exception as e:
                logger.warning(f"Error processing Servus Speed product: {e}")
                continue

        logger.info(f"🚀 Servus Speed processed {len(offers)} offers")
        return offers

    except Exception as e:
        logger.error(f"Error parsing Servus Speed JSON: {e}")
        return []


def safe_string(value: Any, default: str = '') -> str:
    """Safely convert value to string"""
    if value is None:
        return default
    return str(value).strip()

# webwunder!


def parse_webwunder_aggregated(aggregated_response: List[Dict]) -> List[UnifiedOffer]:
    """Parse WebWunder aggregated response from multiple connection types"""
    all_offers = []

    try:
        logger.info(f"🔍 Parsing WebWunder aggregated response with {len(aggregated_response)} connection types")

        for connection_data in aggregated_response:
            connection_type = connection_data.get('connection_type', 'Unknown')
            xml_response = connection_data.get('response_data', '')

            if not xml_response:
                logger.warning(f"⚠️ No response data for {connection_type}")
                continue

            logger.info(f"🔄 Processing {connection_type} connection type")

            # Parse this connection type's XML response
            connection_offers = parse_webwunder_xml_single(xml_response, connection_type)
            all_offers.extend(connection_offers)

            logger.info(f"✅ Found {len(connection_offers)} offers for {connection_type}")

        logger.info(f"🚀 Total WebWunder offers across all connection types: {len(all_offers)}")
        return all_offers

    except Exception as e:
        logger.error(f"⚠️ Error parsing WebWunder aggregated response: {e}")
        return []


def parse_webwunder_xml_single(xml_response: str, connection_type: str = "Unknown") -> List[UnifiedOffer]:
    """Parse single WebWunder SOAP XML response into UnifiedOffer objects"""
    offers = []

    try:
        root = ET.fromstring(xml_response)

        # Register namespaces to handle XML properly
        namespaces = {
            'ns2': 'http://webwunder.gendev7.check24.fun/offerservice',
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/'
        }

        # Find all product elements
        product_elements = root.findall('.//ns2:products', namespaces)

        if not product_elements:
            # Fallback: try without namespace prefix
            product_elements = root.findall('.//products')

        logger.info(f"🔍 Found {len(product_elements)} products for {connection_type}")

        for i, product_elem in enumerate(product_elements, 1):
            try:
                # Extract basic product info with namespace handling
                product_id = get_xml_text(product_elem, 'productId', namespaces)
                provider_name = get_xml_text(product_elem, 'providerName', namespaces)

                # Find productInfo element
                product_info = product_elem.find('ns2:productInfo', namespaces)
                if product_info is None:
                    product_info = product_elem.find('productInfo')

                if product_info is not None:
                    # Extract product details based on your test script
                    speed = safe_int(get_xml_text(product_info, 'speed', namespaces))
                    monthly_cost = safe_int(get_xml_text(product_info, 'monthlyCostInCent', namespaces))
                    monthly_cost_25th = safe_int(
                        get_xml_text(product_info, 'monthlyCostInCentFrom25thMonth', namespaces))
                    contract_duration = safe_int(get_xml_text(product_info, 'contractDurationInMonths', namespaces))
                    xml_connection_type = get_xml_text(product_info, 'connectionType', namespaces)

                    # Use connection type from Step Functions if XML doesn't have it
                    raw_connection_type = xml_connection_type or connection_type or 'Unknown'
                    final_connection_type = normalize_connection_type(raw_connection_type)

                    # Handle voucher information
                    voucher_elem = product_info.find('ns2:voucher', namespaces)
                    if voucher_elem is None:
                        voucher_elem = product_info.find('voucher')

                    voucher_type = ""
                    voucher_value = 0

                    if voucher_elem is not None:
                        voucher_percentage = get_xml_text(voucher_elem, 'percentage', namespaces)
                        voucher_max_discount = safe_int(get_xml_text(voucher_elem, 'maxDiscountInCent', namespaces))

                        if voucher_percentage:
                            voucher_type = f"{voucher_percentage}% discount"
                            voucher_value = voucher_max_discount

                    # Create UnifiedOffer object
                    offer = UnifiedOffer(
                        provider_name=provider_name or 'WebWunder',
                        product_id=product_id or f"webwunder_{connection_type.lower()}_{i}",
                        speed_mbps=speed,
                        monthly_cost_cents=monthly_cost,
                        after_two_years_cost_cents=monthly_cost_25th or monthly_cost,
                        contract_duration_months=contract_duration,
                        connection_type=final_connection_type,
                        installation_service=True,  # Installation doesn't matter per your test
                        tv_included=False,  # Not specified in WebWunder API
                        voucher_type=voucher_type,
                        voucher_value=voucher_value
                    )

                    offers.append(offer)

                    logger.info(
                        f"📦 Parsed {connection_type} offer {i}: {provider_name} - {speed} Mbps - {monthly_cost / 100:.2f}€")

            except Exception as e:
                logger.error(f"⚠️ Error parsing {connection_type} product {i}: {e}")
                continue

        return offers

    except ET.ParseError as e:
        logger.error(f"⚠️ WebWunder XML parsing error for {connection_type}: {e}")
        logger.error(f"XML content preview: {xml_response[:500]}...")
        return []
    except Exception as e:
        logger.error(f"⚠️ Error parsing WebWunder XML for {connection_type}: {e}")
        return []


def get_xml_text(element: ET.Element, tag_name: str, namespaces: Dict[str, str]) -> str:
    """Helper function to extract text from XML element with namespace fallback"""
    try:
        # Try with namespace first
        elem = element.find(f'ns2:{tag_name}', namespaces)
        if elem is not None and elem.text:
            return elem.text.strip()

        # Fallback: try without namespace
        elem = element.find(tag_name)
        if elem is not None and elem.text:
            return elem.text.strip()

        return ""
    except Exception:
        return ""


def normalize_connection_type(connection_type: str) -> str:
    """Normalize connection type to consistent format"""
    if not connection_type:
        return 'Unknown'

    # Convert to consistent format: Fiber, DSL, Cable
    connection_type_upper = connection_type.upper()

    if connection_type_upper == 'FIBER':
        return 'Fiber'
    elif connection_type_upper == 'DSL':
        return 'DSL'  # DSL bleibt komplett groß
    elif connection_type_upper == 'CABLE':
        return 'Cable'
    else:
        # Fallback: Capitalize first letter only
        return connection_type.capitalize()


# ping perfect

def parse_ping_perfect_aggregated(aggregated_response: List[Dict]) -> List[UnifiedOffer]:
    """Parse Ping Perfect aggregated response from fiber and non-fiber calls"""
    all_offers = []

    try:
        logger.info(f"🔍 Parsing Ping Perfect aggregated response with {len(aggregated_response)} call types")

        for call_data in aggregated_response:
            call_type = call_data.get('call_type', 'unknown')
            wants_fiber = call_data.get('wants_fiber', False)
            offers_data = call_data.get('offers', [])

            if not offers_data:
                logger.warning(f"⚠️ No offers data for call_type={call_type}")
                continue

            logger.info(f"🔄 Processing {call_type} call (wantsFiber={wants_fiber}) with {len(offers_data)} offers")

            # Parse this call's offers
            call_offers = parse_ping_perfect_offers(offers_data)
            all_offers.extend(call_offers)

            logger.info(f"✅ Parsed {len(call_offers)} offers for {call_type}")

        logger.info(f"🚀 Total Ping Perfect offers across all calls: {len(all_offers)}")
        return all_offers

    except Exception as e:
        logger.error(f"⚠️ Error parsing Ping Perfect aggregated response: {e}")
        return []


def parse_ping_perfect_offers(offers_data: List[Dict]) -> List[UnifiedOffer]:
    """Parse Ping Perfect offers array into UnifiedOffer objects"""
    offers = []

    try:
        for i, offer_data in enumerate(offers_data, 1):
            try:
                # Extract data according to Ping Perfect response format
                provider_name = offer_data.get('providerName', 'Ping Perfect')

                # Product info
                product_info = offer_data.get('productInfo', {})
                speed = safe_int(product_info.get('speed', 0))
                contract_duration = safe_int(product_info.get('contractDurationInMonths', 0))
                connection_type = product_info.get('connectionType', 'Unknown')
                tv_package = product_info.get('tv', '')

                # Pricing info
                pricing_details = offer_data.get('pricingDetails', {})
                monthly_cost = safe_int(pricing_details.get('monthlyCostInCent', 0))
                installation_service = pricing_details.get('installationService', 'no')

                # Normalize connection type to match other providers
                normalized_connection_type = normalize_connection_type(connection_type)

                # Create UnifiedOffer object
                offer = UnifiedOffer(
                    provider_name=provider_name,
                    product_id=f"ping_perfect_{normalized_connection_type.lower()}_{i}",
                    speed_mbps=speed,
                    monthly_cost_cents=monthly_cost,
                    after_two_years_cost_cents=monthly_cost,  # Ping Perfect doesn't specify different pricing
                    contract_duration_months=contract_duration,
                    connection_type=normalized_connection_type,
                    installation_service=installation_service.lower() in ['yes', 'true', '1'],
                    tv_included=bool(tv_package.strip()),  # True if TV package is specified
                    voucher_type="",  # Ping Perfect doesn't seem to have vouchers
                    voucher_value=0
                )

                offers.append(offer)

                logger.info(
                    f"📦 Parsed Ping Perfect offer {i}: {provider_name} - {speed} Mbps - {monthly_cost / 100:.2f}€ - {normalized_connection_type}")

            except Exception as e:
                logger.error(f"⚠️ Error parsing Ping Perfect offer {i}: {e}")
                continue

        return offers

    except Exception as e:
        logger.error(f"⚠️ Error parsing Ping Perfect offers: {e}")
        return []