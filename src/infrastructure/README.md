# Infrastructure Layer

This directory contains the infrastructure layer implementations for the enterprise refactoring project. The infrastructure layer provides concrete implementations of the interfaces defined in the application layer.

## Structure

```
src/infrastructure/
├── persistence/           # Data persistence implementations
│   ├── mock_repositories.py      # Mock repository implementations for testing
│   └── aws_dynamodb_repository.py # AWS DynamoDB implementations
├── messaging/            # Messaging and communication implementations
│   ├── mock_messaging.py         # Mock messaging implementations for testing
│   ├── mock_connection_manager.py # Mock connection management for testing
│   ├── aws_sqs_adapter.py        # AWS SQS message queue implementation
│   ├── aws_step_functions_adapter.py # AWS Step Functions workflow orchestrator
│   └── aws_websocket_adapter.py  # AWS API Gateway WebSocket management
├── external_services/    # External service adapters
│   └── mock_providers.py         # Mock provider service implementations
├── logging/             # Logging implementations
└── config/              # Configuration management
    ├── loader.py        # Configuration loading utilities
    └── models.py        # Configuration data models
```

## Mock Implementations

The mock implementations provide in-memory alternatives to cloud services for testing and development purposes. They implement the same interfaces as the production services but store data in memory instead of external systems.

### Mock Repositories

Located in `persistence/mock_repositories.py`:

- **MockSearchResultRepository**: In-memory storage for search results with full CRUD operations
- **MockConnectionRepository**: In-memory storage for connection sessions with lifecycle management
- **MockProviderOfferRepository**: In-memory caching for provider offers with expiration support

#### Features:
- Thread-safe operations using deep copying
- Automatic data validation and consistency
- Support for complex queries and filtering
- Statistics and debugging methods for testing
- Automatic cleanup of expired data

#### Usage Example:
```python
from src.infrastructure.persistence.mock_repositories import MockSearchResultRepository
from src.domain.entities.search_result import SearchResult
from src.domain.value_objects.address import Address

# Create repository
repo = MockSearchResultRepository()

# Create and save a search result
address = Address("Musterstraße", "123", "Berlin", "10115", "DE")
result = SearchResult.create_new(address, "request_123")
share_token = await repo.save_result(result)

# Retrieve the result
retrieved = await repo.get_result_by_share_token(share_token)
```

### Mock Messaging

Located in `messaging/mock_messaging.py`:

- **MockMessageQueue**: In-memory message queue with priority support and delayed delivery
- **MockWorkflowOrchestrator**: Simulated workflow execution with realistic timing and failure scenarios
- **MockEventBus**: Event publishing and subscription system with pattern matching

#### Features:
- Message priority handling (urgent, high, normal, low)
- Delayed message delivery simulation
- Workflow execution simulation with configurable success/failure rates
- Event pattern matching and subscription management
- Comprehensive statistics and monitoring

#### Usage Example:
```python
from src.infrastructure.messaging.mock_messaging import MockMessageQueue
from src.application.interfaces.messaging import MessagePriority

# Create message queue
queue = MockMessageQueue()

# Send a message
message_id = await queue.send_message(
    "test_queue", 
    {"data": "hello world"}, 
    MessagePriority.HIGH
)

# Receive messages
messages = await queue.receive_messages("test_queue", max_messages=10)
```

### Mock Connection Management

Located in `messaging/mock_connection_manager.py`:

- **MockConnectionManager**: WebSocket connection simulation with message tracking
- **MockTopicManager**: Topic-based subscription management
- **MockConnectionNotifier**: Typed notification system for different message types

#### Features:
- Connection lifecycle management (connect, disconnect, timeout)
- Message broadcasting and targeted sending
- Topic-based subscription system
- Connection filtering and querying
- Comprehensive message history tracking

#### Usage Example:
```python
from src.infrastructure.messaging.mock_connection_manager import (
    MockConnectionManager, 
    MockConnectionNotifier
)

# Create connection manager
manager = MockConnectionManager()
manager.add_mock_connection("conn_123", "websocket")

# Send message to connection
success = await manager.send_to_connection("conn_123", {"type": "hello"})

# Create notifier and send typed notifications
notifier = MockConnectionNotifier(manager)
await notifier.notify_search_initiated("conn_123", "req_123", "token_123")
```

### Mock Provider Services

Located in `external_services/mock_providers.py`:

- **MockProviderService**: Base provider with configurable behavior and realistic offer generation
- **MockByteMe**: CSV-based provider simulation
- **MockVerbynDich**: API-based provider with nested data structures
- **MockWebWunder**: Hybrid provider with metadata support
- **MockPingPerfect**: Signed request provider simulation
- **MockProviderRegistry**: Provider registration and discovery system
- **MockProviderAggregator**: Multi-provider offer aggregation with fallback strategies

#### Features:
- Realistic offer generation with proper validation
- Provider status simulation (available, rate-limited, maintenance, error)
- Rate limiting simulation with configurable thresholds
- Address validation based on supported regions
- Provider-specific data parsing (CSV, JSON, nested structures)
- Aggregation strategies (parallel, fallback, filtered)

#### Usage Example:
```python
from src.infrastructure.external_services.mock_providers import (
    MockProviderRegistry,
    MockProviderAggregator,
    MockByteMe,
    MockVerbynDich
)
from src.domain.value_objects.address import Address

# Create registry and register providers
registry = MockProviderRegistry()
await registry.register_provider(MockByteMe())
await registry.register_provider(MockVerbynDich())

# Create aggregator and get offers
aggregator = MockProviderAggregator(registry)
address = Address("Teststraße", "42", "München", "80331", "DE")
offers = await aggregator.get_aggregated_offers(address)
```

## Testing Support

All mock implementations include comprehensive testing support:

### Statistics and Monitoring
- Repository statistics (total items, expired items, etc.)
- Message queue metrics (queue depth, message counts)
- Connection statistics (active, disconnected, error states)
- Provider performance metrics (call counts, rate limits)

### Debugging Methods
- Clear all data methods for test isolation
- Message history tracking
- Connection activity logs
- Provider call tracing

### Configurable Behavior
- Failure simulation with configurable rates
- Timing simulation for realistic async behavior
- Status changes for testing error scenarios
- Rate limiting simulation

## Integration with Production Services

The mock implementations follow the same interfaces as production services, making it easy to switch between mock and real implementations using dependency injection:

```python
# Development/Testing configuration
container.register(ISearchResultRepository, MockSearchResultRepository)
container.register(IMessageQueue, MockMessageQueue)
container.register(IConnectionManager, MockConnectionManager)

# Production configuration
container.register(ISearchResultRepository, AWSDynamoDBSearchResultRepository)
container.register(IMessageQueue, AWSSQSMessageQueue)
container.register(IConnectionManager, AWSAPIGatewayWebSocketManager)
```

## Best Practices

1. **Use mocks for unit and integration testing**: Mock implementations provide fast, reliable testing without external dependencies
2. **Test with realistic data**: Mock implementations generate realistic data that matches production patterns
3. **Simulate failure scenarios**: Use the configurable failure modes to test error handling
4. **Monitor performance**: Use the statistics methods to verify expected behavior
5. **Isolate tests**: Use the clear methods to ensure test isolation
6. **Validate interfaces**: Mock implementations help validate that interfaces are complete and usable

## Performance Considerations

Mock implementations are optimized for testing performance:
- In-memory storage for fast access
- Minimal async overhead
- Efficient data structures for common operations
- Lazy initialization where appropriate
- Memory cleanup for long-running tests

The mock implementations provide a solid foundation for testing the enterprise refactoring while maintaining compatibility with production cloud services.