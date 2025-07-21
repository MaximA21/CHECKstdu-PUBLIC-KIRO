# Enterprise Clean Architecture Structure

This directory implements a clean architecture pattern with clear separation of concerns following domain-driven design principles.

## Layer Structure

### Domain Layer (`domain/`)
Contains the enterprise business rules and core business logic.

- **entities/**: Core business entities that encapsulate business rules
- **value_objects/**: Immutable objects representing domain concepts
- **services/**: Domain services containing business logic that doesn't naturally fit within entities

### Application Layer (`application/`)
Contains application-specific business rules and orchestrates the flow of data.

- **use_cases/**: Application-specific business rules and workflows
- **interfaces/**: Abstract interfaces for external concerns (repositories, services)
- **dto/**: Data transfer objects for communication between layers

### Infrastructure Layer (`infrastructure/`)
Contains implementations of external concerns and frameworks.

- **persistence/**: Database implementations and repository adapters
- **messaging/**: Message queue implementations (SQS, Service Bus, etc.)
- **external_services/**: Third-party service adapters and clients
- **logging/**: Logging implementations and adapters
- **config/**: Configuration management and environment setup

### Presentation Layer (`presentation/`)
Contains interface adapters that convert data between external interfaces and internal use cases.

- **lambda_handlers/**: AWS Lambda entry points and handlers
- **http_controllers/**: HTTP API controllers for container deployment
- **websocket_handlers/**: WebSocket connection handlers

### Shared Layer (`shared/`)
Contains cross-cutting concerns and utilities used across all layers.

- **dependency_injection/**: DI container and service registration
- **exceptions/**: Custom exception types and error handling

## Dependency Rules

1. **Dependency Direction**: Dependencies point inward toward the domain layer
2. **Domain Independence**: Domain layer has no dependencies on external frameworks
3. **Interface Segregation**: Application layer defines interfaces implemented by infrastructure
4. **Inversion of Control**: High-level modules don't depend on low-level modules

## Benefits

- **Testability**: Easy to unit test business logic in isolation
- **Flexibility**: Easy to swap implementations (AWS → Azure, etc.)
- **Maintainability**: Clear separation of concerns
- **Scalability**: Supports multiple deployment patterns (Lambda, containers, servers)