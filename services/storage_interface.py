from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class IStorageService(ABC):
    """Simple storage interface - just put and get for now"""

    @abstractmethod
    async def put_item(self, table_name: str, item: Dict[str, Any]) -> bool:
        """Store an item in the database"""
        pass

    @abstractmethod
    async def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get an item from the database"""
        pass