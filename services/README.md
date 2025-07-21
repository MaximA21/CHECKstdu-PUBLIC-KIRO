# Services Folder Migration Notice

⚠️ **DEPRECATED**: This folder has been migrated to the new enterprise architecture.

## Migration Status

The services in this folder have been moved to the new clean architecture structure:

### Migrated Files

| Old Location | New Location | Status |
|-------------|-------------|---------|
| `services/aws_storage.py` | `src/infrastructure/persistence/legacy_aws_storage.py` | ✅ Migrated |
| `services/mock_storage.py` | `src/infrastructure/persistence/legacy_mock_storage.py` | ✅ Migrated |
| `services/storage_interface.py` | `src/application/interfaces/storage.py` | ✅ Migrated |
| `services/logging_config.py` | `src/infrastructure/logging/legacy_logging_config.py` | ✅ Migrated |

### Updated Import Paths

If you need to use these services, update your imports:

#### Legacy Storage Service
```python
# Old import
from services.aws_storage import AWSDynamoDBService
from services.mock_storage import MockStorageService
from services.storage_interface import IStorageService

# New import
from src.infrastructure.persistence.legacy_aws_storage import AWSDynamoDBService
from src.infrastructure.persistence.legacy_mock_storage import MockStorageService
from src.application.interfaces.storage import IStorageService
```

#### Legacy Logging Configuration
```python
# Old import
from services.logging_config import get_lambda_logger, configure_logger

# New import
from src.infrastructure.logging.legacy_logging_config import get_lambda_logger, configure_logger
```

### Recommended Migration Path

Instead of using the legacy implementations, consider migrating to the new repository pattern:

```python
# New repository pattern (recommended)
from src.application.interfaces.repositories import ISearchResultRepository
from src.infrastructure.persistence.aws_dynamodb_repository import AWSDynamoDBSearchResultRepository
from src.infrastructure.persistence.mock_repositories import MockSearchResultRepository

# New logging pattern (recommended)
from src.application.interfaces.logging import ILoggerFactory
from src.infrastructure.logging.logger_factory import LoggerFactory
```

### Dependency Injection

The new architecture uses dependency injection. Services are automatically configured based on environment:

```python
from src.shared.dependency_injection.bootstrap import create_container

# Create DI container
container = create_container()

# Get services
storage_service = container.resolve(IStorageService)  # Legacy interface
search_repo = container.resolve(ISearchResultRepository)  # New interface
logger_factory = container.resolve(ILoggerFactory)  # New interface
```

### Files Remaining in Services Folder

The following files remain for backward compatibility and testing:

- `test_first_step.py` - Updated to use new imports
- `test_logging_config.py` - Updated to use new imports  
- `logging_example.py` - Updated to use new imports
- `run_logging_tests.py` - Test runner for logging tests

These files have been updated to use the new import paths but remain in the services folder to maintain existing test workflows.

## Next Steps

1. **For new code**: Use the new repository and logging interfaces
2. **For existing code**: Update imports to use the new locations
3. **For testing**: Use the dependency injection container to get mock implementations
4. **For production**: Services are automatically selected based on environment configuration

## Support

If you encounter issues during migration, check:

1. Import paths are updated correctly
2. Dependency injection container is properly configured
3. Environment variables are set for service selection

The legacy implementations maintain full backward compatibility while providing a migration path to the new architecture.