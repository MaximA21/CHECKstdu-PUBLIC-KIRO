"""Application layer interfaces package."""

from .connections import ConnectionType, IConnectionManager, IConnectionNotifier, ITopicManager, MessageType
from .logging import (
    ILogAggregator,
    ILogConfiguration,
    ILogDestination,
    ILogger,
    ILoggerFactory,
    IStructuredLogger,
    LogFormat,
    LogLevel,
)

# Legacy IStorageService removed - use repository interfaces instead
from .messaging import IEventBus, IMessageQueue, IWorkflowOrchestrator, MessagePriority, WorkflowStatus
from .providers import (
    IByteMe,
    IPingPerfect,
    IProviderAggregator,
    IProviderRegistry,
    IProviderService,
    IVerbynDich,
    IWebWunder,
    ProviderStatus,
    ProviderType,
)
from .repositories import IConnectionRepository, IProviderOfferRepository, ISearchResultRepository

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
    "LogFormat",
]
