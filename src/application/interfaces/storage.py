"""Legacy storage interface for backward compatibility."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IStorageService(ABC):
    """
    Legacy storage interface - maintained for backward compatibility.
    
    This interface provides simple put/get operations and is used by
    existing code that hasn't been migrated to the new repository pattern.
    """

    @abstractmethod
    async def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        """
        Store an item in the database.
        
        Args:
            table_name: Name of the table/collection to store in
            item: Data to store
            
        Returns:
            bool: True if storage was successful
        """
        pass

    @abstractmethod
    async def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get an item from the database.
        
        Args:
            table_name: Name of the table/collection to retrieve from
            key: Key to look up the item
            
        Returns:
            Optional[Dict[str, Any]]: Retrieved item or None if not found
        """
        pass