"""Infrastructure external services layer."""

# Import concrete provider implementations
from .byteme_adapter import ByteMeAdapter

# Import mock provider implementations (always available)
from .mock_providers import (
    MockByteMe,
    MockPingPerfect,
    MockProviderAggregator,
    MockProviderRegistry,
    MockProviderService,
    MockVerbynDich,
    MockWebWunder,
)
from .ping_perfect_adapter import PingPerfectAdapter
from .provider_aggregator import ProviderAggregator
from .provider_registry import ProviderRegistry
from .verbyndich_adapter import VerbynDichAdapter
from .webwunder_adapter import WebWunderAdapter

__all__ = [
    # Concrete implementations
    "ByteMeAdapter",
    "VerbynDichAdapter",
    "WebWunderAdapter",
    "PingPerfectAdapter",
    "ProviderRegistry",
    "ProviderAggregator",
    # Mock implementations
    "MockProviderService",
    "MockByteMe",
    "MockVerbynDich",
    "MockWebWunder",
    "MockPingPerfect",
    "MockProviderRegistry",
    "MockProviderAggregator",
]
