"""AWS DynamoDB repository implementations."""

import boto3
from botocore.exceptions import ClientError

try:
    from boto3.dynamodb.conditions import Key, Attr
except ImportError:
    # Mock for testing environments
    Key = lambda x: x
    Attr = lambda x: x
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging

from ...application.interfaces.repositories import ISearchResultRepository, IConnectionRepository, IProviderOfferRepository
from ...domain.entities.search_result import SearchResult
from ...domain.entities.connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType
from ...domain.entities.provider_offer import ProviderOffer, ConnectionType, OfferStatus
from ...domain.value_objects.address import Address


logger = logging.getLogger(__name__)


class DynamoDBTypeConverter:
    """Utility class for converting between Python types and DynamoDB types."""

    @staticmethod
    def to_dynamodb_item(obj: Any) -> Any:
        """Convert Python object to DynamoDB-compatible format."""
        if isinstance(obj, dict):
            return {k: DynamoDBTypeConverter.to_dynamodb_item(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DynamoDBTypeConverter.to_dynamodb_item(item) for item in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            # Handle dataclass objects
            return DynamoDBTypeConverter.to_dynamodb_item(obj.__dict__)
        elif hasattr(obj, "value"):
            # Handle enum objects
            return obj.value
        else:
            return obj

    @staticmethod
    def from_dynamodb_item(obj: Any) -> Any:
        """Convert DynamoDB item to Python object."""
        if isinstance(obj, dict):
            return {k: DynamoDBTypeConverter.from_dynamodb_item(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DynamoDBTypeConverter.from_dynamodb_item(item) for item in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj


class AWSDynamoDBSearchResultRepository(ISearchResultRepository):
    """AWS DynamoDB implementation of search result repository."""

    def __init__(self, table_name: str, region_name: str = "eu-central-1"):
        """
        Initialize DynamoDB search result repository.

        Args:
            table_name: Name of the DynamoDB table
            region_name: AWS region name
        """
        self.table_name = table_name
        self.region_name = region_name
        self._dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._table = self._dynamodb.Table(table_name)

        logger.info(f"Initialized DynamoDB SearchResult repository with table: {table_name}")

    async def save_result(self, result: SearchResult) -> str:
        """Save search result and return share token."""
        try:
            # Convert to DynamoDB format
            item = {
                "request_id": result.request_id,
                "share_token": result.share_token,
                "timestamp": result.timestamp.isoformat(),
                "expires_at": int(result.expires_at.timestamp()),
                "address": DynamoDBTypeConverter.to_dynamodb_item(result.address.__dict__),
                "offers": DynamoDBTypeConverter.to_dynamodb_item([offer.__dict__ for offer in result.offers]),
                "search_metadata": DynamoDBTypeConverter.to_dynamodb_item(result.search_metadata),
                "offer_count": len(result.offers),
                "provider_count": result.provider_count,
                "created_at": datetime.utcnow().isoformat(),
            }

            self._table.put_item(Item=item)

            logger.info(f"Saved search result with share token: {result.share_token}")
            return result.share_token

        except ClientError as e:
            logger.error(f"Failed to save search result: {e}")
            raise RuntimeError(f"Database error: {e}")

    async def get_result_by_share_token(self, share_token: str) -> Optional[SearchResult]:
        """Get search result by share token."""
        try:
            response = self._table.query(
                IndexName="ShareTokenIndex", KeyConditionExpression=Key("share_token").eq(share_token)
            )

            items = response.get("Items", [])
            if not items:
                return None

            # Aggregate results from multiple providers
            return self._build_search_result_from_items(items)

        except ClientError as e:
            logger.error(f"Failed to get result by share token {share_token}: {e}")
            return None

    async def get_result_by_request_id(self, request_id: str) -> Optional[SearchResult]:
        """Get search result by request ID."""
        try:
            response = self._table.query(KeyConditionExpression=Key("request_id").eq(request_id))

            items = response.get("Items", [])
            if not items:
                return None

            return self._build_search_result_from_items(items)

        except ClientError as e:
            logger.error(f"Failed to get result by request ID {request_id}: {e}")
            return None

    def _build_search_result_from_items(self, items: List[Dict[str, Any]]) -> SearchResult:
        """Build SearchResult entity from DynamoDB items."""
        # Use first item for metadata
        first_item = items[0]

        # Reconstruct address
        address_data = DynamoDBTypeConverter.from_dynamodb_item(first_item["address"])
        address = Address(**address_data)

        # Aggregate offers from all items
        all_offers = []
        for item in items:
            offers_data = DynamoDBTypeConverter.from_dynamodb_item(item.get("offers", []))
            for offer_data in offers_data:
                # Convert back to ProviderOffer
                offer_data["connection_type"] = ConnectionType(offer_data["connection_type"])
                offer_data["status"] = OfferStatus(offer_data["status"])
                offer_data["monthly_cost_euros"] = Decimal(str(offer_data["monthly_cost_euros"]))
                if offer_data.get("setup_fee_euros"):
                    offer_data["setup_fee_euros"] = Decimal(str(offer_data["setup_fee_euros"]))

                offer = ProviderOffer(**offer_data)
                all_offers.append(offer)

        # Create SearchResult
        search_result = SearchResult(
            request_id=first_item["request_id"],
            address=address,
            offers=all_offers,
            share_token=first_item["share_token"],
            timestamp=datetime.fromisoformat(first_item["timestamp"]),
            expires_at=datetime.fromtimestamp(first_item["expires_at"]),
            search_metadata=DynamoDBTypeConverter.from_dynamodb_item(first_item.get("search_metadata", {})),
        )

        return search_result

    async def update_result(self, result: SearchResult) -> bool:
        """Update an existing search result."""
        try:
            # For simplicity, we'll replace the entire item
            await self.save_result(result)
            return True

        except Exception as e:
            logger.error(f"Failed to update search result: {e}")
            return False

    async def delete_result(self, share_token: str) -> bool:
        """Delete a search result by share token."""
        try:
            # First get all items with this share token
            response = self._table.query(
                IndexName="ShareTokenIndex", KeyConditionExpression=Key("share_token").eq(share_token)
            )

            items = response.get("Items", [])

            # Delete all items
            for item in items:
                self._table.delete_item(Key={"request_id": item["request_id"]})

            logger.info(f"Deleted search result with share token: {share_token}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete search result: {e}")
            return False

    async def get_results_by_address(self, address: Address, limit: int = 10) -> List[SearchResult]:
        """Get recent search results for a specific address."""
        try:
            # This would require a GSI on address fields
            # For now, return empty list as this is complex to implement efficiently
            logger.warning("get_results_by_address not fully implemented - requires address GSI")
            return []

        except Exception as e:
            logger.error(f"Failed to get results by address: {e}")
            return []


class AWSDynamoDBConnectionRepository(IConnectionRepository):
    """AWS DynamoDB implementation of connection repository."""

    def __init__(self, table_name: str, region_name: str = "eu-central-1"):
        """
        Initialize DynamoDB connection repository.

        Args:
            table_name: Name of the DynamoDB table
            region_name: AWS region name
        """
        self.table_name = table_name
        self.region_name = region_name
        self._dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._table = self._dynamodb.Table(table_name)

        logger.info(f"Initialized DynamoDB Connection repository with table: {table_name}")

    async def save_connection(self, session: ConnectionSession) -> str:
        """Save connection session and return connection ID."""
        try:
            item = {
                "connection_id": session.connection_id,
                "connection_type": session.connection_type.value,
                "status": session.status.value,
                "connected_at": session.connected_at.isoformat() if session.connected_at else None,
                "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
                "disconnected_at": session.disconnected_at.isoformat() if session.disconnected_at else None,
                "client_info": DynamoDBTypeConverter.to_dynamodb_item(session.client_info),
                "session_data": DynamoDBTypeConverter.to_dynamodb_item(session.session_data),
                "subscribed_topics": list(session.subscribed_topics),
                "created_at": datetime.utcnow().isoformat(),
            }

            self._table.put_item(Item=item)

            logger.info(f"Saved connection session: {session.connection_id}")
            return session.connection_id

        except ClientError as e:
            logger.error(f"Failed to save connection session: {e}")
            raise RuntimeError(f"Database error: {e}")

    async def get_connection(self, connection_id: str) -> Optional[ConnectionSession]:
        """Get connection session by connection ID."""
        try:
            response = self._table.get_item(Key={"connection_id": connection_id})

            item = response.get("Item")
            if not item:
                return None

            # Convert back to ConnectionSession
            session = ConnectionSession(
                connection_id=item["connection_id"],
                connection_type=SessionConnectionType(item["connection_type"]),
                status=ConnectionStatus(item["status"]),
                connected_at=datetime.fromisoformat(item["connected_at"]) if item.get("connected_at") else None,
                last_activity_at=datetime.fromisoformat(item["last_activity_at"]) if item.get("last_activity_at") else None,
                disconnected_at=datetime.fromisoformat(item["disconnected_at"]) if item.get("disconnected_at") else None,
                client_info=DynamoDBTypeConverter.from_dynamodb_item(item.get("client_info", {})),
                session_data=DynamoDBTypeConverter.from_dynamodb_item(item.get("session_data", {})),
                subscribed_topics=set(item.get("subscribed_topics", [])),
            )

            return session

        except ClientError as e:
            logger.error(f"Failed to get connection {connection_id}: {e}")
            return None

    async def update_connection(self, session: ConnectionSession) -> bool:
        """Update an existing connection session."""
        try:
            await self.save_connection(session)
            return True

        except Exception as e:
            logger.error(f"Failed to update connection session: {e}")
            return False

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection session."""
        try:
            self._table.delete_item(Key={"connection_id": connection_id})

            logger.info(f"Deleted connection session: {connection_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete connection: {e}")
            return False

    async def get_active_connections(self) -> List[ConnectionSession]:
        """Get all active connection sessions."""
        try:
            response = self._table.scan(FilterExpression=Attr("status").eq(ConnectionStatus.CONNECTED.value))

            connections = []
            for item in response.get("Items", []):
                session = ConnectionSession(
                    connection_id=item["connection_id"],
                    connection_type=SessionConnectionType(item["connection_type"]),
                    status=ConnectionStatus(item["status"]),
                    connected_at=datetime.fromisoformat(item["connected_at"]) if item.get("connected_at") else None,
                    last_activity_at=(
                        datetime.fromisoformat(item["last_activity_at"]) if item.get("last_activity_at") else None
                    ),
                    disconnected_at=datetime.fromisoformat(item["disconnected_at"]) if item.get("disconnected_at") else None,
                    client_info=DynamoDBTypeConverter.from_dynamodb_item(item.get("client_info", {})),
                    session_data=DynamoDBTypeConverter.from_dynamodb_item(item.get("session_data", {})),
                    subscribed_topics=set(item.get("subscribed_topics", [])),
                )
                connections.append(session)

            return connections

        except ClientError as e:
            logger.error(f"Failed to get active connections: {e}")
            return []

    async def cleanup_expired_connections(self, timeout_minutes: int = 30) -> int:
        """Clean up expired/idle connections."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)

            response = self._table.scan(
                FilterExpression=Attr("last_activity_at").lt(cutoff_time.isoformat())
                & Attr("status").eq(ConnectionStatus.CONNECTED.value)
            )

            expired_connections = response.get("Items", [])

            # Update status to disconnected
            for item in expired_connections:
                self._table.update_item(
                    Key={"connection_id": item["connection_id"]},
                    UpdateExpression="SET #status = :status, disconnected_at = :disconnected_at",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": ConnectionStatus.DISCONNECTED.value,
                        ":disconnected_at": datetime.utcnow().isoformat(),
                    },
                )

            logger.info(f"Cleaned up {len(expired_connections)} expired connections")
            return len(expired_connections)

        except ClientError as e:
            logger.error(f"Failed to cleanup expired connections: {e}")
            return 0


class AWSDynamoDBProviderOfferRepository(IProviderOfferRepository):
    """AWS DynamoDB implementation of provider offer cache repository."""

    def __init__(self, table_name: str, region_name: str = "eu-central-1"):
        """
        Initialize DynamoDB provider offer repository.

        Args:
            table_name: Name of the DynamoDB table
            region_name: AWS region name
        """
        self.table_name = table_name
        self.region_name = region_name
        self._dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self._table = self._dynamodb.Table(table_name)

        logger.info(f"Initialized DynamoDB ProviderOffer repository with table: {table_name}")

    def _generate_cache_key(self, address: Address, provider_name: str) -> str:
        """Generate cache key for address and provider."""
        return f"{address.postal_code}#{address.house_number}#{provider_name}"

    async def save_offers(self, address: Address, provider_name: str, offers: List[ProviderOffer]) -> bool:
        """Save provider offers for an address."""
        try:
            cache_key = self._generate_cache_key(address, provider_name)

            item = {
                "cache_key": cache_key,
                "address": DynamoDBTypeConverter.to_dynamodb_item(address.__dict__),
                "provider_name": provider_name,
                "offers": DynamoDBTypeConverter.to_dynamodb_item([offer.__dict__ for offer in offers]),
                "offer_count": len(offers),
                "cached_at": datetime.utcnow().isoformat(),
                "expires_at": int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
            }

            self._table.put_item(Item=item)

            logger.info(f"Cached {len(offers)} offers for {provider_name} at {address.full_address}")
            return True

        except ClientError as e:
            logger.error(f"Failed to save cached offers: {e}")
            return False

    async def get_cached_offers(
        self, address: Address, provider_name: str, max_age_hours: int = 24
    ) -> Optional[List[ProviderOffer]]:
        """Get cached offers for an address and provider."""
        try:
            cache_key = self._generate_cache_key(address, provider_name)

            response = self._table.get_item(Key={"cache_key": cache_key})

            item = response.get("Item")
            if not item:
                return None

            # Check if cache is expired
            cached_at = datetime.fromisoformat(item["cached_at"])
            if datetime.utcnow() - cached_at > timedelta(hours=max_age_hours):
                logger.info(f"Cache expired for {provider_name} at {address.full_address}")
                return None

            # Convert back to ProviderOffer objects
            offers_data = DynamoDBTypeConverter.from_dynamodb_item(item["offers"])
            offers = []

            for offer_data in offers_data:
                offer_data["connection_type"] = ConnectionType(offer_data["connection_type"])
                offer_data["status"] = OfferStatus(offer_data["status"])
                offer_data["monthly_cost_euros"] = Decimal(str(offer_data["monthly_cost_euros"]))
                if offer_data.get("setup_fee_euros"):
                    offer_data["setup_fee_euros"] = Decimal(str(offer_data["setup_fee_euros"]))

                offer = ProviderOffer(**offer_data)
                offers.append(offer)

            logger.info(f"Retrieved {len(offers)} cached offers for {provider_name}")
            return offers

        except ClientError as e:
            logger.error(f"Failed to get cached offers: {e}")
            return None

    async def invalidate_cache(self, address: Address, provider_name: Optional[str] = None) -> bool:
        """Invalidate cached offers for an address."""
        try:
            if provider_name:
                # Invalidate specific provider
                cache_key = self._generate_cache_key(address, provider_name)
                self._table.delete_item(Key={"cache_key": cache_key})
                logger.info(f"Invalidated cache for {provider_name} at {address.full_address}")
            else:
                # Invalidate all providers for this address
                # This would require a scan or GSI - simplified implementation
                logger.warning("Invalidating all providers for address not fully implemented")

            return True

        except ClientError as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False
