"""Infrastructure persistence layer."""

# Import mock repositories (always available)
from .mock_repositories import (
    MockSearchResultRepository,
    MockConnectionRepository,
    MockProviderOfferRepository
)

# Import legacy storage implementations for backward compatibility
from .legacy_mock_storage import MockStorageService

# Import AWS legacy storage (optional, requires boto3)
try:
    from .legacy_aws_storage import AWSDynamoDBService
    _aws_legacy_available = True
except ImportError:
    _aws_legacy_available = False

# Import AWS repositories (optional, requires boto3)
try:
    from .aws_dynamodb_repository import (
        AWSDynamoDBSearchResultRepository,
        AWSDynamoDBConnectionRepository,
        AWSDynamoDBProviderOfferRepository,
        DynamoDBTypeConverter
    )
    _aws_available = True
except ImportError:
    _aws_available = False

__all__ = [
    'MockSearchResultRepository',
    'MockConnectionRepository',
    'MockProviderOfferRepository',
    'MockStorageService'
]

if _aws_legacy_available:
    __all__.append('AWSDynamoDBService')

if _aws_available:
    __all__.extend([
        'AWSDynamoDBSearchResultRepository',
        'AWSDynamoDBConnectionRepository', 
        'AWSDynamoDBProviderOfferRepository',
        'DynamoDBTypeConverter'
    ])