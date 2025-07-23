"""Search result entity representing a collection of provider offers for an address."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4
import secrets
from ..value_objects.address import Address
from .provider_offer import ProviderOffer, ConnectionType


@dataclass
class SearchResult:
    """Entity representing search results for internet offers at a specific address."""

    request_id: str
    address: Address
    offers: List[ProviderOffer] = field(default_factory=list)
    share_token: Optional[str] = None
    timestamp: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    search_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default values and validate the search result."""
        # Set default timestamp if not provided
        if self.timestamp is None:
            object.__setattr__(self, "timestamp", datetime.utcnow())

        # Set default expiration (30 days from creation)
        if self.expires_at is None:
            object.__setattr__(self, "expires_at", self.timestamp + timedelta(days=30))

        # Generate share token if not provided
        if self.share_token is None:
            object.__setattr__(self, "share_token", self._generate_share_token())

        self._validate()

    def _validate(self) -> None:
        """Validate search result data."""
        if not self.request_id or not self.request_id.strip():
            raise ValueError("Request ID cannot be empty")

        if not isinstance(self.address, Address):
            raise ValueError("Address must be a valid Address value object")

        if not isinstance(self.offers, list):
            raise ValueError("Offers must be a list")

        # Validate all offers are ProviderOffer instances
        for offer in self.offers:
            if not isinstance(offer, ProviderOffer):
                raise ValueError("All offers must be ProviderOffer instances")

        if self.expires_at <= self.timestamp:
            raise ValueError("Expiration date must be after timestamp")

        if len(self.share_token) < 8:
            raise ValueError("Share token must be at least 8 characters long")

    def _generate_share_token(self) -> str:
        """Generate a secure share token."""
        return secrets.token_urlsafe(16)

    @classmethod
    def create_new(cls, address: Address, request_id: Optional[str] = None) -> "SearchResult":
        """Create a new search result with generated request ID."""
        if request_id is None:
            request_id = str(uuid4())

        return cls(request_id=request_id, address=address)

    def add_offer(self, offer: ProviderOffer) -> None:
        """Add a provider offer to the search results."""
        if not isinstance(offer, ProviderOffer):
            raise ValueError("Offer must be a ProviderOffer instance")

        # Check for duplicate offers from the same provider
        existing_offer = self.get_offer_by_provider_and_product(offer.provider_name, offer.product_id)
        if existing_offer:
            raise ValueError(f"Offer from {offer.provider_name} with product {offer.product_id} already exists")

        self.offers.append(offer)

    def remove_offer(self, provider_name: str, product_id: str) -> bool:
        """Remove an offer by provider name and product ID."""
        for i, offer in enumerate(self.offers):
            if offer.provider_name == provider_name and offer.product_id == product_id:
                self.offers.pop(i)
                return True
        return False

    def get_offer_by_provider_and_product(self, provider_name: str, product_id: str) -> Optional[ProviderOffer]:
        """Get an offer by provider name and product ID."""
        for offer in self.offers:
            if offer.provider_name == provider_name and offer.product_id == product_id:
                return offer
        return None

    def get_offers_by_provider(self, provider_name: str) -> List[ProviderOffer]:
        """Get all offers from a specific provider."""
        return [offer for offer in self.offers if offer.provider_name == provider_name]

    def get_offers_by_connection_type(self, connection_type: ConnectionType) -> List[ProviderOffer]:
        """Get all offers of a specific connection type."""
        return [offer for offer in self.offers if offer.connection_type == connection_type]

    def get_available_offers(self) -> List[ProviderOffer]:
        """Get only available offers."""
        return [offer for offer in self.offers if offer.is_available]

    def get_cheapest_offer(self) -> Optional[ProviderOffer]:
        """Get the cheapest available offer by monthly cost."""
        available_offers = self.get_available_offers()
        if not available_offers:
            return None

        return min(available_offers, key=lambda offer: offer.monthly_cost_euros)

    def get_fastest_offer(self) -> Optional[ProviderOffer]:
        """Get the fastest available offer by download speed."""
        available_offers = self.get_available_offers()
        if not available_offers:
            return None

        return max(available_offers, key=lambda offer: offer.speed_download_mbps)

    def get_best_value_offer(self) -> Optional[ProviderOffer]:
        """Get the best value offer (lowest cost per Mbps)."""
        available_offers = self.get_available_offers()
        if not available_offers:
            return None

        return min(available_offers, key=lambda offer: offer.calculate_monthly_cost_per_mbps())

    def get_fiber_offers(self) -> List[ProviderOffer]:
        """Get all fiber connection offers."""
        return self.get_offers_by_connection_type(ConnectionType.FIBER)

    @property
    def offer_count(self) -> int:
        """Get the total number of offers."""
        return len(self.offers)

    @property
    def available_offer_count(self) -> int:
        """Get the number of available offers."""
        return len(self.get_available_offers())

    @property
    def provider_count(self) -> int:
        """Get the number of unique providers."""
        return len(set(offer.provider_name for offer in self.offers))

    @property
    def is_expired(self) -> bool:
        """Check if the search result has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def days_until_expiration(self) -> int:
        """Get the number of days until expiration."""
        if self.is_expired:
            return 0

        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    def extend_expiration(self, days: int) -> None:
        """Extend the expiration date by the specified number of days."""
        if days <= 0:
            raise ValueError("Extension days must be positive")

        new_expiration = self.expires_at + timedelta(days=days)
        object.__setattr__(self, "expires_at", new_expiration)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the search result."""
        if not key or not key.strip():
            raise ValueError("Metadata key cannot be empty")

        self.search_metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata value by key."""
        return self.search_metadata.get(key, default)

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the search result."""
        available_offers = self.get_available_offers()

        if not available_offers:
            return {
                "total_offers": self.offer_count,
                "available_offers": 0,
                "providers": self.provider_count,
                "cheapest_monthly_cost": None,
                "fastest_speed": None,
                "fiber_available": False,
            }

        monthly_costs = [offer.monthly_cost_euros for offer in available_offers]
        speeds = [offer.speed_download_mbps for offer in available_offers]

        return {
            "total_offers": self.offer_count,
            "available_offers": len(available_offers),
            "providers": self.provider_count,
            "cheapest_monthly_cost": min(monthly_costs),
            "most_expensive_monthly_cost": max(monthly_costs),
            "fastest_speed": max(speeds),
            "slowest_speed": min(speeds),
            "fiber_available": len(self.get_fiber_offers()) > 0,
            "connection_types": list(set(offer.connection_type.value for offer in available_offers)),
        }
