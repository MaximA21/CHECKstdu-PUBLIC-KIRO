"""Infrastructure external services layer."""

# Import concrete provider implementations
from .byteme_adapter import ByteMeAdapter
from .verbyndich_adapter import VerbynDichAdapter
from .webwunder_adapter import WebWunderAdapter
from .ping_perfect_adapter import PingPerfectAdapter
from .provider_registry import ProviderRegistry
from .provider_aggregator import ProviderAggregator

# Import mock provider implementations (always available)
from .mock_providers import (
    MockProviderService,
    MockByteMe,
    MockVerbynDich,
    MockWebWunder,
    MockPingPerfect,
    MockProviderRegistry,
    MockProviderAggregator,
)

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
