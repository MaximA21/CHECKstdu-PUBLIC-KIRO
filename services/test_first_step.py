import pytest

from lambda_functions.results_handler import results_handler
from services.mock_storage import MockStorageService


@pytest.mark.asyncio
async def test_store_results_with_mock():
    """Your first dependency injection test!"""

    # Create a fake storage service
    mock_storage = MockStorageService()

    # Test your function with the mock
    success = await store_results_with_injection(
        storage_service=mock_storage,  # ← Inject the mock!
        request_id='test-123',
        provider_name='byteme',
        offers_data=[{'speed': 100}],
        share_token='abc123'
    )

    # Assert it worked
    assert success == True

    # Check the mock actually stored it
    stored_item = await mock_storage.get_item(
        'provider-results',
        {'request_id': 'test-123'}
    )
    assert stored_item is not None
    assert stored_item['provider_name'] == 'byteme'

# Run this test:
# pytest test_first_step.py -v