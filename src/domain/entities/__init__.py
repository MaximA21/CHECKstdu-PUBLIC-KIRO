"""Domain entities - Core business entities."""

from .provider_offer import ProviderOffer, ConnectionType, OfferStatus
from .search_result import SearchResult
from .connection_session import ConnectionSession, ConnectionStatus, SessionConnectionType

__all__ = [
    "ProviderOffer",
    "ConnectionType",
    "OfferStatus",
    "SearchResult",
    "ConnectionSession",
    "ConnectionStatus",
    "SessionConnectionType",
]
