"""Infrastructure persistence layer."""

# Import mock repositories (always available)
from .mock_repositories import (
    MockSearchResultRepository,
    MockConnectionRepository,
    MockProviderOfferRepository
)

# Legacy storage implementations removed - use repository pattern instead

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
    'MockProviderOfferRepository'
]

if _aws_available:
    __all__.extend([
        'AWSDynamoDBSearchResultRepository',
        'AWSDynamoDBConnectionRepository', 
        'AWSDynamoDBProviderOfferRepository',
        'DynamoDBTypeConverter'
    ])