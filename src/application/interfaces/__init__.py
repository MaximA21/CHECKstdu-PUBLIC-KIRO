"""Application layer interfaces package."""

from .repositories import (
    ISearchResultRepository,
    IConnectionRepository,
    IProviderOfferRepository
)
# Legacy IStorageService removed - use repository interfaces instead
from .messaging import (
    IMessageQueue,
    IWorkflowOrchestrator,
    IEventBus,
    MessagePriority,
    WorkflowStatus
)
from .connections import (
    IConnectionManager,
    ITopicManager,
    IConnectionNotifier,
    ConnectionType,
    MessageType
)
from .providers import (
    IProviderService,
    IByteMe,
    IVerbynDich,
    IWebWunder,
    IPingPerfect,
    IProviderRegistry,
    IProviderAggregator,
    ProviderStatus,
    ProviderType
)
from .logging import (
    ILogger,
    IStructuredLogger,
    ILoggerFactory,
    ILogConfiguration,
    ILogDestination,
    ILogAggregator,
    LogLevel,
    LogFormat
)

__all__ = [
    # Repository interfaces
    "ISearchResultRepository",
    "IConnectionRepository", 
    "IProviderOfferRepository",
    
    # Legacy storage interface
    "IStorageService",
    
    # Messaging interfaces
    "IMessageQueue",
    "IWorkflowOrchestrator",
    "IEventBus",
    "MessagePriority",
    "WorkflowStatus",
    
    # Connection interfaces
    "IConnectionManager",
    "ITopicManager",
    "IConnectionNotifier",
    "ConnectionType",
    "MessageType",
    
    # Provider interfaces
    "IProviderService",
    "IByteMe",
    "IVerbynDich", 
    "IWebWunder",
    "IPingPerfect",
    "IProviderRegistry",
    "IProviderAggregator",
    "ProviderStatus",
    "ProviderType",
    
    # Logging interfaces
    "ILogger",
    "IStructuredLogger",
    "ILoggerFactory",
    "ILogConfiguration",
    "ILogDestination",
    "ILogAggregator",
    "LogLevel",
    "LogFormat"
]