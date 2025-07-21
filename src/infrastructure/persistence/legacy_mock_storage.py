"""
Legacy mock storage service implementation.

This module provides the original mock IStorageService implementation for backward
compatibility with existing code that hasn't been migrated to the new repository pattern.
"""

import json
import logging
from typing import Dict, Any, Optional

from ...application.interfaces.storage import IStorageService


logger = logging.getLogger(__name__)


class MockStorageService(IStorageService):
    """
    Mock storage implementation of the legacy IStorageService interface.
    
    This class maintains backward compatibility with existing code while
    providing the same functionality as the original services/mock_storage.py.
    Stores everything in memory for testing purposes.
    """

    def __init__(self):
        """Initialize mock storage with in-memory storage."""
        # Just store everything in memory
        self.tables = {}  # table_name -> dict of items
        logger.info("Initialized mock storage service")

    async def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        """
        Store an item in memory (fake storage).
        
        Args:
            table_name: Name of the table to store in
            item: Item data to store
            
        Returns:
            bool: Always True for mock implementation
        """
        if table_name not in self.tables:
            self.tables[table_name] = {}
            logger.debug(f"Created new table in memory: {table_name}")

        # Create a simple key from the item
        # Try to use request_id if available, otherwise use a hash of the item
        key_value = item.get('request_id', item.get('id', 'unknown'))
        key_str = json.dumps(key_value, sort_keys=True)
        
        self.tables[table_name][key_str] = item
        logger.debug(f"Stored item in mock table {table_name} with key: {key_str}")
        return True

    async def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve an item from memory (fake retrieval).
        
        Args:
            table_name: Name of the table to retrieve from
            key: Key to look up the item
            
        Returns:
            Optional[Dict[str, Any]]: Retrieved item or None if not found
        """
        if table_name not in self.tables:
            logger.debug(f"Table not found in mock storage: {table_name}")
            return None

        # Create key string from the key dict
        # Try to use request_id if available, otherwise use a hash of the key
        key_value = key.get('request_id', key.get('id', 'unknown'))
        key_str = json.dumps(key_value, sort_keys=True)
        
        item = self.tables[table_name].get(key_str)
        
        if item:
            logger.debug(f"Retrieved item from mock table {table_name} with key: {key_str}")
        else:
            logger.debug(f"Item not found in mock table {table_name} with key: {key_str}")
            
        return item
    
    def clear_all_tables(self) -> None:
        """Clear all stored data (useful for testing)."""
        self.tables.clear()
        logger.info("Cleared all mock storage tables")
    
    def get_table_stats(self) -> Dict[str, int]:
        """Get statistics about stored data (useful for testing/debugging)."""
        stats = {}
        for table_name, table_data in self.tables.items():
            stats[table_name] = len(table_data)
        return stats